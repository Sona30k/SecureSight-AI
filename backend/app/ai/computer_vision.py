from ai.inference.currency import CurrencyDetectionPipeline


class CurrencyVisionModel:
    """Compatibility adapter backed by the measured-pixel forensic pipeline."""

    def __init__(self) -> None:
        self.pipeline = CurrencyDetectionPipeline()

    async def predict(self, content: bytes) -> dict:
        result = await self.pipeline.analyze(content)
        return {
            "prediction": result["prediction"],
            "confidence": result["confidence"],
            "authenticity_score": result["authenticity_score"],
            "counterfeit_probability": result["counterfeit_probability"],
            "denomination": result["denomination"],
            "security_thread": result["security_thread"],
            "watermark": result["watermark"],
            "serial_valid": result["serial_valid"],
            "features": result["features"],
            "explanation": result["explanation"],
            "model_version": result["model_version"],
        }
