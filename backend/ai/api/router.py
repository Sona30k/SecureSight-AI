import time
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ai.api.schemas import ChatRequest, PredictionResponse, RiskRequest, ScamRequest
from ai.inference import (
    FraudGraphPipeline, HotspotPipeline, HybridRiskEngine,
    OCRPipeline, ScamDetectionPipeline, VoiceAnalysisPipeline,
)
from ai.inference.assistant import SentinelAssistant
from app.auth import CurrentUser
from app.database import get_db
from app.models import CounterfeitCase, DigitalArrestCase, RiskAlert
from app.realtime import hub
from app.services import AnalysisRecorder, ImageProcessingService

router = APIRouter(prefix="/ai", tags=["AI & Machine Learning"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/scam-detection", response_model=PredictionResponse)
async def scam_detection(payload: ScamRequest, user: CurrentUser, db: DB):
    started = time.perf_counter()
    result = await ScamDetectionPipeline().predict(**payload.model_dump())
    case = DigitalArrestCase(
        caller_number=payload.caller_number, transcript=payload.transcript,
        duration=payload.duration, video_call=payload.video_call, caller_location=None,
        risk_score=result.risk_score, scam_probability=result.details["scam_probability"],
        spoof_detected=payload.spoof_detected, detected_keywords=result.details["detected_keywords"],
        recommendation="Block immediately" if result.risk_score >= 75 else "Verify independently",
        analyzed_by=user.id,
    )
    db.add(case)
    await db.flush()
    if result.risk_score >= 75:
        db.add(RiskAlert(title="High-risk AI scam prediction", severity="critical", risk_score=result.risk_score, source_type="digital_arrest", source_id=str(case.id), details={"caller_number": payload.caller_number}))
    await AnalysisRecorder.record(db, module="scam_detection", input_type="text", result=result.to_dict(), user_id=user.id, started_at=started, input_reference=str(case.id))
    await db.commit()
    await hub.broadcast("dashboard", "scam.analyzed", {"case_id": str(case.id), "risk_score": result.risk_score})
    return result.to_dict()


@router.post("/currency-detection", response_model=PredictionResponse)
async def currency_detection(user: CurrentUser, db: DB, image: UploadFile = File(...)):
    started = time.perf_counter()
    try:
        image_path, normalized = await ImageProcessingService().process_currency(image)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result = {
        "prediction": normalized["prediction"], "confidence": normalized["confidence"],
        "risk_score": normalized["risk_score"], "explanation": normalized["explanation"],
        "model_version": normalized["model_version"],
        "details": {key: normalized[key] for key in ("security_thread", "watermark", "serial_valid", "features")},
    }
    case = CounterfeitCase(
        image_path=image_path, prediction=result["prediction"], confidence=result["confidence"],
        security_thread=normalized["security_thread"], watermark=normalized["watermark"],
        serial_valid=normalized["serial_valid"], analysis=normalized["features"], submitted_by=user.id,
    )
    db.add(case)
    await db.flush()
    await AnalysisRecorder.record(db, module="currency", input_type="image", result=result, user_id=user.id, started_at=started, input_reference=image_path)
    await db.commit()
    await hub.broadcast("dashboard", "currency.analyzed", {"case_id": str(case.id), "prediction": result["prediction"]})
    return result


@router.post("/ocr")
async def ocr(user: CurrentUser, db: DB, image: UploadFile = File(...)):
    started = time.perf_counter()
    content = await image.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds the 10 MB limit")
    try:
        ImageProcessingService._verified_suffix(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result = await OCRPipeline().extract(content)
    await AnalysisRecorder.record(db, module="ocr", input_type="image", result=result, user_id=user.id, started_at=started)
    await db.commit()
    return result


@router.post("/voice-analysis")
async def voice_analysis(
    user: CurrentUser, db: DB, audio: UploadFile = File(...),
    caller_number: str = Form("unknown"), previous_reports: int = Form(0),
):
    started = time.perf_counter()
    try:
        result = await VoiceAnalysisPipeline().analyze(audio.filename or "audio.wav", await audio.read(), caller_number, previous_reports)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await AnalysisRecorder.record(db, module="voice", input_type="audio", result=result.to_dict(), user_id=user.id, started_at=started)
    await db.commit()
    return result.to_dict()


@router.get("/fraud-network")
async def fraud_network(user: CurrentUser, db: DB):
    started = time.perf_counter()
    result = FraudGraphPipeline().analyze()
    await AnalysisRecorder.record(db, module="fraud_graph", input_type="graph", result={"prediction": "Graph analyzed", "confidence": 100, "model_version": "networkx-v1.0", "statistics": result["statistics"]}, user_id=user.id, started_at=started)
    await db.commit()
    return result


@router.get("/high-risk-nodes")
async def high_risk_nodes(user: CurrentUser, limit: int = Query(50, ge=1, le=500)):
    analysis = FraudGraphPipeline().analyze()
    return {"items": analysis["high_risk_nodes"][:limit], "model_version": "networkx-graph-v1.0"}


@router.get("/hotspots")
async def hotspots(user: CurrentUser, db: DB, limit: int = Query(10, ge=1, le=100)):
    started = time.perf_counter()
    result = HotspotPipeline().predict(limit)
    await AnalysisRecorder.record(db, module="hotspots", input_type="geojson", result=result, user_id=user.id, started_at=started)
    await db.commit()
    return result


@router.post("/risk-score", response_model=PredictionResponse)
async def risk_score(payload: RiskRequest, user: CurrentUser, db: DB):
    started = time.perf_counter()
    result = (await HybridRiskEngine().predict(**payload.model_dump())).to_dict()
    await AnalysisRecorder.record(db, module="risk", input_type="structured", result=result, user_id=user.id, started_at=started)
    await db.commit()
    return result


@router.post("/chat")
async def chat(payload: ChatRequest, user: CurrentUser, db: DB):
    started = time.perf_counter()
    result = await SentinelAssistant().chat(payload.message, payload.task)
    await AnalysisRecorder.record(db, module="assistant", input_type="text", result=result, user_id=user.id, started_at=started)
    await db.commit()
    return result
