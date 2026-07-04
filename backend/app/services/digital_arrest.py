from __future__ import annotations

import asyncio
import hashlib
import math
import re
import textwrap
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.preprocessing import detect_keywords, normalize_text
from app.config.settings import settings
from app.models import (
    AIAnalysis, AuditLog, CallerHistory, CallTranscript, DigitalArrestCase,
    Evidence, Notification, RiskAlert, RiskAnalysis, User,
)
from app.services.field_integrations import TelecomSpoofAnalyzer

AUTHORITY_TERMS = ("cbi", "ed", "income tax", "customs", "police", "court", "rbi", "national security")
THREAT_TERMS = ("arrest", "warrant", "freeze account", "money laundering", "police will arrive", "jail")
FINANCIAL_TERMS = ("transfer money", "transfer immediately", "verification account", "bank account", "upi", "funds")
ISOLATION_TERMS = ("do not disconnect", "don't disconnect", "stay on the call", "stay on this call", "do not tell anyone", "secret")
CREDENTIAL_TERMS = ("otp", "pin", "password", "aadhaar", "cvv")
URGENCY_TERMS = ("immediately", "urgent", "now", "today", "within minutes")


def _hits(text: str, terms: tuple[str, ...]) -> list[str]:
    return [
        term for term in terms
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text)
    ]


def _level(score: int) -> str:
    return "critical" if score >= 90 else "high" if score >= 70 else "medium" if score >= 40 else "low"


def _reputation_label(score: int) -> str:
    return "dangerous" if score < 30 else "suspicious" if score < 60 else "unknown" if score < 85 else "trusted"


