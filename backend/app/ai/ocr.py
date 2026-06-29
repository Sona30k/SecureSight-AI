class OCRService:
    async def extract(self, content: bytes) -> dict:
        return {"text": "", "confidence": 0.0, "model": "placeholder-v1"}
