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
    location: str | None = Field(default=None, max_length=150)
    caller_location: str | None = Field(default=None, max_length=150, exclude=True)
    country: str | None = Field(default=None, max_length=100)
    spoof_detected: bool | None = None

    @field_validator("caller_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.strip().replace(" ", "").replace("-", "")
        if normalized.startswith("+"):
            digits = normalized[1:]
        else:
            digits = normalized
        if not digits.isdigit() or not 7 <= len(digits) <= 15:
            raise ValueError("Caller number must contain 7 to 15 digits")
        return normalized

    @property
    def resolved_location(self) -> str | None:
        return self.location or self.caller_location


class ConversationStage(BaseModel):
    stage: Literal["Introduction", "Authority Claim", "Threat", "Isolation", "Financial Demand", "Money Transfer", "Credential Request"]
    evidence: str
    severity: Literal["low", "medium", "high"]
    order: int


class CallerReputationRead(BaseModel):
    caller_number: str
    report_count: int
    average_risk: float
    reputation_score: int
    total_victims: int
    last_seen: datetime | None = None
    label: str


class DigitalArrestResponse(BaseModel):
    case_id: UUID
    risk_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    scam_probability: float = Field(ge=0, le=1)
    threat_level: Literal["low", "medium", "high", "critical"]
    detected_keywords: list[str]
    spoof_detected: bool
    recommendation: str
    explanation: list[str]
    manipulation_techniques: list[str]
    psychological_signals: dict[str, float]
    authority_impersonation: list[str]
    financial_threats: list[str]
    conversation_stages: list[ConversationStage]
    suspicious_spans: list[dict[str, Any]]
    caller_reputation: CallerReputationRead
    signals: dict[str, Any]
    model_version: str


class DigitalArrestReportCreate(BaseModel):
    case_id: UUID
    notes: str | None = Field(default=None, max_length=5000)
    total_victims: int = Field(default=1, ge=0, le=100_000)
    bank_accounts: list[str] = Field(default_factory=list, max_length=20)
    device_ids: list[str] = Field(default_factory=list, max_length=20)


class DigitalArrestAction(BaseModel):
    action: Literal["block", "notify_police", "save_report"]
    notes: str | None = Field(default=None, max_length=1000)


class DigitalArrestHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    caller_number: str
    duration: int
    country: str | None
    caller_location: str | None
    risk_score: int
    confidence: float
    scam_probability: float
    threat_level: str
    spoof_detected: bool
    detected_keywords: list[str]
    status: str
    blocked: bool
    police_notified: bool
    report_saved: bool
    created_at: datetime


class DigitalArrestDashboard(BaseModel):
    today_scam_calls: int
    blocked_calls: int
    average_risk: float
    high_risk_numbers: int
    total_cases: int
    risk_distribution: dict[str, int]
    common_keywords: list[dict[str, int | str]]
    top_numbers: list[dict[str, int | float | str]]
    daily_cases: list[dict[str, int | str]]


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
