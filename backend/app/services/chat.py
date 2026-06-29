from app.ai import NLPAnalyzer, RiskScoringEngine, RiskSignals


class ChatService:
    """RAG-ready orchestrator. Replace retrieve() and generate() without changing the API."""

    def __init__(self):
        self.nlp = NLPAnalyzer()
        self.risk = RiskScoringEngine()

    async def chat(self, text: str, attachment_type: str | None = None) -> dict:
        analysis = await self.nlp.analyze(text)
        score, _ = self.risk.score(RiskSignals(
            suspicious_keywords=len(analysis["keywords"]),
            coercion_detected=analysis["coercion_detected"],
            suspicious_transactions=1 if any(x in text.lower() for x in ("upi", "qr", "transfer", "otp")) else 0,
        ))
        level = "critical" if score >= 80 else "high" if score >= 60 else "medium" if score >= 30 else "low"
        if score >= 30:
            response = "This content shows warning signs commonly associated with fraud. Do not click links, transfer money, or share OTPs."
            recommendations = ["Stop engaging with the sender", "Verify using an official phone number", "Preserve evidence and file a report"]
        else:
            response = "I did not find strong fraud indicators, but independently verify the sender before taking financial action."
            recommendations = ["Check the official domain", "Never share OTP or PIN", "Report any request for urgent payment"]
        return {"response": response, "confidence": round(min(.55 + score / 180, .98), 2), "risk_level": level, "recommendations": recommendations}
