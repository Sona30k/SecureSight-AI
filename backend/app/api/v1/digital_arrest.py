from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import case as sql_case
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.inference.voice import VoiceAnalysisPipeline
from app.auth import CurrentUser
from app.database import get_db
from app.graph import Neo4jClient
from app.models import (
    AuditLog, CallerHistory, DigitalArrestCase, FraudReport, LiveCallSession,
    ReportStatus, UserRole,
)
from app.realtime import hub
from app.schemas import (
    DigitalArrestAction, DigitalArrestDashboard, DigitalArrestHistoryItem,
    DigitalArrestReportCreate, DigitalArrestRequest, DigitalArrestResponse,
    ExternalAlertRequest, LiveCallStart, LiveTranscriptChunk,
)
from app.services import ExternalDispatchService, TelecomSpoofAnalyzer
from app.services.digital_arrest import DigitalArrestService, investigation_pdf

router = APIRouter(prefix="/digital-arrest", tags=["Digital Arrest Detection"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _scope(statement, user):
    if user.role == UserRole.citizen:
        return statement.where(DigitalArrestCase.analyzed_by == user.id)
    return statement


async def _case_or_404(db: AsyncSession, case_id: UUID, user) -> DigitalArrestCase:
    statement = _scope(select(DigitalArrestCase).where(DigitalArrestCase.id == case_id), user)
    item = await db.scalar(statement)
    if item is None:
        raise HTTPException(status_code=404, detail="Digital arrest case not found")
    return item


async def _sync_graph(case: DigitalArrestCase, citizen: str, bank_accounts=None, devices=None) -> bool:
    if case.scam_probability <= 0.8:
        return False
    client = Neo4jClient()
    try:
        await client.create_report({
            "case_id": str(case.id), "citizen": citizen, "phones": [case.caller_number],
            "devices": devices or [], "bank_accounts": bank_accounts or [],
            "upi_ids": [], "ip_addresses": [], "risk_score": case.risk_score,
        })
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def _broadcast_case(case: DigitalArrestCase, event: str = "digital_arrest.analyzed") -> None:
    payload = {
        "case_id": str(case.id), "caller_number": case.caller_number,
        "risk_score": case.risk_score, "threat_level": case.threat_level,
        "status": case.status, "transcript": case.transcript,
        "timeline": case.conversation_stages,
    }
    await hub.broadcast("digital-arrest", event, payload)
    await hub.broadcast("dashboard", event, payload)
    if case.risk_score >= 90:
        await hub.broadcast("alerts", "digital_arrest.critical", payload)


@router.post("/analyze", response_model=DigitalArrestResponse)
async def analyze_call(payload: DigitalArrestRequest, user: CurrentUser, db: DbSession):
    service = DigitalArrestService(db)
    case, result = await service.analyze(
        caller_number=payload.caller_number, transcript=payload.transcript,
        duration=payload.duration, video_call=payload.video_call,
        location=payload.resolved_location, country=payload.country,
        spoof_detected=payload.spoof_detected, user=user,
        telecom_signals=payload.telecom_signals.model_dump() if payload.telecom_signals else None,
    )
    if case.risk_score >= 90 and user.role in {UserRole.police, UserRole.administrator}:
        dispatch = await ExternalDispatchService(db).dispatch(
            case_id=case.id, integration="mha", action="submit_alert",
            payload={
                "case_id": str(case.id), "caller_number": case.caller_number,
                "risk_score": case.risk_score, "threat_level": case.threat_level,
                "detected_keywords": case.detected_keywords,
            },
            user_id=user.id,
        )
        result["external_actions"].append({
            "integration": "mha", "action": "submit_alert", "status": dispatch.status,
        })
    graph_synced = await _sync_graph(case, user.email)
    if graph_synced:
        db.add(AuditLog(
            user_id=user.id, action="digital_arrest.graph_sync",
            resource="digital_arrest_case", resource_id=str(case.id), details={"status": "created"},
        ))
        await db.commit()
    await _broadcast_case(case)
    return DigitalArrestResponse(case_id=case.id, **result)


@router.post("/analyze-audio", response_model=DigitalArrestResponse)
async def analyze_audio(
    user: CurrentUser, db: DbSession,
    audio: Annotated[UploadFile, File()],
    caller_number: Annotated[str, Form(min_length=7, max_length=32)],
    duration: Annotated[int, Form(ge=0, le=86_400)] = 0,
    video_call: Annotated[bool, Form()] = False,
    location: Annotated[str | None, Form(max_length=150)] = None,
    country: Annotated[str | None, Form(max_length=100)] = None,
    spoof_detected: Annotated[bool | None, Form()] = None,
):
    content = await audio.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds the 25 MB limit")
    try:
        voice = await VoiceAnalysisPipeline().analyze(audio.filename or "call.wav", content, caller_number)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    transcript = str(voice.details.get("transcript", "")).strip()
    if not transcript or transcript.startswith("Audio transcription requires"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Whisper speech-to-text is not installed on this server",
        )
    service = DigitalArrestService(db)
    evidence = await service.save_audio(audio.filename or "call.wav", audio.content_type or "application/octet-stream", content)
    normalized = DigitalArrestRequest(
        caller_number=caller_number, transcript=transcript, duration=duration,
        video_call=video_call, location=location, country=country, spoof_detected=spoof_detected,
    )
    case, result = await service.analyze(
        caller_number=normalized.caller_number, transcript=transcript, duration=duration,
        video_call=video_call, location=location, country=country,
        spoof_detected=spoof_detected, user=user, source="audio", evidence=evidence,
        voice_forensics=voice.details.get("voice_forensics"),
    )
    await _sync_graph(case, user.email)
    await _broadcast_case(case)
    return DigitalArrestResponse(case_id=case.id, **result)


@router.post("/live/start", status_code=201)
async def start_live_call(payload: LiveCallStart, user: CurrentUser, db: DbSession):
    session = LiveCallSession(
        caller_number=payload.caller_number.replace(" ", "").replace("-", ""),
        video_call=payload.video_call, consent_confirmed=payload.consent_confirmed,
        telecom_signals=payload.telecom_signals.model_dump() if payload.telecom_signals else {},
        started_by=user.id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, "status": session.status, "started_at": session.created_at}


async def _live_session(db: AsyncSession, session_id: UUID, user) -> LiveCallSession:
    item = await db.get(LiveCallSession, session_id)
    if not item or (user.role == UserRole.citizen and item.started_by != user.id):
        raise HTTPException(status_code=404, detail="Live call session not found")
    return item


@router.post("/live/{session_id}/chunk")
async def append_live_chunk(
    session_id: UUID, payload: LiveTranscriptChunk, user: CurrentUser, db: DbSession,
):
    item = await _live_session(db, session_id, user)
    if item.status not in {"active", "ready"}:
        raise HTTPException(status_code=409, detail="Live call session is already finalized")
    item.transcript = f"{item.transcript}\n{payload.text}".strip()
    if len(item.transcript) > 50_000:
        raise HTTPException(status_code=413, detail="Live transcript exceeds 50,000 characters")
    item.duration = max(item.duration, payload.duration)
    history = await db.scalar(select(CallerHistory).where(
        CallerHistory.caller_number == item.caller_number
    ))
    spoof = TelecomSpoofAnalyzer().analyze(item.caller_number, item.telecom_signals)
    preview = DigitalArrestService(db).engine.analyze(
        transcript=item.transcript, duration=item.duration, video_call=item.video_call,
        spoof_detected=bool(spoof["detected"]), spoof_score=int(spoof["score"]),
        previous_reports=history.report_count if history else 0,
    )
    preview["spoof_score"], preview["spoof_reasons"] = spoof["score"], spoof["reasons"]
    item.latest_analysis = preview
    item.status = "ready" if payload.final else "active"
    await db.commit()
    await hub.broadcast("digital-arrest", "digital_arrest.live_update", {
        "session_id": str(item.id), "caller_number": item.caller_number,
        "risk_score": preview["risk_score"], "threat_level": preview["threat_level"],
        "timeline": preview["conversation_stages"], "transcript": item.transcript,
    })
    return {"session_id": item.id, "status": item.status, **preview}


@router.post("/live/{session_id}/finalize", response_model=DigitalArrestResponse)
async def finalize_live_call(session_id: UUID, user: CurrentUser, db: DbSession):
    item = await _live_session(db, session_id, user)
    if item.finalized_case_id:
        case = await _case_or_404(db, item.finalized_case_id, user)
        latest = item.latest_analysis
        latest.setdefault("caller_reputation", {
            "caller_number": case.caller_number, "report_count": 0, "average_risk": case.risk_score,
            "reputation_score": max(0, 100-case.risk_score), "total_victims": 0,
            "last_seen": case.created_at, "label": "unknown",
        })
        return DigitalArrestResponse(case_id=case.id, **latest)
    if len(item.transcript.strip()) < 5:
        raise HTTPException(status_code=422, detail="Live transcript is too short to finalize")
    case, result = await DigitalArrestService(db).analyze(
        caller_number=item.caller_number, transcript=item.transcript, duration=item.duration,
        video_call=item.video_call, location=None, country=None, spoof_detected=None,
        telecom_signals=item.telecom_signals, user=user, source="live",
    )
    stored_result = DigitalArrestResponse(case_id=case.id, **result).model_dump(
        mode="json", exclude={"case_id"}
    )
    item.status, item.finalized_case_id, item.latest_analysis = "finalized", case.id, stored_result
    await db.commit()
    await _sync_graph(case, user.email)
    await _broadcast_case(case, "digital_arrest.live_finalized")
    return DigitalArrestResponse(case_id=case.id, **result)


@router.post("/{case_id}/external-action")
async def external_action(
    case_id: UUID, payload: ExternalAlertRequest, user: CurrentUser, db: DbSession,
):
    item = await _case_or_404(db, case_id, user)
    allowed = {
        "mha": {UserRole.police, UserRole.administrator},
        "bank": {UserRole.bank, UserRole.police, UserRole.administrator},
    }
    if user.role not in allowed[payload.integration]:
        raise HTTPException(status_code=403, detail="Your role cannot request this external action")
    if payload.integration == "bank" and not payload.transaction_id and not payload.account_reference:
        raise HTTPException(status_code=422, detail="A transaction or account reference is required for a bank hold")
    dispatch = await ExternalDispatchService(db).dispatch(
        case_id=item.id, integration=payload.integration, action=payload.action,
        payload={
            "case_id": str(item.id), "caller_number": item.caller_number,
            "risk_score": item.risk_score, **payload.model_dump(exclude={"integration", "action"}),
        },
        user_id=user.id,
    )
    db.add(AuditLog(
        user_id=user.id, action=f"digital_arrest.external.{payload.action}",
        resource="digital_arrest_case", resource_id=str(item.id),
        details={"integration": payload.integration, "dispatch_status": dispatch.status},
    ))
    await db.commit()
    return {
        "dispatch_id": dispatch.id, "integration": dispatch.integration,
        "action": dispatch.action, "status": dispatch.status,
        "response": dispatch.response_payload,
    }


@router.post("/report", status_code=201)
async def report_case(payload: DigitalArrestReportCreate, user: CurrentUser, db: DbSession):
    item = await _case_or_404(db, payload.case_id, user)
    if not item.report_saved:
        item.report_saved = True
        item.status = "reported"
        history = await db.scalar(select(CallerHistory).where(CallerHistory.caller_number == item.caller_number))
        if history:
            history.report_count += 1
            history.total_victims += payload.total_victims
            history.reputation_score = max(0, history.reputation_score - 8)
        db.add(FraudReport(
            title=f"Digital arrest call from {item.caller_number}",
            description=payload.notes or item.recommendation, category="digital_arrest",
            location=item.caller_location, status=ReportStatus.submitted,
            risk_score=item.risk_score, reporter_id=user.id,
        ))
        db.add(AuditLog(
            user_id=user.id, action="digital_arrest.report",
            resource="digital_arrest_case", resource_id=str(item.id),
            details={"total_victims": payload.total_victims},
        ))
        await db.commit()
    graph_synced = await _sync_graph(
        item, user.email, bank_accounts=payload.bank_accounts, devices=payload.device_ids,
    )
    await _broadcast_case(item, "digital_arrest.reported")
    return {"case_id": item.id, "status": item.status, "graph_synced": graph_synced}


@router.post("/{case_id}/actions")
async def case_action(case_id: UUID, payload: DigitalArrestAction, user: CurrentUser, db: DbSession):
    item = await _case_or_404(db, case_id, user)
    if payload.action == "block":
        item.blocked = True
        item.status = "blocked"
    elif payload.action == "notify_police":
        item.police_notified = True
        item.status = "police_notified"
    else:
        item.report_saved = True
        item.status = "saved"
    db.add(AuditLog(
        user_id=user.id, action=f"digital_arrest.{payload.action}",
        resource="digital_arrest_case", resource_id=str(item.id),
        details={"notes": payload.notes},
    ))
    await db.commit()
    await _broadcast_case(item, f"digital_arrest.{payload.action}")
    return {
        "case_id": item.id, "status": item.status, "blocked": item.blocked,
        "police_notified": item.police_notified, "report_saved": item.report_saved,
    }


@router.get("/history", response_model=list[DigitalArrestHistoryItem])
async def history(
    user: CurrentUser, db: DbSession,
    caller_number: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
):
    statement = _scope(select(DigitalArrestCase), user)
    if caller_number:
        statement = statement.where(DigitalArrestCase.caller_number == caller_number)
    return list((await db.scalars(statement.order_by(DigitalArrestCase.created_at.desc()).limit(limit))).all())


@router.get("/dashboard", response_model=DigitalArrestDashboard)
async def dashboard(user: CurrentUser, db: DbSession):
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    scope_filters = [DigitalArrestCase.analyzed_by == user.id] if user.role == UserRole.citizen else []
    totals = (await db.execute(select(
        func.count(DigitalArrestCase.id),
        func.coalesce(func.sum(sql_case((
            (DigitalArrestCase.created_at >= start) & (DigitalArrestCase.scam_probability >= .55), 1
        ), else_=0)), 0),
        func.coalesce(func.sum(sql_case((DigitalArrestCase.blocked.is_(True), 1), else_=0)), 0),
        func.coalesce(func.avg(DigitalArrestCase.risk_score), 0),
        func.count(func.distinct(sql_case((DigitalArrestCase.risk_score >= 70, DigitalArrestCase.caller_number)))),
    ).where(*scope_filters))).one()
    distribution = {label: 0 for label in ("low", "medium", "high", "critical")}
    for level, count in (await db.execute(
        select(DigitalArrestCase.threat_level, func.count(DigitalArrestCase.id))
        .where(*scope_filters).group_by(DigitalArrestCase.threat_level)
    )).all():
        distribution[level] = count
    caller_scope = select(DigitalArrestCase.caller_number).where(*scope_filters).distinct()
    reputations = list((await db.scalars(
        select(CallerHistory).where(CallerHistory.caller_number.in_(caller_scope))
        .order_by(CallerHistory.report_count.desc(), CallerHistory.average_risk.desc()).limit(8)
    )).all())
    keyword_rows = (await db.scalars(
        select(DigitalArrestCase.detected_keywords).where(*scope_filters)
        .order_by(DigitalArrestCase.created_at.desc()).limit(5000)
    )).all()
    keyword_counter = Counter(keyword for keywords in keyword_rows for keyword in keywords)
    daily_rows = dict((await db.execute(
        select(func.date(DigitalArrestCase.created_at), func.count(DigitalArrestCase.id))
        .where(DigitalArrestCase.created_at >= start - timedelta(days=6), *scope_filters)
        .group_by(func.date(DigitalArrestCase.created_at))
    )).all())
    daily = []
    for offset in range(6, -1, -1):
        day = (start - timedelta(days=offset)).date()
        daily.append({"date": day.isoformat(), "count": int(daily_rows.get(day, daily_rows.get(day.isoformat(), 0)))})
    return DigitalArrestDashboard(
        today_scam_calls=int(totals[1]), blocked_calls=int(totals[2]),
        average_risk=round(float(totals[3]), 1), high_risk_numbers=int(totals[4]),
        total_cases=int(totals[0]), risk_distribution=distribution,
        common_keywords=[
            {"keyword": keyword, "count": count} for keyword, count in keyword_counter.most_common(8)
        ],
        top_numbers=[{
            "caller_number": item.caller_number, "reports": item.report_count,
            "average_risk": item.average_risk, "reputation_score": item.reputation_score,
        } for item in reputations],
        daily_cases=daily,
    )


@router.get("/{case_id}/evidence.pdf")
async def download_evidence(case_id: UUID, user: CurrentUser, db: DbSession):
    item = await _case_or_404(db, case_id, user)
    db.add(AuditLog(
        user_id=user.id, action="digital_arrest.evidence_download",
        resource="digital_arrest_case", resource_id=str(item.id),
    ))
    await db.commit()
    return Response(
        investigation_pdf(item), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="shieldiq-{item.id}.pdf"'},
    )
