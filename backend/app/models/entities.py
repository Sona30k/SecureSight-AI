from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    citizen = "citizen"
    police = "police"
    bank = "bank"
    telecom_provider = "telecom_provider"
    administrator = "administrator"


class AccountStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"
    blocked = "blocked"


class ReportStatus(str, enum.Enum):
    submitted = "submitted"
    verified = "verified"
    assigned = "assigned"
    investigating = "investigating"
    resolved = "resolved"
    rejected = "rejected"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.citizen, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    account_status: Mapped[AccountStatus] = mapped_column(Enum(AccountStatus), default=AccountStatus.pending, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(30), default="English")
    organization: Mapped[str | None] = mapped_column(String(180), nullable=True)
    employee_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    badge_number: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    police_station: Mapped[str | None] = mapped_column(String(180), nullable=True)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    rank: Mapped[str | None] = mapped_column(String(100), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(180), nullable=True)
    profile_picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notification_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=lambda: {"email": True, "sms": True, "push": True})
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    reports: Mapped[list[FraudReport]] = relationship(back_populates="reporter")


class Role(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(250))


class Permission(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(250))


class RolePermission(Base, UUIDMixin):
    __tablename__ = "role_permissions"
    role_name: Mapped[str] = mapped_column(ForeignKey("roles.name", ondelete="CASCADE"), index=True)
    permission_code: Mapped[str] = mapped_column(ForeignKey("permissions.code", ondelete="CASCADE"), index=True)
    __table_args__ = (UniqueConstraint("role_name", "permission_code", name="uq_role_permission"),)


