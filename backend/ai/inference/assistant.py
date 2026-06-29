from abc import ABC, abstractmethod
from typing import Any

from ai.inference.currency import CurrencyDetectionPipeline
from ai.inference.risk import HybridRiskEngine
from ai.inference.scam import ScamDetectionPipeline


class BaseProvider(ABC):
    name = "base"

    @abstractmethod
    async def generate(self, prompt: str, context: dict[str, Any]) -> str: ...


class LocalSafetyProvider(BaseProvider):
    name = "local"

    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        prediction = context.get("prediction", "Unknown")
        risk = context.get("risk_score", 0)
        return f"SentinelX assessment: {prediction} ({risk}/100 risk). Preserve evidence, do not share OTPs or credentials, and verify requests through official channels."


class OpenAIProvider(BaseProvider):
    name = "openai"
    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        raise RuntimeError("Configure the OpenAI provider adapter and credentials before use")


class GeminiProvider(BaseProvider):
    name = "gemini"
    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        raise RuntimeError("Configure the Gemini provider adapter and credentials before use")


class LlamaProvider(BaseProvider):
    name = "llama"
    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        raise RuntimeError("Configure the Llama provider endpoint before use")


class SentinelAssistant:
    def __init__(self, provider: BaseProvider | None = None):
        self.provider = provider or LocalSafetyProvider()

    async def chat(self, message: str, task: str = "scam_message", image: bytes | None = None) -> dict:
        if task in {"currency", "qr"} and image:
            prediction = await CurrencyDetectionPipeline().predict(image)
        elif task == "risk_explanation":
            prediction = await HybridRiskEngine().predict(60, 20, 55, 40, 2)
        else:
            prediction = await ScamDetectionPipeline().predict("unknown", message, 0, False, 0)
        response = await self.provider.generate(message, prediction.to_dict())
        return {**prediction.to_dict(), "response": response, "provider": self.provider.name}
