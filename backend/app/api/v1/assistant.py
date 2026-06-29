import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_db
from app.models import AIAnalysis
from app.schemas import AssistantResponse
from app.services import ChatService

router = APIRouter(prefix="/assistant", tags=["AI Citizen Assistant"])


@router.post("/chat", response_model=AssistantResponse)
async def chat(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    text: str = Form(..., min_length=2, max_length=20_000),
    image: UploadFile | None = File(None),
    voice: UploadFile | None = File(None),
    pdf: UploadFile | None = File(None),
):
    started = time.perf_counter()
    attachment = "image" if image else "voice" if voice else "pdf" if pdf else None
    result = await ChatService().chat(text, attachment)
    analysis = AIAnalysis(
        id=uuid4(), module="assistant", input_type=attachment or "text",
        result={**result, "user_id": str(user.id)}, confidence=result["confidence"],
        processing_ms=int((time.perf_counter() - started) * 1000),
    )
    db.add(analysis)
    await db.commit()
    return AssistantResponse(analysis_id=analysis.id, **result)
