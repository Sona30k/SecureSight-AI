import json

import pytest

from ai.inference.risk import HybridRiskEngine
from ai.inference.scam import ScamDetectionPipeline
from ai.synthetic_data.generate import crime_geojson, digital_arrest_calls, fraud_network, scam_calls
from app.services.chat import ChatService
from app.services.digital_arrest import DigitalArrestRiskEngine


@pytest.mark.asyncio
async def test_scam_pipeline_explains_high_risk_call():
    result = await ScamDetectionPipeline().predict(
        "+919999900000", "I am calling from CBI. Do not disconnect. Transfer immediately to the verification account.",
        720, True, 6, True,
    )
    assert result.prediction == "Scam"
    assert result.risk_score >= 80
    assert "cbi" in result.details["detected_keywords"]
    assert result.explanation


@pytest.mark.asyncio
async def test_hybrid_risk_engine_is_bounded_and_explainable():
    result = await HybridRiskEngine().predict(100, 100, 100, 100, 100)
    assert result.risk_score == 100
    assert result.prediction == "Critical"
    assert len(result.explanation) == 5


def test_synthetic_generators_are_deterministic_and_shaped():
    calls = scam_calls(10, seed=7)
    assert len(calls) == 10
    assert calls == scam_calls(10, seed=7)
    assert len(crime_geojson(12)["features"]) == 12
    graph = fraud_network(30, 5)
    assert len(graph["nodes"]) == 30
    assert graph["edges"]
    digital_calls = digital_arrest_calls()
    assert sum(item["risk_label"] for item in digital_calls) == 500
    assert len(digital_calls) == 700


def test_short_authority_acronyms_match_whole_words_only():
    result = DigitalArrestRiskEngine().analyze(
        transcript="Your Aadhaar is linked to a routine profile update.",
        duration=30, video_call=False, spoof_detected=False, previous_reports=0,
    )
    assert "ed" not in result["authority_impersonation"]
    assert "ED" not in " ".join(result["explanation"])


@pytest.mark.asyncio
async def test_ai_endpoint(client, auth_headers):
    response = await client.post("/ai/scam-detection", headers=auth_headers, json={
        "caller_number": "+919999900000", "transcript": "CBI digital arrest. Transfer immediately.",
        "duration": 500, "video_call": True, "previous_reports": 4, "spoof_detected": True,
    })
    assert response.status_code == 200
    assert response.json()["model_version"]


@pytest.mark.asyncio
async def test_assistant_explains_digital_arrest_without_misclassifying_question():
    result = await ChatService().chat("Explain digital arrest fraud")
    assert result["risk_level"] == "high"
    assert "not a lawful police procedure" in result["response"]
    assert "End the call" in result["recommendations"]


@pytest.mark.asyncio
async def test_assistant_requests_content_for_underspecified_verification():
    result = await ChatService().chat("Is this message fake?")
    assert result["risk_level"] == "low"
    assert "paste the full suspicious message" in result["response"]


@pytest.mark.asyncio
async def test_assistant_api_returns_actionable_recommendations(client, auth_headers):
    response = await client.post(
        "/assistant/chat", headers=auth_headers,
        data={"text": "CBI says I am under digital arrest and must transfer money immediately"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] in {"high", "critical"}
    assert body["recommendations"]
    assert body["analysis_id"]