class DigitalArrestRiskEngine:
    """Explainable baseline with a stable contract for future transformer fusion."""

    model_version = "shieldiq-digital-arrest-hybrid-v2"

    def analyze(
        self, *, transcript: str, duration: int, video_call: bool,
        spoof_detected: bool, previous_reports: int, spoof_score: int = 0,
        voice_synthetic_score: int = 0,
        transformer_probability: float | None = None,
    ) -> dict[str, Any]:
        cleaned = normalize_text(transcript)
        keywords = detect_keywords(cleaned)
        authority = _hits(cleaned, AUTHORITY_TERMS)
        threats = _hits(cleaned, THREAT_TERMS)
        financial = _hits(cleaned, FINANCIAL_TERMS)
        isolation = _hits(cleaned, ISOLATION_TERMS)
        credentials = _hits(cleaned, CREDENTIAL_TERMS)
        urgency = _hits(cleaned, URGENCY_TERMS)
        contributions = {
            "scam_keywords": min(len(keywords) * 5, 30),
            "authority_impersonation": min(len(authority) * 6, 12),
            "threat_language": min(len(threats) * 8, 16),
            "financial_demand": min(len(financial) * 9, 18),
            "isolation_pressure": min(len(isolation) * 7, 10),
            "credential_request": min(len(credentials) * 5, 10),
            "spoof_detection": min(18, round(max(spoof_score, 70 if spoof_detected else 0) * .18)),
            "synthetic_voice_signal": min(12, round(voice_synthetic_score * .12)),
            "previous_reports": min(previous_reports * 4, 12),
            "video_call": 4 if video_call else 0,
            "conversation_length": 4 if duration >= 600 else 2 if duration >= 240 else 0,
        }
        rules_score = min(100, round(sum(contributions.values())))
        if "digital arrest" in cleaned and threats and financial:
            rules_score = max(rules_score, 82 if video_call else 76)
        elif authority and threats and financial and (isolation or credentials):
            rules_score = max(rules_score, 80 if video_call else 74)
        score = (
            round(rules_score * 0.7 + transformer_probability * 100 * 0.3)
            if transformer_probability is not None else rules_score
        )
        probability = 1 / (1 + math.exp(-(score - 48) / 10))
        confidence = min(99.0, 70 + min(len(keywords), 8) * 3 + (8 if previous_reports else 0) + (5 if spoof_detected else 0))

        groups = [
            (authority, "Authority Claim", "high"), (threats, "Threat", "high"),
            (isolation, "Isolation", "high"), (financial, "Financial Demand", "high"),
            (credentials, "Credential Request", "medium"),
        ]
        stages = [{"stage": "Introduction", "evidence": "Caller initiated conversation", "severity": "low", "order": 1}]
        for terms, stage, severity in groups:
            if terms:
                stages.append({"stage": stage, "evidence": terms[0], "severity": severity, "order": len(stages) + 1})
        if financial and any(term in cleaned for term in ("sent", "paid", "transferred")):
            stages.append({"stage": "Money Transfer", "evidence": "transfer completion language", "severity": "high", "order": len(stages) + 1})

        suspicious_spans: list[dict[str, Any]] = []
        categorized = [
            (authority, "authority", "yellow"), (threats, "threat", "red"),
            (financial, "financial", "red"), (isolation, "isolation", "red"),
            (credentials, "credential", "yellow"), (urgency, "urgency", "yellow"),
        ]
        lower = transcript.lower()
        for terms, category, color in categorized:
            for term in terms:
                for match in re.finditer(re.escape(term), lower):
                    suspicious_spans.append({
                        "start": match.start(), "end": match.end(),
                        "text": transcript[match.start():match.end()],
                        "category": category, "severity": color,
                    })
        suspicious_spans.sort(key=lambda item: (item["start"], -(item["end"] - item["start"])))

        techniques = []
        for condition, technique in (
            (authority, "Authority impersonation"), (threats, "Fear and legal intimidation"),
            (urgency, "Artificial urgency"), (isolation, "Victim isolation"),
            (financial, "Financial coercion"), (credentials, "Credential harvesting"),
        ):
            if condition:
                techniques.append(technique)
        explanations = []
        if authority:
            explanations.append(f"Caller impersonated {', '.join(term.upper() for term in authority[:3])}")
        if threats:
            explanations.append(f"Threat language detected: {', '.join(threats[:3])}")
        if financial:
            explanations.append("Money transfer or account demand detected")
        if previous_reports:
            explanations.append(f"Number has {previous_reports} previous report{'s' if previous_reports != 1 else ''}")
        if spoof_detected:
            explanations.append("Caller ID spoofing is suspected")
        if voice_synthetic_score >= 60:
            explanations.append("Audio signal screening found possible synthetic-voice indicators")
        if not explanations:
            explanations.append("No strong digital-arrest pattern was detected in the supplied conversation")

        recommendation = (
            "End the call immediately. Do not transfer money or share credentials. Block the number, preserve the evidence, contact the claimed agency using an independently verified number, and notify police."
            if score >= 70 else
            "Pause the conversation and independently verify the caller. Do not share Aadhaar, OTP, PIN, passwords, or make a transfer."
            if score >= 40 else
            "No strong scam pattern was found, but remain cautious and never disclose OTPs, PINs, passwords, or transfer money under pressure."
        )
        psychology = {
            "fear": min(1.0, len(threats) * 0.35),
            "urgency": min(1.0, len(urgency) * 0.4),
            "authority": min(1.0, len(authority) * 0.4),
            "isolation": min(1.0, len(isolation) * 0.5),
            "pressure": min(1.0, (len(financial) + len(urgency)) * 0.25),
            "threat": min(1.0, len(threats) * 0.4),
        }
        return {
            "risk_score": score, "confidence": round(confidence, 2),
            "scam_probability": round(probability, 4), "threat_level": _level(score),
            "detected_keywords": keywords, "spoof_detected": spoof_detected,
            "recommendation": recommendation, "explanation": explanations,
            "manipulation_techniques": techniques, "psychological_signals": psychology,
            "authority_impersonation": authority, "financial_threats": financial,
            "conversation_stages": stages, "suspicious_spans": suspicious_spans,
            "signals": contributions, "model_version": self.model_version,
            "prediction": "Scam" if score >= 55 else "Likely Safe",
        }


class DigitalArrestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = DigitalArrestRiskEngine()

    async def reputation(self, caller_number: str) -> CallerHistory:
        history = await self.db.scalar(select(CallerHistory).where(CallerHistory.caller_number == caller_number))
        if history is None:
            history = CallerHistory(caller_number=caller_number)
            self.db.add(history)
            await self.db.flush()
        return history

    async def analyze(
        self, *, caller_number: str, transcript: str, duration: int, video_call: bool,
        location: str | None, country: str | None, spoof_detected: bool | None,
        user: User, source: str = "text", evidence: dict[str, Any] | None = None,
        telecom_signals: dict[str, Any] | None = None,
        voice_forensics: dict[str, Any] | None = None,
    ) -> tuple[DigitalArrestCase, dict[str, Any]]:
        started = datetime.now(timezone.utc)
        history = await self.reputation(caller_number)
        spoof_analysis = TelecomSpoofAnalyzer().analyze(caller_number, telecom_signals)
        inferred_spoof = spoof_detected if spoof_detected is not None else bool(spoof_analysis["detected"])
        spoof_score = max(int(spoof_analysis["score"]), 70 if spoof_detected is True else 0)
        voice_score = int((voice_forensics or {}).get("synthetic_likelihood", 0))
        result = self.engine.analyze(
            transcript=transcript, duration=duration, video_call=video_call,
            spoof_detected=inferred_spoof, previous_reports=history.report_count,
            spoof_score=spoof_score, voice_synthetic_score=voice_score,
        )
        result["spoof_score"] = spoof_score
        result["spoof_reasons"] = spoof_analysis["reasons"]
        result["voice_forensics"] = voice_forensics
        result["external_actions"] = []
        case = DigitalArrestCase(
            caller_number=caller_number, transcript=transcript, duration=duration,
            video_call=video_call, caller_location=location, country=country,
            risk_score=result["risk_score"], confidence=result["confidence"],
            scam_probability=result["scam_probability"], spoof_detected=result["spoof_detected"],
            threat_level=result["threat_level"], detected_keywords=result["detected_keywords"],
            explanation=result["explanation"], manipulation_techniques=result["manipulation_techniques"],
            psychological_signals=result["psychological_signals"],
            conversation_stages=result["conversation_stages"],
            recommendation=result["recommendation"], analyzed_by=user.id,
        )
        self.db.add(case)
        await self.db.flush()
        self.db.add(CallTranscript(
            case_id=case.id, sequence=1, text=transcript, source=source,
            suspicious_spans=result["suspicious_spans"],
        ))
        self.db.add(RiskAnalysis(
            case_id=case.id, risk_score=result["risk_score"],
            scam_probability=result["scam_probability"], confidence=result["confidence"],
            threat_level=result["threat_level"], contributions=result["signals"],
            model_version=result["model_version"],
        ))
        self.db.add(Evidence(
            case_id=case.id, evidence_type="transcript",
            metadata_={
                "source": source, "characters": len(transcript),
                "telecom_signals": telecom_signals or {},
                "spoof_analysis": spoof_analysis,
                "voice_forensics": voice_forensics or {},
            },
        ))
        if evidence:
            self.db.add(Evidence(case_id=case.id, **evidence))

        old_count = history.analysis_count
        history.analysis_count += 1
        history.average_risk = round((history.average_risk * old_count + result["risk_score"]) / history.analysis_count, 2)
        history.reputation_score = max(0, round(100 - history.average_risk * 0.7 - min(history.report_count * 6, 30)))
        history.last_seen = datetime.now(timezone.utc)
        history.last_country = country
        history.spoof_suspicions += int(inferred_spoof)

        if result["risk_score"] >= 70:
            self.db.add(RiskAlert(
                title=f"High-risk digital arrest call: {caller_number}",
                severity="critical" if result["risk_score"] >= 90 else "high",
                risk_score=result["risk_score"], source_type="digital_arrest",
                source_id=str(case.id), details={
                    "keywords": result["detected_keywords"], "location": location, "country": country,
                    "spoof_analysis": spoof_analysis, "voice_forensics": voice_forensics or {},
                },
            ))
        if result["risk_score"] > 90:
            for channel, recipient in (
                ("push", str(user.id)), ("email", user.email),
                ("sms", caller_number), ("push", "police-dashboard"),
            ):
                self.db.add(Notification(
                    channel=channel, recipient=recipient,
                    subject="Critical digital-arrest warning",
                    body=f"A call from {caller_number} scored {result['risk_score']}/100. Immediate action is recommended.",
                    status="queued", metadata_={
                        "case_id": str(case.id), "mock_delivery": channel in {"email", "sms"},
                    },
                ))
        self.db.add(AIAnalysis(
            module="digital_arrest", input_type=source, input_reference=str(case.id),
            result=result, confidence=result["confidence"], model_version=result["model_version"],
            processing_ms=max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000)),
            requested_by=user.id,
        ))
        self.db.add(AuditLog(
            user_id=user.id, action="digital_arrest.analyze",
            resource="digital_arrest_case", resource_id=str(case.id),
            details={"risk_score": result["risk_score"], "caller_number": caller_number},
        ))
        await self.db.commit()
        await self.db.refresh(case)
        result["caller_reputation"] = {
            "caller_number": history.caller_number, "report_count": history.report_count,
            "average_risk": history.average_risk, "reputation_score": history.reputation_score,
            "total_victims": history.total_victims, "last_seen": history.last_seen,
            "label": _reputation_label(history.reputation_score),
        }
        return case, result

    async def save_audio(self, filename: str, content_type: str, content: bytes) -> dict[str, Any]:
        digest = hashlib.sha256(content).hexdigest()
        safe_name = f"{digest[:20]}{Path(filename).suffix.lower()}"
        destination = settings.storage_path / "digital_arrest" / safe_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(destination.write_bytes, content)
        return {
            "evidence_type": "audio", "file_name": Path(filename).name[:255],
            "storage_path": str(destination), "content_type": content_type,
            "sha256": digest, "metadata_": {"size": len(content)},
        }


