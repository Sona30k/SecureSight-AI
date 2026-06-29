import re

from app.ai import NLPAnalyzer, RiskScoringEngine, RiskSignals


class ScamDetectionService:
    def __init__(self, nlp: NLPAnalyzer | None = None, risk_engine: RiskScoringEngine | None = None):
        self.nlp = nlp or NLPAnalyzer()
        self.risk_engine = risk_engine or RiskScoringEngine()

    async def analyze(self, caller_number: str, transcript: str, duration: int, location: str | None) -> dict:
        nlp_result = await self.nlp.analyze(transcript)
        spoof = bool(re.search(r"(00000|12345|99999)$", caller_number)) or location in {None, "", "Unknown"}
        signals = RiskSignals(
            spoof_detected=spoof,
            suspicious_keywords=len(nlp_result["keywords"]),
            previous_reports=1 if caller_number.endswith(("104", "221")) else 0,
            unusual_location=not location,
            suspicious_transactions=1 if any(x in transcript.lower() for x in ("transfer", "upi", "account")) else 0,
            coercion_detected=nlp_result["coercion_detected"],
        )
        score, contributions = self.risk_engine.score(signals)
        recommendation = (
            "Block immediately and notify police" if score >= 75
            else "End the call and independently verify the caller" if score >= 45
            else "Proceed cautiously; never share credentials or OTPs"
        )
        return {
            "risk_score": score,
            "scam_probability": round(min(0.2 + score / 120, 0.99), 2),
            "detected_keywords": nlp_result["keywords"],
            "spoof_detected": spoof,
            "recommendation": recommendation,
            "signals": {**contributions, "duration_seconds": duration},
        }