class RefreshToken(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "refresh_tokens"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("user_sessions.id", ondelete="CASCADE"), index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OTP(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "otps"
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    destination: Mapped[str] = mapped_column(String(320), index=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_sessions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    remember_me: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class FraudReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fraud_reports"
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), index=True)
    images: Mapped[list[str]] = mapped_column(JSON, default=list)
    location: Mapped[str | None] = mapped_column(String(250), nullable=True, index=True)
    contact: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.submitted, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    money_involved: Mapped[float] = mapped_column(Float, default=0)
    reporter_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reporter: Mapped[User] = relationship(back_populates="reports")


class CounterfeitCase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "counterfeit_cases"
    image_path: Mapped[str] = mapped_column(String(500))
    corrected_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    heatmap_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prediction: Mapped[str] = mapped_column(String(30), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    authenticity_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    counterfeit_probability: Mapped[float] = mapped_column(Float, default=0)
    denomination: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    series: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    legal_tender: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    currency_status: Mapped[str | None] = mapped_column(String(160), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    serial_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    security_thread: Mapped[bool] = mapped_column(Boolean)
    watermark: Mapped[bool] = mapped_column(Boolean)
    serial_valid: Mapped[bool] = mapped_column(Boolean)
    bounding_box: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    detected_features: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    explanation: Mapped[list[str]] = mapped_column(JSON, default=list)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    submitted_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class CurrencyDevice(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "currency_devices"
    name: Mapped[str] = mapped_column(String(150))
    device_type: Mapped[str] = mapped_column(String(30), index=True)
    organization: Mapped[str] = mapped_column(String(180), index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class CurrencyReview(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "currency_reviews"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("counterfeit_cases.id", ondelete="CASCADE"), unique=True, index=True)
    ground_truth: Mapped[str] = mapped_column(String(20), index=True)
    verification_method: Mapped[str] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class DigitalArrestCase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "digital_arrest_cases"
    caller_number: Mapped[str] = mapped_column(String(32), index=True)
    transcript: Mapped[str] = mapped_column(Text)
    duration: Mapped[int] = mapped_column(Integer)
    video_call: Mapped[bool] = mapped_column(Boolean, default=False)
    caller_location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    scam_probability: Mapped[float] = mapped_column(Float)
    spoof_detected: Mapped[bool] = mapped_column(Boolean)
    threat_level: Mapped[str] = mapped_column(String(20), index=True, default="low")
    detected_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    explanation: Mapped[list[str]] = mapped_column(JSON, default=list)
    manipulation_techniques: Mapped[list[str]] = mapped_column(JSON, default=list)
    psychological_signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    conversation_stages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="analyzed", index=True)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    police_notified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    report_saved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    analyzed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    transcripts: Mapped[list[CallTranscript]] = relationship(back_populates="case", cascade="all, delete-orphan")
    risk_analyses: Mapped[list[RiskAnalysis]] = relationship(back_populates="case", cascade="all, delete-orphan")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="case", cascade="all, delete-orphan")


class LiveCallSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "live_call_sessions"
    caller_number: Mapped[str] = mapped_column(String(32), index=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    video_call: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_confirmed: Mapped[bool] = mapped_column(Boolean)
    telecom_signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    latest_analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    started_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    finalized_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("digital_arrest_cases.id"), nullable=True, index=True)


class IntegrationDispatch(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_dispatches"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("digital_arrest_cases.id", ondelete="CASCADE"), index=True)
    integration: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attempted_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class CallTranscript(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "call_transcripts"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("digital_arrest_cases.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="text")
    language: Mapped[str] = mapped_column(String(20), default="auto")
    suspicious_spans: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    case: Mapped[DigitalArrestCase] = relationship(back_populates="transcripts")
    __table_args__ = (UniqueConstraint("case_id", "sequence", name="uq_call_transcripts_case_sequence"),)


class RiskAnalysis(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "risk_analyses"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("digital_arrest_cases.id", ondelete="CASCADE"), index=True)
    risk_score: Mapped[int] = mapped_column(Integer, index=True)
    scam_probability: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    threat_level: Mapped[str] = mapped_column(String(20), index=True)
    contributions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_version: Mapped[str] = mapped_column(String(80))
    case: Mapped[DigitalArrestCase] = relationship(back_populates="risk_analyses")


class Evidence(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "digital_arrest_evidence"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("digital_arrest_cases.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(30), index=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    case: Mapped[DigitalArrestCase] = relationship(back_populates="evidence")


class CallerHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "caller_histories"
    caller_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    report_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    analysis_count: Mapped[int] = mapped_column(Integer, default=0)
    average_risk: Mapped[float] = mapped_column(Float, default=0)
    reputation_score: Mapped[int] = mapped_column(Integer, default=100, index=True)
    total_victims: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    last_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    spoof_suspicions: Mapped[int] = mapped_column(Integer, default=0)


class Notification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notifications"
    channel: Mapped[str] = mapped_column(String(20), index=True)
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class CrimeLocation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "crime_locations"
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    crime_type: Mapped[str] = mapped_column(String(100), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    reported_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    __table_args__ = (Index("ix_crime_geo", "latitude", "longitude"),)


class GISFeed(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "gis_feeds"
    name: Mapped[str] = mapped_column(String(150))
    provider: Mapped[str] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="geojson_webhook")
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class DistrictIntelligenceShare(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "district_intelligence_shares"
    source_district: Mapped[str] = mapped_column(String(100), index=True)
    target_district: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    incident_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="shared", index=True)
    shared_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpeechStream(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "speech_streams"
    language: Mapped[str] = mapped_column(String(20), default="en")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    latest_forensics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelInteraction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "channel_interactions"
    channel: Mapped[str] = mapped_column(String(20), index=True)
    external_id: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    sender_reference: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(20), default="en")
    request_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="processed")


class GovernmentSubmission(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "government_submissions"
    provider: Mapped[str] = mapped_column(String(30), default="ncrb", index=True)
    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("ai_analyses.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    submitted_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class IntelligenceFeed(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "intelligence_feeds"
    name: Mapped[str] = mapped_column(String(150))
    agency_type: Mapped[str] = mapped_column(String(40), index=True)
    data_type: Mapped[str] = mapped_column(String(40), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(150), index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class GraphIngestionBatch(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "graph_ingestion_batches"
    feed_id: Mapped[UUID] = mapped_column(ForeignKey("intelligence_feeds.id"), index=True)
    external_batch_id: Mapped[str] = mapped_column(String(150))
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    graph_status: Mapped[str] = mapped_column(String(30), default="pending")
    __table_args__ = (UniqueConstraint("feed_id", "external_batch_id", name="uq_graph_feed_batch"),)


class GraphEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "graph_events"
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("graph_ingestion_batches.id"), index=True)
    external_event_id: Mapped[str] = mapped_column(String(150), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    source_value: Mapped[str] = mapped_column(String(250), index=True)
    target_type: Mapped[str] = mapped_column(String(40), index=True)
    target_value: Mapped[str] = mapped_column(String(250), index=True)
    relationship: Mapped[str] = mapped_column(String(60))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class EvidenceItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_items"
    case_reference: Mapped[str] = mapped_column(String(150), index=True)
    title: Mapped[str] = mapped_column(String(200))
    evidence_type: Mapped[str] = mapped_column(String(60), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_reference: Mapped[str] = mapped_column(String(500))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class EvidenceCustodyEvent(Base, UUIDMixin):
    __tablename__ = "evidence_custody_events"
    evidence_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_items.id"), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class CaseExchange(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "case_exchanges"
    case_reference: Mapped[str] = mapped_column(String(150), index=True)
    source_jurisdiction: Mapped[str] = mapped_column(String(150), index=True)
    target_jurisdiction: Mapped[str] = mapped_column(String(150), index=True)
    package_hash: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="shared", index=True)
    shared_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskAlert(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "risk_alerts"
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    risk_score: Mapped[int] = mapped_column(Integer, index=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditLog(Base, UUIDMixin):
    __tablename__ = "audit_logs"
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource: Mapped[str] = mapped_column(String(120))
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class AIAnalysis(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_analyses"
    module: Mapped[str] = mapped_column(String(50), index=True)
    input_type: Mapped[str] = mapped_column(String(30))
    input_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    model_version: Mapped[str] = mapped_column(String(50), default="rules-v1")
    processing_ms: Mapped[int] = mapped_column(Integer, default=0)
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
