import json

import pytest

from ai.inference.risk import HybridRiskEngine
from ai.inference.scam import ScamDetectionPipeline
from ai.synthetic_data.generate import crime_geojson, fraud_network, scam_calls


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


@pytest.mark.asyncio
async def test_ai_endpoint(client, auth_headers):
    response = await client.post("/ai/scam-detection", headers=auth_headers, json={
        "caller_number": "+919999900000", "transcript": "CBI digital arrest. Transfer immediately.",
        "duration": 500, "video_call": True, "previous_reports": 4, "spoof_detected": True,
    })
    assert response.status_code == 200
    assert response.json()["model_version"]
