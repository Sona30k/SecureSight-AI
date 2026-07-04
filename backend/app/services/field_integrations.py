from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models import IntegrationDispatch


class TelecomSpoofAnalyzer:
    """Score carrier-provided provenance without claiming telecom-network access."""

    def analyze(self, presented_number: str, signals: dict[str, Any] | None) -> dict[str, Any]:
        if not signals:
            return {"score": 0, "detected": False, "reasons": [], "source": "not_provided"}
        score = 0
        reasons: list[str] = []
        asserted = str(signals.get("network_asserted_number") or "").replace(" ", "").replace("-", "")
        if asserted and asserted != presented_number:
            score += 45
            reasons.append("Presented caller ID differs from the network-asserted number")
        attestation = signals.get("attestation", "unavailable")
        if attestation == "failed":
            score += 35
            reasons.append("Carrier identity attestation failed")
        elif attestation == "partial":
            score += 15
            reasons.append("Carrier could only partially attest caller identity")
        if signals.get("network_type") == "voip":
            score += 8
            reasons.append("Call originated through a VoIP route")
        if signals.get("recent_sim_swap"):
            score += 12
            reasons.append("Carrier reports a recent SIM swap")
        if int(signals.get("diversion_count") or 0) >= 2:
            score += 10
            reasons.append("Multiple network diversions were reported")
        carrier_score = signals.get("carrier_risk_score")
        if carrier_score is not None and int(carrier_score) >= 70:
            score += 15
            reasons.append("Carrier reputation service marked the origin high risk")
        score = min(100, score)
        return {
            "score": score, "detected": score >= 40, "reasons": reasons,
            "source": "carrier_metadata", "provider_reference": signals.get("provider_reference"),
        }


class ExternalDispatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def dispatch(
        self, *, case_id: UUID, integration: str, action: str,
        payload: dict[str, Any], user_id: UUID,
    ) -> IntegrationDispatch:
        key_material = json.dumps(
            {"case_id": str(case_id), "integration": integration, "action": action, **payload},
            sort_keys=True, default=str,
        )
        idempotency_key = hashlib.sha256(key_material.encode()).hexdigest()
        existing = await self.db.scalar(select(IntegrationDispatch).where(
            IntegrationDispatch.idempotency_key == idempotency_key
        ))
        if existing:
            return existing
        url = settings.mha_alert_webhook_url if integration == "mha" else settings.bank_hold_webhook_url
        dispatch = IntegrationDispatch(
            case_id=case_id, integration=integration, action=action,
            idempotency_key=idempotency_key, status="not_configured" if not url else "pending",
            request_payload=payload, response_payload={}, attempted_by=user_id,
        )
        self.db.add(dispatch)
        await self.db.flush()
        if not url:
            dispatch.response_payload = {
                "message": f"{integration.upper()} provider is not configured; no external action was sent"
            }
            await self.db.commit()
            return dispatch
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        signature = hmac.new(
            (settings.integration_webhook_secret or "").encode(), body, hashlib.sha256
        ).hexdigest()
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    url, content=body, headers={
                        "Content-Type": "application/json",
                        "X-ShieldIQ-Signature": signature,
                        "Idempotency-Key": idempotency_key,
                    },
                )
            dispatch.status = "accepted" if 200 <= response.status_code < 300 else "failed"
            dispatch.response_payload = {
                "status_code": response.status_code, "body": response.text[:2000],
            }
        except httpx.HTTPError as exc:
            dispatch.status = "failed"
            dispatch.response_payload = {"error": str(exc)[:500]}
        await self.db.commit()
        return dispatch
