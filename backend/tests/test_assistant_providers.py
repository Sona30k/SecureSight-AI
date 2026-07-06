import pytest
import json
from uuid import UUID

from app.database import AsyncSessionLocal
from app.models import CounterfeitCase
from app.config import settings
from app.services.llm import GeminiProvider, LlamaProvider, OpenAIProvider, redact_sensitive


class _ProviderResponse:
    def __init__(self, payload):
        self.payload = payload
        self.is_success = True

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _ProviderClient:
    def __init__(self, response, captured):
        self.response = response
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        self.captured.update({"url": url, **kwargs})
        return _ProviderResponse(self.response)


@pytest.mark.asyncio
async def test_assistant_explains_persisted_currency_case(client, auth_headers):
    me = (await client.get("/auth/me", headers=auth_headers)).json()
    async with AsyncSessionLocal() as db:
        case = CounterfeitCase(
            image_path="test-note.png",
            prediction="Suspicious",
            confidence=91,
            authenticity_score=38,
            counterfeit_probability=.62,
            denomination="₹500",
            series="mahatma_gandhi_new_series",
            legal_tender=True,
            currency_status="Current series candidate",
            serial_number="8AB123456",
            serial_duplicate=False,
            security_thread=False,
            watermark=True,
            serial_valid=True,
            explanation=["Security thread was not detected"],
            submitted_by=UUID(me["id"]),
        )
        db.add(case)
        await db.commit()
        await db.refresh(case)

    response = await client.post("/assistant/chat", headers=auth_headers, data={
        "text": "Explain this counterfeit detection.",
        "provider": "rules",
        "context_type": "currency",
        "context_id": str(case.id),
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "rules"
    assert body["provider_status"] == "local"
    assert body["grounded_context"] == ["currency_detection"]
    assert "38/100" in body["response"]
    assert "screening result" in body["response"].lower()


@pytest.mark.asyncio
async def test_assistant_summarizes_authorized_fraud_report(client, auth_headers):
    report = await client.post("/reports", headers=auth_headers, json={
        "title": "UPI collect request campaign",
        "description": "Multiple citizens received urgent collect requests from a linked UPI identifier.",
        "category": "upi_fraud",
        "location": "Delhi",
        "risk_score": 82,
        "money_involved": 125000,
    })
    assert report.status_code == 201
    updated = await client.put(
        f"/reports/{report.json()['id']}", headers=auth_headers, json={"risk_score": 82},
    )
    assert updated.status_code == 200
    response = await client.post("/assistant/chat", headers=auth_headers, data={
        "text": "Summarize this fraud report.",
        "provider": "rules",
        "context_type": "report",
        "context_id": report.json()["id"],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["grounded_context"] == ["fraud_report"]
    assert "UPI collect request campaign" in body["response"]
    assert body["risk_level"] == "high"


@pytest.mark.asyncio
async def test_provider_status_is_explicit(client, auth_headers):
    response = await client.get("/assistant/providers", headers=auth_headers)
    assert response.status_code == 200
    providers = {item["id"]: item for item in response.json()["providers"]}
    assert set(providers) == {"openai", "gemini", "llama", "rules"}
    assert providers["rules"]["configured"] is True


def test_cloud_prompt_redacts_credentials_and_long_financial_identifiers():
    value = redact_sensitive(
        "OTP 123456, PIN: 9988 and account 1234 5678 9012 3456 must never leave the service."
    )
    assert "123456" not in value
    assert "9988" not in value
    assert "1234 5678 9012 3456" not in value
    assert value.count("[REDACTED") >= 3


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["openai", "gemini", "llama"])
async def test_llm_provider_adapters_validate_structured_answers(
    provider_name, monkeypatch,
):
    answer = json.dumps({
        "response": "The message shows high-risk impersonation and payment pressure.",
        "confidence": .91,
        "risk_level": "high",
        "recommendations": ["Do not pay", "Verify through an official channel"],
    })
    if provider_name == "openai":
        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        response = {"output": [{"content": [{"type": "output_text", "text": answer}]}]}
        provider = OpenAIProvider()
    elif provider_name == "gemini":
        monkeypatch.setattr(settings, "gemini_api_key", "test-key")
        response = {"candidates": [{"content": {"parts": [{"text": answer}]}}]}
        provider = GeminiProvider()
    else:
        response = {"message": {"content": answer}}
        provider = LlamaProvider()
    captured = {}
    monkeypatch.setattr(
        "app.services.llm.httpx.AsyncClient",
        lambda **_kwargs: _ProviderClient(response, captured),
    )
    result = await provider.generate("Assess this suspicious message")
    assert result.provider == provider_name
    assert result.answer.risk_level == "high"
    assert result.answer.confidence == .91
    assert captured["json"]
