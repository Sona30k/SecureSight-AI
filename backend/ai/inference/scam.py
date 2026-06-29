import math
from pathlib import Path

from ai.explainability import FeatureExplainer
from ai.preprocessing import detect_keywords, text_features
from ai.utils import Prediction
from ai.utils.lazy_imports import optional_import


class ScamDetectionPipeline:
    """Hybrid baseline with optional HuggingFace classifier artifact."""

    def __init__(self, model_path: str | Path | None = None):
        self.model_path = Path(model_path) if model_path else None
        self.explainer = FeatureExplainer()
        self._pipeline = None

    def _load_transformer(self):
        if self._pipeline is None and self.model_path and self.model_path.exists():
            transformers = optional_import("transformers")
            if transformers:
                self._pipeline = transformers.pipeline("text-classification", model=str(self.model_path))
        return self._pipeline

    async def predict(
        self, caller_number: str, transcript: str, duration: int,
        video_call: bool, previous_reports: int, spoof_detected: bool = False,
    ) -> Prediction:
        features = text_features(transcript)
        contributions = {
            "spoof_detected": 24.0 if spoof_detected or caller_number.endswith(("00000", "12345")) else 0,
            "keyword_count": min(features["keyword_count"] * 8, 32),
            "previous_reports": min(previous_reports * 6, 18),
            "video_call": 8.0 if video_call else 0,
            "duration": 7.0 if duration > 600 else 3.0 if duration > 240 else 0,
            "urgency": min(features["urgency_count"] * 5, 10),
            "financial_request": min(features["financial_count"] * 4, 12),
        }
        rules_score = min(sum(contributions.values()), 100)
        transformer = self._load_transformer()
        if transformer:
            output = transformer(transcript[:4000])[0]
            ml_probability = float(output["score"]) if output["label"].lower() in {"label_1", "scam"} else 1 - float(output["score"])
            risk_score = round(.55 * rules_score + .45 * ml_probability * 100)
            model = "indicbert-hybrid-v1.0"
        else:
            risk_score = round(rules_score)
            ml_probability = 1 / (1 + math.exp(-(risk_score - 45) / 12))
            model = "explainable-baseline-v1.0"
        return Prediction(
            prediction="Scam" if risk_score >= 55 else "Likely Safe",
            confidence=round(max(ml_probability, 1 - ml_probability) * 100, 2),
            risk_score=risk_score,
            explanation=self.explainer.explain(contributions),
            model_version=model,
            details={"scam_probability": round(ml_probability, 4), "detected_keywords": detect_keywords(transcript), "features": features},
        )
