import re


class NLPAnalyzer:
    KEYWORDS = (
        "digital arrest", "money laundering", "verification account", "transfer immediately",
        "do not inform", "police will arrive", "aadhaar blocked", "arrest warrant",
        "share otp", "stay on this call", "cbi officer", "customs parcel",
    )

    async def analyze(self, text: str) -> dict:
        normalized = re.sub(r"\s+", " ", text.lower())
        keywords = [word for word in self.KEYWORDS if word in normalized]
        coercion = any(x in normalized for x in ("immediately", "do not inform", "stay on this call", "arrest"))
        return {
            "keywords": keywords,
            "coercion_detected": coercion,
            "urgency_score": min(sum(normalized.count(x) for x in ("urgent", "immediately", "now")) * 0.25, 1),
        }
