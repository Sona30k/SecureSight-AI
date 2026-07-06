import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ai.inference.voice import VoiceAnalysisPipeline
from app.auth import CurrentUser
from app.config import settings
from app.database import get_db
from app.models import AIAnalysis, ChannelInteraction, GovernmentSubmission, SpeechStream
from app.realtime import hub
from app.schemas import AssistantResponse, ChannelWebhook, SpeechStreamStart, SpeechTranscriptChunk
from app.services import AnalysisRecorder, ChatService, GroundedAssistantService
from app.services.assistant_orchestrator import ContextType
from app.services.llm import LLMRouter, ProviderName

router = APIRouter(prefix="/assistant", tags=["AI Citizen Assistant"])


@router.post("/chat", response_model=AssistantResponse)
async def chat(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    text: str = Form(..., min_length=2, max_length=20_000),
    image: UploadFile | None = File(None),
    voice: UploadFile | None = File(None),
    pdf: UploadFile | None = File(None),
    language: str = Form("en"),
    provider: ProviderName = Form("auto"),
    context_type: ContextType = Form("auto"),
    context_id: UUID | None = Form(None),
):
    started = time.perf_counter()
    uploads = [item for item in (image, voice, pdf) if item]
    if len(uploads) > 1:
        raise HTTPException(status_code=422, detail="Attach only one file per analysis request")
    attachment = "image" if image else "voice" if voice else "pdf" if pdf else None
    upload = uploads[0] if uploads else None
    content = await upload.read() if upload else None
    if content and len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Attachment exceeds the 25 MB limit")
    try:
        result = await GroundedAssistantService(db).answer(
            text=text, user=user, provider=provider,
            context_type=context_type, context_id=context_id,
            attachment_type=attachment, attachment=content,
            filename=upload.filename if upload else "", language=language,
        )
    except (ValueError, OSError, EOFError) as exc:
        raise HTTPException(status_code=422, detail=f"Unable to process attachment: {exc}")
    analysis = await AnalysisRecorder.record(
        db, module="assistant", input_type=attachment or "text",
        result={
            **result, "prediction": result["risk_level"],
            "model_version": result["model"],
        },
        user_id=user.id, started_at=started,
    )
    await db.commit()
    return AssistantResponse(analysis_id=analysis.id, **result)


@router.get("/providers")
async def assistant_providers(user: CurrentUser):
    return {
        "default": settings.assistant_provider,
        "providers": await LLMRouter().status(),
    }


@router.post("/speech/stream/start", status_code=201)
async def start_speech_stream(payload: SpeechStreamStart, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    await db.execute(
        update(SpeechStream)
        .where(SpeechStream.started_by == user.id, SpeechStream.status == "active")
        .values(status="abandoned", finalized_at=datetime.now(timezone.utc))
    )
    stream = SpeechStream(language=payload.language, started_by=user.id)
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    return {"stream_id": stream.id, "status": stream.status, "language": stream.language}


@router.post("/speech/stream/{stream_id}/chunk")
async def speech_chunk(
    stream_id: UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)],
    audio: UploadFile = File(...),
):
    stream = await db.get(SpeechStream, stream_id)
    if not stream or stream.started_by != user.id:
        raise HTTPException(status_code=404, detail="Speech stream not found")
    if stream.status != "active":
        raise HTTPException(status_code=409, detail="Speech stream is finalized")
    content = await audio.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio chunk exceeds 10 MB")
    try:
        result = await VoiceAnalysisPipeline().analyze(audio.filename or "chunk.webm", content)
    except (ValueError, OSError, EOFError) as exc:
        raise HTTPException(status_code=422, detail=f"Unable to process audio chunk: {exc}")
    transcript = str(result.details.get("transcript", ""))
    if "requires the optional Whisper model" in transcript:
        transcript = ""
    if transcript:
        stream.transcript = f"{stream.transcript} {transcript}".strip()
    stream.chunk_count += 1
    stream.latest_forensics = result.details.get("voice_forensics", {})
    await db.commit()
    payload = {
        "stream_id": str(stream.id), "chunk_count": stream.chunk_count,
        "transcript_delta": transcript, "transcript": stream.transcript,
        "risk_score": result.risk_score, "voice_forensics": stream.latest_forensics,
        "speech_model": result.details.get("speech_model"),
    }
    await hub.broadcast("speech", "speech.chunk_analyzed", payload)
    return payload


