from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CounterfeitCase, FraudReport, User, UserRole
from app.services.chat import ChatService
from app.services.llm import LLMRouter, ProviderName

ContextType = Literal["auto", "currency", "report", "none"]
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class GroundedAssistantService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.router = LLMRouter()

    @staticmethod
    def _infer_context(text: str, requested: ContextType) -> ContextType:
        if requested != "auto":
            return requested
        normalized = text.lower()
        if any(term in normalized for term in (
            "counterfeit detection", "currency detection", "banknote result",
            "explain this note", "explain this detection",
        )):
            return "currency"
        if any(term in normalized for term in (
            "fraud report", "summarize this report", "summarise this report",
            "report summary",
        )):
            return "report"
        return "none"

    async def _currency_context(
        self, user: User, context_id: UUID | None,
    ) -> dict[str, Any] | None:
        if user.role not in {UserRole.police, UserRole.bank, UserRole.administrator}:
            return None
        statement = select(CounterfeitCase)
        if context_id:
            statement = statement.where(CounterfeitCase.id == context_id)
        else:
            statement = statement.order_by(desc(CounterfeitCase.created_at)).limit(1)
        item = await self.db.scalar(statement)
        if not item:
            return None
        return {
            "type": "currency_detection",
            "id": str(item.id),
            "prediction": item.prediction,
            "confidence": item.confidence,
            "authenticity_score": item.authenticity_score,
            "counterfeit_probability": item.counterfeit_probability,
            "denomination": item.denomination,
            "series": item.series,
            "legal_tender": item.legal_tender,
            "currency_status": item.currency_status,
            "serial_number": item.serial_number,
            "serial_duplicate": item.serial_duplicate,
            "security_thread": item.security_thread,
            "watermark": item.watermark,
            "serial_valid": item.serial_valid,
            "explanation": item.explanation,
            "model_provenance": (item.analysis or {}).get("model_provenance", {}),
            "created_at": item.created_at.isoformat(),
        }

    async def _report_context(
        self, user: User, context_id: UUID | None,
    ) -> dict[str, Any] | None:
        statement = select(FraudReport)
        if user.role == UserRole.citizen:
            statement = statement.where(FraudReport.reporter_id == user.id)
        if context_id:
            statement = statement.where(FraudReport.id == context_id)
        else:
            statement = statement.order_by(desc(FraudReport.created_at)).limit(1)
        item = await self.db.scalar(statement)
        if not item:
            return None
        return {
            "type": "fraud_report",
            "id": str(item.id),
            "title": item.title,
            "description": item.description,
            "category": item.category,
            "location": item.location,
            "status": item.status.value,
            "risk_score": item.risk_score,
            "money_involved": item.money_involved,
            "created_at": item.created_at.isoformat(),
        }

    async def context(
        self, text: str, requested: ContextType, context_id: UUID | None, user: User,
    ) -> dict[str, Any] | None:
        resolved = self._infer_context(text, requested)
        if resolved == "currency":
            return await self._currency_context(user, context_id)
        if resolved == "report":
            return await self._report_context(user, context_id)
        return None

    @staticmethod
    def _grounded_fallback(
        local: dict[str, Any], context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not context:
            return local
        if context["type"] == "currency_detection":
            caveat = (
                "This is a screening result, not a legal or forensic-laboratory determination."
                if context["legal_tender"] else
                "The record marks this note as not valid for circulation."
            )
            reasons = "; ".join(context.get("explanation", [])[:4]) or "No explanation was recorded."
            return {
                "response": (
                    f"Detection {context['id'][:8]} classified the {context.get('denomination') or 'banknote'} "
                    f"as {context['prediction']} with an authenticity score of "
                    f"{context['authenticity_score']}/100. {context.get('currency_status') or ''} "
                    f"Recorded reasons: {reasons} {caveat}"
                ).strip(),
                "confidence": min(float(context.get("confidence", 0)) / 100, .99),
                "risk_level": "high" if context["prediction"] in {"Counterfeit", "Suspicious"} else "medium",
                "recommendations": [
                    "Do not circulate a note flagged as suspicious",
                    "Preserve the original note and scan record",
                    "Request verification by an authorized bank or forensic laboratory",
                ],
                "language": local.get("language", "en"),
            }
        return {
            "response": (
                f"Report {context['id'][:8]} — {context['title']}. "
                f"Category: {context['category']}; status: {context['status']}; "
                f"risk score: {context['risk_score']}/100; location: "
                f"{context.get('location') or 'not provided'}. Summary: {context['description']}"
            ),
            "confidence": .95,
            "risk_level": (
                "critical" if context["risk_score"] >= 90 else
                "high" if context["risk_score"] >= 70 else
                "medium" if context["risk_score"] >= 40 else "low"
            ),
            "recommendations": [
                "Verify the report evidence and reporter details",
                "Follow the assigned investigation workflow",
                "Do not infer guilt from an unverified report",
            ],
            "language": local.get("language", "en"),
        }

    async def answer(
        self,
        *,
        text: str,
        user: User,
        provider: ProviderName = "auto",
        context_type: ContextType = "auto",
        context_id: UUID | None = None,
        attachment_type: str | None = None,
        attachment: bytes | None = None,
        filename: str = "",
        language: str = "en",
    ) -> dict[str, Any]:
        local = await ChatService().chat(
            text, attachment_type, attachment, filename, language,
        )
        grounded = await self.context(text, context_type, context_id, user)
        fallback = self._grounded_fallback(local, grounded)
        prompt = self.router.prompt(text, fallback, grounded, language)
        generated, failures = await self.router.generate(provider, prompt)
        if generated is None:
            return {
                **fallback,
                "provider": "rules",
                "model": "sentinel-rules-v2",
                "provider_status": "fallback" if provider != "rules" else "local",
                "grounded_context": [grounded["type"]] if grounded else [],
                "provider_failures": failures,
            }
        answer = generated.answer.model_dump()
        if RISK_RANK[answer["risk_level"]] < RISK_RANK[fallback["risk_level"]]:
            answer["risk_level"] = fallback["risk_level"]
        return {
            **answer,
            "language": language,
            "provider": generated.provider,
            "model": generated.model,
            "provider_status": "live",
            "grounded_context": [grounded["type"]] if grounded else [],
            "provider_failures": failures,
        }
