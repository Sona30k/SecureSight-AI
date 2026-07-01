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
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    reports: Mapped[list[FraudReport]] = relationship(back_populates="reporter")


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
    prediction: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    security_thread: Mapped[bool] = mapped_column(Boolean)
    watermark: Mapped[bool] = mapped_column(Boolean)
    serial_valid: Mapped[bool] = mapped_column(Boolean)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    submitted_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


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
