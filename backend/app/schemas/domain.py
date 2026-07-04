from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ReportStatus


class TelecomSignals(BaseModel):
    network_asserted_number: str | None = Field(default=None, max_length=32)
    attestation: Literal["verified", "partial", "failed", "unavailable"] = "unavailable"
    network_type: Literal["mobile", "landline", "voip", "international", "unknown"] = "unknown"
    origination_country: str | None = Field(default=None, max_length=100)
    sim_age_days: int | None = Field(default=None, ge=0, le=20_000)
    recent_sim_swap: bool = False
    diversion_count: int = Field(default=0, ge=0, le=20)
    carrier_risk_score: int | None = Field(default=None, ge=0, le=100)
    provider_reference: str | None = Field(default=None, max_length=150)


class DigitalArrestRequest(BaseModel):
    caller_number: str = Field(min_length=7, max_length=32, examples=["+919821044221"])
    transcript: str = Field(min_length=5, max_length=50_000)
    duration: int = Field(ge=0, le=86_400)
    video_call: bool = False
    location: str | None = Field(default=None, max_length=150)
    caller_location: str | None = Field(default=None, max_length=150, exclude=True)
    country: str | None = Field(default=None, max_length=100)
    spoof_detected: bool | None = None
    telecom_signals: TelecomSignals | None = None

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
    spoof_score: int = 0
    spoof_reasons: list[str] = Field(default_factory=list)
    voice_forensics: dict[str, Any] | None = None
    external_actions: list[dict[str, Any]] = Field(default_factory=list)


class LiveCallStart(BaseModel):
    caller_number: str = Field(min_length=7, max_length=32)
    video_call: bool = False
    consent_confirmed: bool
    telecom_signals: TelecomSignals | None = None

    @field_validator("consent_confirmed")
    @classmethod
    def consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Recording or analyzing a live call requires explicit consent")
        return value

    @field_validator("caller_number")
    @classmethod
    def live_phone(cls, value: str) -> str:
        normalized = value.strip().replace(" ", "").replace("-", "")
        digits = normalized[1:] if normalized.startswith("+") else normalized
        if not digits.isdigit() or not 7 <= len(digits) <= 15:
            raise ValueError("Caller number must contain 7 to 15 digits")
        return normalized


class LiveTranscriptChunk(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    duration: int = Field(ge=0, le=86_400)
    final: bool = False


class ExternalAlertRequest(BaseModel):
    integration: Literal["mha", "bank"]
    action: Literal["submit_alert", "request_payment_hold"]
    transaction_id: str | None = Field(default=None, max_length=150)
    account_reference: str | None = Field(default=None, max_length=150)
    amount: float | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=1000)


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
    prediction: Literal["Genuine", "Likely Genuine", "Suspicious", "Counterfeit", "Withdrawn Note", "Not Valid Tender"]
    confidence: float
    authenticity_score: int = Field(ge=0, le=100)
    counterfeit_probability: float = Field(ge=0, le=1)
    denomination: str | None
    series: str
    legal_tender: bool
    currency_status: str
    specimen_detected: bool
    serial_number: str | None
    serial_valid: bool
    serial_duplicate: bool
    security_thread: bool
    watermark: bool
    features: dict[str, dict[str, Any]]
    quality: dict[str, float | int | str | bool]
    bounding_box: dict[str, int]
    detected_note: str
    heatmap: str
    explanation: list[str] = Field(default_factory=list)
    model_version: str = "shieldiq-currency-cv-v2"
    explainability_method: str
    spectral_analysis: dict[str, Any] = Field(default_factory=dict)
    model_provenance: dict[str, Any] = Field(default_factory=dict)


class CurrencyDeviceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    device_type: Literal["mobile", "counting_machine", "pos", "scanner"]
    organization: str = Field(min_length=2, max_length=180)


class CurrencyDeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    device_type: str
    organization: str
    active: bool
    last_seen_at: datetime | None
    created_at: datetime


