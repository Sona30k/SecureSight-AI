import time
from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_db
from app.schemas import AssistantResponse
from app.services import AnalysisRecorder, ChatService

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
    uploads = [item for item in (image, voice, pdf) if item]
    if len(uploads) > 1:
        raise HTTPException(status_code=422, detail="Attach only one file per analysis request")
    attachment = "image" if image else "voice" if voice else "pdf" if pdf else None
    upload = uploads[0] if uploads else None
    content = await upload.read() if upload else None
    if content and len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Attachment exceeds the 25 MB limit")
    try:
        result = await ChatService().chat(text, attachment, content, upload.filename if upload else "")
    except (ValueError, OSError, EOFError) as exc:
        raise HTTPException(status_code=422, detail=f"Unable to process attachment: {exc}")
    analysis = await AnalysisRecorder.record(
        db, module="assistant", input_type=attachment or "text",
        result={**result, "prediction": result["risk_level"], "model_version": "assistant-v1.0"},
        user_id=user.id, started_at=started,
    )
    await db.commit()
    return AssistantResponse(analysis_id=analysis.id, **result)
