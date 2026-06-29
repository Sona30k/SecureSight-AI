from dataclasses import dataclass


@dataclass(frozen=True)
class RiskSignals:
    spoof_detected: bool = False
    suspicious_keywords: int = 0
    previous_reports: int = 0
    unusual_location: bool = False
    suspicious_transactions: int = 0
    coercion_detected: bool = False


class RiskScoringEngine:
    """Explainable rule engine; weights can later be replaced by a calibrated model."""

    def score(self, signals: RiskSignals) -> tuple[int, dict[str, int]]:
        contributions = {
            "spoof_detection": 25 if signals.spoof_detected else 0,
            "keyword_risk": min(signals.suspicious_keywords * 8, 32),
            "previous_reports": min(signals.previous_reports * 5, 15),
            "location_anomaly": 8 if signals.unusual_location else 0,
            "transaction_risk": min(signals.suspicious_transactions * 5, 10),
            "coercion": 18 if signals.coercion_detected else 0,
        }
        return min(sum(contributions.values()), 100), contributions