class CurrencyReviewCreate(BaseModel):
    ground_truth: Literal["genuine", "counterfeit"]
    verification_method: Literal["bank_forensic_lab", "police_forensic_lab", "rbi_confirmation", "expert_review"]
    notes: str | None = Field(default=None, max_length=5000)


class CurrencyHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    prediction: str
    confidence: float
    authenticity_score: int
    counterfeit_probability: float
    denomination: str | None
    series: str | None
    legal_tender: bool
    currency_status: str | None
    serial_number: str | None
    serial_duplicate: bool
    location: str | None
    created_at: datetime


class CurrencyStatistics(BaseModel):
    total_notes_scanned: int
    fake_notes_found: int
    detection_accuracy: float | None
    most_counterfeited_denomination: str | None
    denomination_distribution: list[dict[str, int | str]]
    monthly_trends: list[dict[str, int | str]]


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


class GISFeedCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    provider: str = Field(min_length=2, max_length=100)
    district: str | None = Field(default=None, max_length=100)


class GeoJSONIngest(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[dict[str, Any]] = Field(min_length=1, max_length=5000)


class DistrictShareCreate(BaseModel):
    source_district: str = Field(min_length=2, max_length=100)
    target_district: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=5, max_length=5000)
    severity: Literal["low", "medium", "high", "critical"]
    incident_ids: list[str] = Field(default_factory=list, max_length=500)


class SpeechStreamStart(BaseModel):
    language: Literal["en", "hi", "bn", "te", "mr", "ta", "gu", "ur", "kn", "or", "ml", "pa"] = "en"


class SpeechTranscriptChunk(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class ChannelWebhook(BaseModel):
    external_id: str | None = Field(default=None, max_length=150)
    sender_reference: str = Field(min_length=3, max_length=200)
    text: str = Field(min_length=2, max_length=20_000)
    language: Literal["en", "hi", "bn", "te", "mr", "ta", "gu", "ur", "kn", "or", "ml", "pa"] = "en"


class AssistantResponse(BaseModel):
    response: str
    confidence: float
    risk_level: Literal["low", "medium", "high", "critical"]
    recommendations: list[str]
    analysis_id: UUID
    provider: str = "sentinel-rules-v1"
    language: str = "en"


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


class IntelligenceFeedCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    agency_type: Literal["bank", "telecom", "law_enforcement", "fintech", "other"]
    data_type: Literal["bank_transaction", "telecom_cdr", "device_fingerprint", "agency_case"]
    jurisdiction: str = Field(min_length=2, max_length=150)


class GraphEventCreate(BaseModel):
    external_event_id: str = Field(min_length=1, max_length=150)
    event_type: Literal["transaction", "call", "device_observation", "case_link"]
    source_type: Literal["person", "phone", "bank_account", "upi", "device", "ip_address", "case"]
    source_value: str = Field(min_length=1, max_length=250)
    target_type: Literal["person", "phone", "bank_account", "upi", "device", "ip_address", "case"]
    target_value: str = Field(min_length=1, max_length=250)
    relationship: str = Field(min_length=2, max_length=60)
    occurred_at: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphBatchCreate(BaseModel):
    external_batch_id: str = Field(min_length=1, max_length=150)
    events: list[GraphEventCreate] = Field(min_length=1, max_length=5000)


class CustodyEventCreate(BaseModel):
    action: Literal["acquired", "transferred", "examined", "sealed", "unsealed", "presented", "returned"]
    location: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)


class CaseExchangeCreate(BaseModel):
    case_reference: str = Field(min_length=1, max_length=150)
    source_jurisdiction: str = Field(min_length=2, max_length=150)
    target_jurisdiction: str = Field(min_length=2, max_length=150)
    summary: str = Field(min_length=5, max_length=5000)
    entity_references: list[str] = Field(default_factory=list, max_length=1000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=500)
