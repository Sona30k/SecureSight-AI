from typing import Mapping


FRIENDLY_NAMES = {
    "spoof_detected": "Spoofed caller number",
    "keyword_count": "Repeated scam keywords",
    "previous_reports": "Number has previous fraud reports",
    "video_call": "Unsolicited video-call pressure",
    "duration": "Unusually long coercive call",
    "graph_score": "Known fraud device or account connection",
    "location_risk": "High-risk district",
    "counterfeit_score": "Currency security features failed",
    "scam_score": "Scam-language classifier signal",
}


class FeatureExplainer:
    def explain(self, contributions: Mapping[str, float], limit: int = 5) -> list[str]:
        ranked = sorted(contributions.items(), key=lambda item: abs(item[1]), reverse=True)
        return [f"{FRIENDLY_NAMES.get(name, name.replace('_', ' ').title())} ({value:+.1f})" for name, value in ranked[:limit] if value]

    def shap_values(self, model, features):
        try:
            import shap
            return shap.Explainer(model)(features)
        except (ImportError, TypeError, ValueError):
            return None
