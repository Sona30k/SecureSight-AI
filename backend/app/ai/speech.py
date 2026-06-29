class SpeechAnalysisService:
    async def analyze(self, audio: bytes) -> dict:
        return {"stress_score": 0.0, "speaker_count": 1, "model": "placeholder-v1"}
