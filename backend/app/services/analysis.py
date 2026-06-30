import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIAnalysis, AuditLog


class AnalysisRecorder:
    """Single persistence path for predictions and their audit trail."""

    @staticmethod
    async def record(
        db: AsyncSession,
        *,
        module: str,
        input_type: str,
        result: dict[str, Any],
        user_id: UUID,
        started_at: float,
        input_reference: str | None = None,
    ) -> AIAnalysis:
        analysis = AIAnalysis(
            module=module,
            input_type=input_type,
            input_reference=input_reference,
            result=result,
            confidence=float(result.get("confidence", 0)),
            model_version=str(result.get("model_version", "v1.0")),
            processing_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            requested_by=user_id,
        )
        db.add(analysis)
        await db.flush()
        db.add(AuditLog(
            user_id=user_id,
            action="ai.prediction",
            resource=module,
            resource_id=str(analysis.id),
            details={"prediction": result.get("prediction"), "risk_score": result.get("risk_score")},
        ))
        return analysis
