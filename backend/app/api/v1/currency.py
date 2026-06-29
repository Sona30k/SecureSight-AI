from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_db
from app.models import CounterfeitCase
from app.schemas import CurrencyDetectionResponse
from app.services import ImageProcessingService

router = APIRouter(prefix="/currency", tags=["Counterfeit Currency"])


@router.post("/detect", response_model=CurrencyDetectionResponse)
async def detect_currency(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    image: UploadFile = File(..., description="JPEG, PNG or WebP currency note image"),
):
    try:
        image_path, result = await ImageProcessingService().process_currency(image)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    case = CounterfeitCase(
        image_path=image_path, prediction=result["prediction"], confidence=result["confidence"],
        security_thread=result["security_thread"], watermark=result["watermark"],
        serial_valid=result["serial_valid"], analysis=result["features"], submitted_by=user.id,
    )
    db.add(case)
    await db.commit()
    return CurrencyDetectionResponse(case_id=case.id, **result)
