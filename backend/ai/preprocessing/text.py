import re

SCAM_KEYWORDS = (
    "digital arrest", "cbi", "ed", "income tax", "money laundering", "aadhaar",
    "arrest", "national security", "do not disconnect", "don't disconnect",
    "transfer money", "transfer immediately", "bank account", "freeze account",
    "verification account", "arrest warrant", "otp", "share otp", "customs",
    "customs parcel", "police verification", "police will arrive", "video call",
    "stay on the call", "do not tell anyone",
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s₹@.+-]", " ", text.lower())).strip()


def detect_keywords(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [
        keyword for keyword in SCAM_KEYWORDS
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
    ]


def text_features(text: str) -> dict[str, float]:
    normalized = normalize_text(text)
    keywords = detect_keywords(normalized)
    return {
        "keyword_count": float(len(keywords)),
        "urgency_count": float(sum(normalized.count(x) for x in ("urgent", "immediately", "now", "today"))),
        "authority_count": float(sum(normalized.count(x) for x in ("cbi", "police", "court", "customs", "rbi"))),
        "financial_count": float(sum(normalized.count(x) for x in ("transfer", "upi", "account", "otp", "funds"))),
        "text_length": float(len(normalized)),
    }
