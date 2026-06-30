from ai.inference import ScamDetectionPipeline


class ScamDetectionService:
    def __init__(self, pipeline: ScamDetectionPipeline | None = None):
        self.pipeline = pipeline or ScamDetectionPipeline()

    async def analyze(
        self, caller_number: str, transcript: str, duration: int, location: str | None,
        previous_reports: int = 0, spoof_detected: bool | None = None, video_call: bool = False,
    ) -> dict:
        spoof = spoof_detected if spoof_detected is not None else location in {None, "", "Unknown"}
        prediction = await self.pipeline.predict(
            caller_number, transcript, duration, video_call, previous_reports, spoof,
        )
        score = prediction.risk_score
        recommendation = (
            "Block immediately and notify police" if score >= 75
            else "End the call and independently verify the caller" if score >= 45
            else "Proceed cautiously; never share credentials or OTPs"
        )
        return {
            "risk_score": score,
            "scam_probability": prediction.details["scam_probability"],
            "detected_keywords": prediction.details["detected_keywords"],
            "spoof_detected": spoof,
            "recommendation": recommendation,
            "signals": prediction.details["features"],
            "explanation": prediction.explanation,
            "model_version": prediction.model_version,
            "confidence": prediction.confidence,
            "prediction": prediction.prediction,
        }
