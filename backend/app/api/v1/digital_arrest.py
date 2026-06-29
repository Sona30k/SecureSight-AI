from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_db
from app.models import DigitalArrestCase, RiskAlert
from app.schemas import DigitalArrestRequest, DigitalArrestResponse
from app.services import ScamDetectionService

router = APIRouter(prefix="/digital-arrest", tags=["Digital Arrest Detection"])


@router.post("/analyze", response_model=DigitalArrestResponse)
async def analyze_call(
    payload: DigitalArrestRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await ScamDetectionService().analyze(
        payload.caller_number, payload.transcript, payload.duration, payload.caller_location
    )
    case = DigitalArrestCase(
        **payload.model_dump(), **{k: result[k] for k in (
            "risk_score", "scam_probability", "spoof_detected", "detected_keywords", "recommendation"
        )}, analyzed_by=user.id,
    )
    db.add(case)
    await db.flush()
    if result["risk_score"] >= 75:
        db.add(RiskAlert(
            title=f"High-risk digital arrest call: {payload.caller_number}", severity="critical",
            risk_score=result["risk_score"], source_type="digital_arrest", source_id=str(case.id),
            details={"keywords": result["detected_keywords"], "location": payload.caller_location},
        ))
    await db.commit()
    return DigitalArrestResponse(case_id=case.id, **result)