@router.post("/speech/stream/{stream_id}/transcript")
async def append_browser_transcript(
    stream_id: UUID, payload: SpeechTranscriptChunk, user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stream = await db.get(SpeechStream, stream_id)
    if not stream or stream.started_by != user.id:
        raise HTTPException(status_code=404, detail="Speech stream not found")
    if stream.status != "active":
        raise HTTPException(status_code=409, detail="Speech stream is finalized")
    stream.transcript = f"{stream.transcript} {payload.text.strip()}".strip()
    await db.commit()
    response = {"stream_id": str(stream.id), "transcript": stream.transcript, "source": "browser_speech_recognition"}
    await hub.broadcast("speech", "speech.transcript", response)
    return response


@router.post("/speech/stream/{stream_id}/finalize")
async def finalize_speech_stream(stream_id: UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    stream = await db.get(SpeechStream, stream_id)
    if not stream or stream.started_by != user.id:
        raise HTTPException(status_code=404, detail="Speech stream not found")
    stream.status, stream.finalized_at = "finalized", datetime.now(timezone.utc)
    result = await GroundedAssistantService(db).answer(
        text=stream.transcript or "Audio stream contained no locally transcribed speech.",
        user=user, language=stream.language,
    )
    analysis = await AnalysisRecorder.record(
        db, module="assistant_speech_stream", input_type="voice_stream",
        result={**result, "prediction": result["risk_level"], "model_version": result["model"]},
        user_id=user.id, started_at=time.perf_counter(),
    )
    await db.commit()
    return {"stream_id": stream.id, "status": stream.status, "transcript": stream.transcript,
            "voice_forensics": stream.latest_forensics, "analysis_id": analysis.id, **result}


@router.post("/channels/{channel}/webhook")
async def channel_webhook(
    channel: str, payload: ChannelWebhook, db: Annotated[AsyncSession, Depends(get_db)],
    x_shieldiq_channel_secret: Annotated[str | None, Header()] = None,
):
    if channel not in {"whatsapp", "ivr"}:
        raise HTTPException(status_code=404, detail="Unsupported channel")
    expected = settings.channel_webhook_secret
    if not expected or not x_shieldiq_channel_secret or not hmac.compare_digest(expected, x_shieldiq_channel_secret):
        raise HTTPException(status_code=401, detail="Invalid channel webhook credentials")
    local = await ChatService().chat(payload.text, language=payload.language)
    llm_router = LLMRouter()
    generated, failures = await llm_router.generate(
        "auto", llm_router.prompt(payload.text, local, None, payload.language),
    )
    result = (
        {
            **generated.answer.model_dump(), "language": payload.language,
            "provider": generated.provider, "model": generated.model,
            "provider_status": "live", "provider_failures": failures,
        }
        if generated else
        {
            **local, "provider": "rules", "model": "sentinel-rules-v2",
            "provider_status": "fallback", "provider_failures": failures,
        }
    )
    item = ChannelInteraction(
        channel=channel, external_id=payload.external_id, sender_reference=payload.sender_reference,
        language=payload.language, request_text=payload.text, response_text=result["response"],
        risk_level=result["risk_level"], confidence=result["confidence"],
    )
    db.add(item)
    await db.commit()
    return {"interaction_id": item.id, **result}


@router.post("/analyses/{analysis_id}/ncrb-submit", status_code=202)
async def submit_ncrb(
    analysis_id: UUID, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)],
):
    analysis = await db.get(AIAnalysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    payload = {"analysis_id": str(analysis.id), "module": analysis.module, "result": analysis.result,
               "submitted_at": datetime.now(timezone.utc).isoformat()}
    status, response = "not_configured", {"message": "NCRB connector is not configured; no external submission was sent"}
    if settings.ncrb_webhook_url:
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        signature = hmac.new((settings.integration_webhook_secret or "").encode(), body, hashlib.sha256).hexdigest()
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                external = await client.post(settings.ncrb_webhook_url, content=body, headers={
                    "Content-Type": "application/json", "X-ShieldIQ-Signature": signature,
                    "Idempotency-Key": hashlib.sha256(str(analysis.id).encode()).hexdigest(),
                })
            status = "accepted" if 200 <= external.status_code < 300 else "failed"
            response = {"status_code": external.status_code, "body": external.text[:2000]}
        except httpx.HTTPError as exc:
            status, response = "failed", {"error": str(exc)[:500]}
    submission = GovernmentSubmission(
        analysis_id=analysis.id, status=status, payload=payload, response=response, submitted_by=user.id,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return {"submission_id": submission.id, "status": status, "response": response}
