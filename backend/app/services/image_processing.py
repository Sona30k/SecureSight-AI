import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.ai import CurrencyVisionModel
from app.config.settings import settings


class ImageProcessingService:
    allowed_types = {"image/jpeg", "image/png", "image/webp"}

    def __init__(self, model: CurrencyVisionModel | None = None):
        self.model = model or CurrencyVisionModel()

    async def process_currency(self, upload: UploadFile) -> tuple[str, dict]:
        if upload.content_type not in self.allowed_types:
            raise ValueError("Only JPEG, PNG and WebP images are accepted")
        content = await upload.read()
        if not content or len(content) > settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"Image must be between 1 byte and {settings.max_upload_mb} MB")
        suffix = Path(upload.filename or "note.jpg").suffix.lower()
        filename = f"{uuid4()}-{hashlib.sha256(content).hexdigest()[:10]}{suffix}"
        target = settings.storage_path / "currency" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target), await self.model.predict(content)
