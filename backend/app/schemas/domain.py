from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ReportStatus


class DigitalArrestRequest(BaseModel):
    caller_number: str = Field(min_length=7, max_length=32, examples=["+919821044221"])
    transcript: str = Field(min_length=5, max_length=50_000)
    duration: int = Field(ge=0, le=86_400)
    video_call: bool = False
    caller_location: str | None = Field(default=None, max_length=150)
    previous_reports: int = Field(default=0, ge=0, le=10_000)
    spoof_detected: bool | None = None


class DigitalArrestResponse(BaseModel):
    case_id: UUID
    risk_score: int = Field(ge=0, le=100)
    scam_probability: float = Field(ge=0, le=1)
    detected_keywords: list[str]
    spoof_detected: bool
    recommendation: str
    signals: dict[str, Any]


class CurrencyDetectionResponse(BaseModel):
    case_id: UUID
    prediction: Literal["Real", "Fake"]
    confidence: float
    security_thread: bool
    watermark: bool
    serial_valid: bool
    features: dict[str, float | bool]
    explanation: list[str] = Field(default_factory=list)
    model_version: str = "currency-cv-v1.0"


class ReportCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10_000)
    category: str = Field(min_length=2, max_length=80)
    images: list[str] = Field(default_factory=list, max_length=10)
    location: str | None = Field(default=None, max_length=250)
    contact: str | None = Field(default=None, max_length=120)
    money_involved: float = Field(default=0, ge=0)


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=10_000)
    category: str | None = None
    location: str | None = None
    contact: str | None = None
    status: ReportStatus | None = None
    risk_score: int | None = Field(default=None, ge=0, le=100)


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    description: str
    category: str
    images: list[str]
    location: str | None
    contact: str | None
    status: ReportStatus
    risk_score: int
    money_involved: float
    reporter_id: UUID
    created_at: datetime
    updated_at: datetime


class CrimeCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    district: str = Field(min_length=2, max_length=100)
    crime_type: str = Field(min_length=2, max_length=100)
    timestamp: datetime
    description: str | None = Field(default=None, max_length=5000)
    risk_score: int = Field(default=50, ge=0, le=100)


class AssistantResponse(BaseModel):
    response: str
    confidence: float
    risk_level: Literal["low", "medium", "high", "critical"]
    recommendations: list[str]
    analysis_id: UUID
    provider: str = "sentinel-rules-v1"


class NotificationCreate(BaseModel):
    channel: Literal["sms", "email", "push", "whatsapp"]
    recipient: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2, max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphReport(BaseModel):
    case_id: str = Field(min_length=1, max_length=100)
    citizen: str
    phones: list[str] = Field(default_factory=list)
    devices: list[str] = Field(default_factory=list)
    bank_accounts: list[str] = Field(default_factory=list)
    upi_ids: list[str] = Field(default_factory=list)
    ip_addresses: list[str] = Field(default_factory=list)
    risk_score: int = Field(default=50, ge=0, le=100)

    @field_validator("phones", "devices", "bank_accounts", "upi_ids", "ip_addresses")
    @classmethod
    def unique_values(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))
