from __future__ import annotations

import asyncio
from collections import Counter
import io
import re
import textwrap
import time
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageOps
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.auth.security import hash_token
from app.config.settings import settings
from app.database import get_db
from app.models import AuditLog, CounterfeitCase, CurrencyDevice, CurrencyReview, UserRole
from app.realtime import hub
from app.schemas import (
    CurrencyDetectionResponse, CurrencyDeviceCreate, CurrencyDeviceRead,
    CurrencyHistoryItem, CurrencyReviewCreate, CurrencyStatistics,
)
from app.services import AnalysisRecorder, ImageProcessingService, SpectralCurrencyAnalyzer

router = APIRouter(prefix="/currency", tags=["Counterfeit Currency"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
TOKEN_PATTERN = re.compile(r"^[a-f0-9-]{20,80}\.(?:jpg|png|webp)$")


def _scope(statement, user):
    if user.role == UserRole.citizen:
        return statement.where(CounterfeitCase.submitted_by == user.id)
    return statement


@router.post("/upload", status_code=201)
async def upload_currency(user: CurrentUser, image: Annotated[UploadFile, File()]):
    try:
        path, content = await ImageProcessingService().store_currency(image)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "upload_token": Path(path).name, "file_name": Path(image.filename or "note").name,
        "size": len(content), "status": "validated",
    }


async def _analyze_and_store(
    image: UploadFile, location: str | None, user, db: AsyncSession,
) -> CurrencyDetectionResponse:
    started = time.perf_counter()
    try:
        image_path, result = await ImageProcessingService().process_currency(image)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    duplicate = False
    if result["serial_number"]:
        duplicate = bool(await db.scalar(select(CounterfeitCase.id).where(
            CounterfeitCase.serial_number == result["serial_number"],
        ).limit(1)))
    if duplicate:
        result["authenticity_score"] = max(0, result["authenticity_score"] - 25)
        result["counterfeit_probability"] = round(1 - result["authenticity_score"] / 100, 4)
        result["prediction"] = "Counterfeit" if result["authenticity_score"] < 40 else "Suspicious"
        result["explanation"].insert(0, "Serial number was previously scanned and is flagged as a duplicate")
    result["serial_duplicate"] = duplicate
    result["spectral_analysis"] = {}
    result["model_provenance"] = {
        "pipeline": result["model_version"],
        "resnet_checkpoint_configured": bool(settings.currency_resnet_path),
        "yolo_checkpoint_configured": bool(settings.currency_yolo_path),
        "ocr_available": bool(result["features"]["serial_number"].get("ocr_available")),
        "independent_certification": False,
        "validation_status": "site_checkpoint" if settings.currency_resnet_path else "measured-feature baseline; not independently certified",
    }
    case = CounterfeitCase(
        image_path=image_path, corrected_image_path=result["corrected_image_path"],
        heatmap_path=result["heatmap_path"], prediction=result["prediction"],
        confidence=result["confidence"], authenticity_score=result["authenticity_score"],
        counterfeit_probability=result["counterfeit_probability"],
        denomination=result["denomination"], series=result["series"],
        legal_tender=result["legal_tender"], currency_status=result["currency_status"],
        serial_number=result["serial_number"],
        serial_duplicate=duplicate, location=location,
        security_thread=result["security_thread"], watermark=result["watermark"],
        serial_valid=result["serial_valid"], bounding_box=result["bounding_box"],
        detected_features=result["features"], explanation=result["explanation"],
        analysis={
            "quality": result["quality"], "model_version": result["model_version"],
            "model_provenance": result["model_provenance"], "spectral_analysis": {},
        },
        submitted_by=user.id,
    )
    db.add(case)
    await db.flush()
    record_result = {
        key: value for key, value in result.items()
        if key not in {"detected_note", "heatmap", "corrected_image_path", "heatmap_path"}
    }
    await AnalysisRecorder.record(
        db, module="currency", input_type="image", result=record_result,
        user_id=user.id, started_at=started, input_reference=str(case.id),
    )
    db.add(AuditLog(
        user_id=user.id, action="currency.analyze", resource="counterfeit_case",
        resource_id=str(case.id), details={
            "prediction": result["prediction"], "denomination": result["denomination"],
            "authenticity_score": result["authenticity_score"],
        },
    ))
    await db.commit()
    await hub.broadcast("dashboard", "currency.analyzed", {
        "case_id": str(case.id), "prediction": result["prediction"],
        "denomination": result["denomination"],
    })
    return CurrencyDetectionResponse(case_id=case.id, **result)


@router.post("/analyze", response_model=CurrencyDetectionResponse)
async def analyze_currency(
    user: CurrentUser, db: DbSession,
    image: Annotated[UploadFile, File(description="Single Indian currency note image")],
    location: Annotated[str | None, Form(max_length=150)] = None,
):
    return await _analyze_and_store(image, location, user, db)


@router.post("/detect", response_model=CurrencyDetectionResponse, include_in_schema=False)
async def detect_currency(
    user: CurrentUser, db: DbSession,
    image: Annotated[UploadFile, File(description="Single Indian currency note image")],
    location: Annotated[str | None, Form(max_length=150)] = None,
):
    return await _analyze_and_store(image, location, user, db)


@router.post("/analyze-multispectral", response_model=CurrencyDetectionResponse)
async def analyze_multispectral(
    user: CurrentUser, db: DbSession,
    image: Annotated[UploadFile, File(description="Visible-light image")],
    uv_image: Annotated[UploadFile | None, File(description="Physical UV capture")] = None,
    infrared_image: Annotated[UploadFile | None, File(description="Physical infrared capture")] = None,
    location: Annotated[str | None, Form(max_length=150)] = None,
):
    result = await _analyze_and_store(image, location, user, db)
    case = await db.get(CounterfeitCase, result.case_id)
    assert case is not None
    visible = await asyncio.to_thread(Path(case.image_path).read_bytes)
    spectral_paths: dict[str, str] = {}
    spectral_content: dict[str, bytes | None] = {"uv": None, "infrared": None}
    for name, upload in (("uv", uv_image), ("infrared", infrared_image)):
        if upload:
            try:
                path, content = await ImageProcessingService().store_currency(upload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"{name.title()} capture: {exc}") from exc
            spectral_paths[name], spectral_content[name] = path, content
    try:
        spectral = await asyncio.to_thread(
            SpectralCurrencyAnalyzer().analyze,
            visible, spectral_content["uv"], spectral_content["infrared"],
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=f"Unable to analyze spectral captures: {exc}") from exc
    case.analysis = {
        **case.analysis, "spectral_analysis": spectral, "spectral_paths": spectral_paths,
    }
    db.add(AuditLog(
        user_id=user.id, action="currency.multispectral_analyze",
        resource="counterfeit_case", resource_id=str(case.id),
        details={"channels": list(spectral_paths)},
    ))
    await db.commit()
    return result.model_copy(update={"spectral_analysis": spectral})


@router.get("/model-card")
async def currency_model_card(user: CurrentUser):
    return {
        "pipeline": "shieldiq-currency-cv-v2",
        "purpose": "Screening and decision support for Indian banknote images",
        "resnet_checkpoint_configured": bool(settings.currency_resnet_path),
        "yolo_checkpoint_configured": bool(settings.currency_yolo_path),
        "visible_baseline": "Measured image regions and quality checks",
        "spectral_support": ["physical UV capture", "physical infrared capture"],
        "independent_certification": False,
        "limitations": [
            "A visible image cannot reproduce physical UV or infrared behavior",
            "Results require trained-checkpoint validation and expert confirmation before enforcement action",
        ],
    }


def _device_roles(user) -> None:
    if user.role not in {UserRole.bank, UserRole.police, UserRole.administrator}:
        raise HTTPException(status_code=403, detail="Only authorized institutions can manage currency devices")


@router.post("/devices", status_code=201)
async def register_currency_device(payload: CurrencyDeviceCreate, user: CurrentUser, db: DbSession):
    _device_roles(user)
    api_key = secrets.token_urlsafe(32)
    device = CurrencyDevice(
        name=payload.name, device_type=payload.device_type, organization=payload.organization,
        api_key_hash=hash_token(api_key), registered_by=user.id,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return {"device": CurrencyDeviceRead.model_validate(device), "api_key": api_key}


@router.get("/devices", response_model=list[CurrencyDeviceRead])
async def currency_devices(user: CurrentUser, db: DbSession):
    _device_roles(user)
    return list((await db.scalars(
        select(CurrencyDevice).order_by(CurrencyDevice.created_at.desc()).limit(500)
    )).all())


@router.post("/device-scan", response_model=CurrencyDetectionResponse)
async def device_scan(
    user: CurrentUser, db: DbSession,
    image: Annotated[UploadFile, File()],
    x_currency_device_key: Annotated[str, Header(min_length=20)],
    location: Annotated[str | None, Form(max_length=150)] = None,
):
    _device_roles(user)
    device = await db.scalar(select(CurrencyDevice).where(
        CurrencyDevice.api_key_hash == hash_token(x_currency_device_key),
        CurrencyDevice.active.is_(True),
    ))
    if not device:
        raise HTTPException(status_code=401, detail="Invalid or inactive currency device key")
    device.last_seen_at = datetime.now(timezone.utc)
    result = await _analyze_and_store(image, location or device.organization, user, db)
    case = await db.get(CounterfeitCase, result.case_id)
    if case:
        case.analysis = {**case.analysis, "device_id": str(device.id), "device_type": device.device_type}
        await db.commit()
    return result


@router.post("/batch-analyze")
async def batch_analyze(
    user: CurrentUser, db: DbSession,
    images: Annotated[list[UploadFile], File(min_length=1, max_length=20)],
    location: Annotated[str | None, Form(max_length=150)] = None,
):
    _device_roles(user)
    results = []
    for image in images:
        try:
            value = await _analyze_and_store(image, location, user, db)
            results.append({"file_name": image.filename, "status": "analyzed", "result": value.model_dump()})
        except HTTPException as exc:
            results.append({"file_name": image.filename, "status": "rejected", "error": exc.detail})
    return {"total": len(images), "analyzed": sum(item["status"] == "analyzed" for item in results), "items": results}


@router.post("/{case_id}/review", status_code=201)
async def review_currency_case(
    case_id: UUID, payload: CurrencyReviewCreate, user: CurrentUser, db: DbSession,
):
    _device_roles(user)
    case = await db.get(CounterfeitCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Currency case not found")
    review = await db.scalar(select(CurrencyReview).where(CurrencyReview.case_id == case_id))
    if review:
        review.ground_truth, review.verification_method = payload.ground_truth, payload.verification_method
        review.notes, review.reviewed_by = payload.notes, user.id
    else:
        review = CurrencyReview(
            case_id=case_id, ground_truth=payload.ground_truth,
            verification_method=payload.verification_method,
            notes=payload.notes, reviewed_by=user.id,
        )
        db.add(review)
    await db.commit()
    return {"case_id": case_id, "ground_truth": review.ground_truth, "status": "reviewed"}


@router.get("/history", response_model=list[CurrencyHistoryItem])
async def currency_history(
    user: CurrentUser, db: DbSession,
    denomination: str | None = Query(default=None, max_length=10),
    limit: int = Query(default=50, ge=1, le=200),
):
    statement = _scope(select(CounterfeitCase), user)
    if denomination:
        statement = statement.where(CounterfeitCase.denomination == denomination)
    return list((await db.scalars(
        statement.order_by(CounterfeitCase.created_at.desc()).limit(limit)
    )).all())


@router.get("/statistics", response_model=CurrencyStatistics)
async def currency_statistics(user: CurrentUser, db: DbSession):
    filters = [CounterfeitCase.submitted_by == user.id] if user.role == UserRole.citizen else []
    filters.append(CounterfeitCase.prediction != "Legacy Unverified")
    total, fake = (await db.execute(select(
        func.count(CounterfeitCase.id),
        func.coalesce(func.sum(
            (CounterfeitCase.prediction.in_(("Suspicious", "Counterfeit"))).cast(Integer)
        ), 0),
    ).where(*filters))).one()
    denominations = (await db.execute(
        select(CounterfeitCase.denomination, func.count(CounterfeitCase.id))
        .where(CounterfeitCase.denomination.is_not(None), *filters)
        .group_by(CounterfeitCase.denomination).order_by(func.count(CounterfeitCase.id).desc())
    )).all()
    fake_denominations = (await db.execute(
        select(CounterfeitCase.denomination, func.count(CounterfeitCase.id))
        .where(CounterfeitCase.prediction.in_(("Suspicious", "Counterfeit")), *filters)
        .group_by(CounterfeitCase.denomination).order_by(func.count(CounterfeitCase.id).desc())
    )).all()
    month_counts = Counter(
        timestamp.strftime("%Y-%m")
        for timestamp in (await db.scalars(select(CounterfeitCase.created_at).where(*filters))).all()
    )
    reviewed = (await db.execute(
        select(CounterfeitCase.prediction, CurrencyReview.ground_truth)
        .join(CurrencyReview, CurrencyReview.case_id == CounterfeitCase.id)
        .where(*filters)
    )).all()
    correct = sum(
        (truth == "counterfeit") == (prediction in {"Suspicious", "Counterfeit"})
        for prediction, truth in reviewed
    )
    return CurrencyStatistics(
        total_notes_scanned=int(total), fake_notes_found=int(fake),
        detection_accuracy=round(correct / len(reviewed) * 100, 2) if reviewed else None,
        most_counterfeited_denomination=fake_denominations[0][0] if fake_denominations else None,
        denomination_distribution=[
            {"denomination": name or "Unknown", "count": count} for name, count in denominations
        ],
        monthly_trends=[
            {"month": month, "count": count} for month, count in sorted(month_counts.items())
        ],
    )


def _report_bytes(item: CounterfeitCase) -> bytes:
    canvas = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(canvas)
    y = 70
    lines = [
        "SHIELDIQ COUNTERFEIT CURRENCY FORENSIC REPORT", "",
        f"Case ID: {item.id}", f"Timestamp: {item.created_at.isoformat()}",
        f"Prediction: {item.prediction}", f"Confidence: {item.confidence:.1f}%",
        f"Authenticity score: {item.authenticity_score}/100",
        f"Denomination: {item.denomination or 'Not determined'}",
        f"Series: {item.series or 'Not determined'}",
        f"Legal tender: {'Yes' if item.legal_tender else 'No'}",
        f"Circulation status: {item.currency_status or 'Not determined'}",
        f"Serial number: {item.serial_number or 'Not available'}",
        f"Duplicate serial: {'Yes' if item.serial_duplicate else 'No'}", "",
    ]
    for line in lines:
        draw.text((70, y), line, fill="black")
        y += 30
    for path, title in ((item.corrected_image_path, "Detected note"), (item.heatmap_path, "Forensic saliency")):
        if path and Path(path).exists():
            draw.text((70, y), title, fill="black")
            y += 28
            image = Image.open(path).convert("RGB")
            image.thumbnail((1080, 420))
            canvas.paste(image, (70, y))
            y += image.height + 35
    for explanation in item.explanation:
        for line in textwrap.wrap(f"• {explanation}", 110):
            draw.text((70, y), line, fill="black")
            y += 25
    output = io.BytesIO()
    canvas.save(output, "PDF", resolution=150)
    return output.getvalue()


@router.get("/{case_id}/report.pdf")
async def currency_report(case_id: UUID, user: CurrentUser, db: DbSession):
    item = await db.scalar(_scope(select(CounterfeitCase).where(CounterfeitCase.id == case_id), user))
    if item is None:
        raise HTTPException(status_code=404, detail="Currency case not found")
    pdf = await asyncio.to_thread(_report_bytes, item)
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="currency-{case_id}.pdf"'},
    )