def investigation_pdf(case: DigitalArrestCase) -> bytes:
    """Generate a dependency-free, valid multi-page PDF evidence summary."""
    lines = [
        "SHIELDIQ DIGITAL ARREST INVESTIGATION REPORT", f"Case ID: {case.id}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Caller: {case.caller_number}",
        f"Location: {case.caller_location or 'Unknown'} / {case.country or 'Unknown'}",
        f"Duration: {case.duration}s | Video: {'Yes' if case.video_call else 'No'}",
        f"Risk: {case.risk_score}/100 | Confidence: {case.confidence:.1f}% | Threat: {case.threat_level.upper()}",
        f"Spoof suspected: {'Yes' if case.spoof_detected else 'No'}", "",
        "DETECTED KEYWORDS", ", ".join(case.detected_keywords) or "None", "",
        "EXPLANATION", *case.explanation, "", "CONVERSATION TIMELINE",
        *[f"{item.get('order')}. {item.get('stage')}: {item.get('evidence')}" for item in case.conversation_stages],
        "", "RECOMMENDATION", case.recommendation, "", "TRANSCRIPT", case.transcript,
    ]
    wrapped = [part for line in lines for part in (textwrap.wrap(str(line), width=92) or [""])]
    pages = [wrapped[index:index + 48] for index in range(0, len(wrapped), 48)] or [[]]
    objects: list[bytes] = []
    font_id = 3 + len(pages) * 2
    page_ids = [3 + index * 2 for index in range(len(pages))]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(f"<< /Type /Pages /Count {len(pages)} /Kids [{kids}] >>".encode())
    for index, page_lines in enumerate(pages):
        page_id, content_id = page_ids[index], page_ids[index] + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        commands = ["BT", "/F1 9 Tf", "45 750 Td", "12 TL"]
        for line in page_lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", "replace").decode("latin-1")
            commands.extend([f"({escaped}) Tj", "T*"])
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)


def keyword_counts(cases: list[DigitalArrestCase]) -> list[dict[str, int | str]]:
    counts = Counter(keyword for case in cases for keyword in case.detected_keywords)
    return [{"keyword": keyword, "count": count} for keyword, count in counts.most_common(8)]
