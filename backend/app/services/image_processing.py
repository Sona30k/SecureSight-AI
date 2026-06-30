import hashlib
import asyncio
from uuid import uuid4

from fastapi import UploadFile

from ai.inference import CurrencyDetectionPipeline
from app.config.settings import settings


class ImageProcessingService:
    allowed_types = {"image/jpeg", "image/png", "image/webp"}

    def __init__(self, model: CurrencyDetectionPipeline | None = None):
        self.model = model or CurrencyDetectionPipeline()

    @staticmethod
    def _verified_suffix(content: bytes) -> str:
        if content.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return ".webp"
        raise ValueError("File contents do not match a supported image format")

    async def process_currency(self, upload: UploadFile) -> tuple[str, dict]:
        if upload.content_type not in self.allowed_types:
            raise ValueError("Only JPEG, PNG and WebP images are accepted")
        content = await upload.read()
        if not content or len(content) > settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"Image must be between 1 byte and {settings.max_upload_mb} MB")
        suffix = self._verified_suffix(content)
        filename = f"{uuid4()}-{hashlib.sha256(content).hexdigest()[:10]}{suffix}"
        target = settings.storage_path / "currency" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_bytes, content)
        prediction = (await self.model.predict(content)).to_dict()
        details = prediction.pop("details")
        return str(target), {
            **prediction,
            **{key: details[key] for key in ("security_thread", "watermark", "serial_valid")},
            "features": details["quality"],
        }
