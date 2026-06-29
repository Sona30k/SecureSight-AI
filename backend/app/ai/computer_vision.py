import hashlib


class CurrencyVisionModel:
    """Deterministic development adapter with the same interface as a future CNN."""

    async def predict(self, content: bytes) -> dict:
        digest = hashlib.sha256(content).digest()
        authenticity = digest[0] / 255
        is_real = authenticity >= 0.35
        confidence = round(90 + (digest[1] / 255) * 9.5, 2)
        return {
            "prediction": "Real" if is_real else "Fake",
            "confidence": confidence,
            "security_thread": is_real or digest[2] > 180,
            "watermark": is_real or digest[3] > 210,
            "serial_valid": is_real and digest[4] > 20,
            "features": {
                "microprint": round(digest[5] / 255, 3),
                "intaglio": round(digest[6] / 255, 3),
                "color_shift": round(digest[7] / 255, 3),
            },
        }
