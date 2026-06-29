import re

SCAM_KEYWORDS = (
    "digital arrest", "cbi", "money laundering", "aadhaar", "do not disconnect",
    "transfer immediately", "verification account", "arrest warrant", "share otp",
    "customs parcel", "police will arrive", "stay on the call", "do not tell anyone",
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s₹@.+-]", " ", text.lower())).strip()


def detect_keywords(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [keyword for keyword in SCAM_KEYWORDS if keyword in normalized]


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
