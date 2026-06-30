from typing import Any

from pydantic import BaseModel, Field


class ScamRequest(BaseModel):
    caller_number: str
    transcript: str = Field(min_length=3, max_length=50_000)
    duration: int = Field(ge=0, le=86_400)
    video_call: bool = False
    previous_reports: int = Field(default=0, ge=0)
    spoof_detected: bool = False


class RiskRequest(BaseModel):
    scam_score: float = Field(ge=0, le=100)
    counterfeit_score: float = Field(ge=0, le=100)
    graph_score: float = Field(ge=0, le=100)
    location_risk: float = Field(ge=0, le=100)
    previous_reports: int = Field(ge=0)


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=20_000)
    task: str = "scam_message"


class PredictionResponse(BaseModel):
    prediction: str
    confidence: float = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    explanation: list[str]
    model_version: str
    details: dict[str, Any] = Field(default_factory=dict)
