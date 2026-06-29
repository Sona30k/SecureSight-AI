from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass
class Prediction:
    prediction: str
    confidence: float
    risk_score: int
    explanation: list[str]
    model_version: str = "v1.0"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Predictor(Protocol):
    async def predict(self, *args: Any, **kwargs: Any) -> Prediction: ...


class AssistantProvider(Protocol):
    name: str
    async def generate(self, prompt: str, context: dict[str, Any]) -> str: ...
