from fastapi import APIRouter, File, Form, Query, UploadFile

from ai.api.schemas import ChatRequest, RiskRequest, ScamRequest
from ai.inference import (
    CurrencyDetectionPipeline, FraudGraphPipeline, HotspotPipeline, HybridRiskEngine,
    OCRPipeline, ScamDetectionPipeline, VoiceAnalysisPipeline,
)
from ai.inference.assistant import SentinelAssistant
from app.auth import CurrentUser

router = APIRouter(prefix="/ai", tags=["AI & Machine Learning"])


@router.post("/scam-detection")
async def scam_detection(payload: ScamRequest, user: CurrentUser):
    result = await ScamDetectionPipeline().predict(**payload.model_dump())
    return result.to_dict()


@router.post("/currency-detection")
async def currency_detection(user: CurrentUser, image: UploadFile = File(...)):
    return (await CurrencyDetectionPipeline().predict(await image.read())).to_dict()


@router.post("/ocr")
async def ocr(user: CurrentUser, image: UploadFile = File(...)):
    return await OCRPipeline().extract(await image.read())


@router.post("/voice-analysis")
async def voice_analysis(
    user: CurrentUser, audio: UploadFile = File(...),
    caller_number: str = Form("unknown"), previous_reports: int = Form(0),
):
    result = await VoiceAnalysisPipeline().analyze(audio.filename or "audio.wav", await audio.read(), caller_number, previous_reports)
    return result.to_dict()


@router.get("/fraud-network")
async def fraud_network(user: CurrentUser):
    return FraudGraphPipeline().analyze()


@router.get("/high-risk-nodes")
async def high_risk_nodes(user: CurrentUser, limit: int = Query(50, ge=1, le=500)):
    analysis = FraudGraphPipeline().analyze()
    return {"items": analysis["high_risk_nodes"][:limit], "model_version": "networkx-graph-v1.0"}


@router.get("/hotspots")
async def hotspots(user: CurrentUser, limit: int = Query(10, ge=1, le=100)):
    return HotspotPipeline().predict(limit)


@router.post("/risk-score")
async def risk_score(payload: RiskRequest, user: CurrentUser):
    return (await HybridRiskEngine().predict(**payload.model_dump())).to_dict()


@router.post("/chat")
async def chat(payload: ChatRequest, user: CurrentUser):
    return await SentinelAssistant().chat(payload.message, payload.task)
