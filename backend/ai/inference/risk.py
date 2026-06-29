from ai.explainability import FeatureExplainer
from ai.utils import Prediction


class HybridRiskEngine:
    weights = {"scam_score": .38, "counterfeit_score": .17, "graph_score": .22, "location_risk": .13, "previous_reports": .10}

    async def predict(self, scam_score: float, counterfeit_score: float, graph_score: float, location_risk: float, previous_reports: int) -> Prediction:
        values = {
            "scam_score": max(0, min(scam_score, 100)),
            "counterfeit_score": max(0, min(counterfeit_score, 100)),
            "graph_score": max(0, min(graph_score, 100)),
            "location_risk": max(0, min(location_risk, 100)),
            "previous_reports": min(max(previous_reports, 0) * 10, 100),
        }
        contributions = {key: round(values[key] * weight, 2) for key, weight in self.weights.items()}
        score = round(sum(contributions.values()))
        level = "Critical" if score >= 80 else "High" if score >= 60 else "Medium" if score >= 30 else "Low"
        return Prediction(
            prediction=level, confidence=96.0, risk_score=score,
            explanation=FeatureExplainer().explain(contributions),
            model_version="hybrid-risk-v1.0", details={"contributions": contributions},
        )
