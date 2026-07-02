from __future__ import annotations

import asyncio
from collections import Counter
import io
import re
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageOps
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.config.settings import settings
from app.database import get_db
from app.models import AuditLog, CounterfeitCase, UserRole
from app.realtime import hub
from app.schemas import CurrencyDetectionResponse, CurrencyHistoryItem, CurrencyStatistics
from app.services import AnalysisRecorder, ImageProcessingService

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
        analysis={"quality": result["quality"], "model_version": result["model_version"]},
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
    return CurrencyStatistics(
        total_notes_scanned=int(total), fake_notes_found=int(fake),
        detection_accuracy=None,
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
