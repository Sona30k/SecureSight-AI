import io
import wave

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageEnhance

from ai.inference.voice import VoiceAnalysisPipeline


def note_bytes(mode: str = "visible") -> bytes:
    image = Image.new("RGB", (960, 400), (142, 121, 157))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 951, 391), outline=(35, 30, 50), width=6)
    draw.rectangle((280, 20, 298, 380), fill=(85, 78, 98))
    draw.ellipse((490, 65, 700, 335), outline=(45, 40, 60), width=10)
    for x in range(35, 930, 22):
        draw.line((x, 30, x + 18, 370), fill=(65 + x % 100, 70, 110), width=2)
    draw.text((50, 50), "RESERVE BANK OF INDIA 100", fill=(20, 20, 25))
    if mode == "uv":
        image = ImageEnhance.Contrast(image.convert("L")).enhance(1.8).convert("RGB")
        ImageDraw.Draw(image).ellipse((90, 90, 125, 125), fill="white")
    elif mode == "ir":
        image = ImageEnhance.Contrast(image.convert("L")).enhance(.55).convert("RGB")
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def test_wav_voice_forensics_returns_auditable_signal_metrics():
    sample_rate = 16_000
    time = np.arange(sample_rate * 2) / sample_rate
    signal = (np.sin(2 * np.pi * 220 * time) * 12_000).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(signal.tobytes())
    result = VoiceAnalysisPipeline.forensic_signals(output.getvalue())
    assert result["available"] is True
    assert result["method"] == "pcm-signal-heuristics-v1"
    assert result["metrics"]["sample_rate"] == sample_rate
    assert "limitation" in result


@pytest.mark.asyncio
async def test_carrier_spoof_signals_and_external_dispatch_state(client, auth_headers):
    response = await client.post("/digital-arrest/analyze", headers=auth_headers, json={
        "caller_number": "+919999900000",
        "transcript": (
            "I am a CBI officer. This is a digital arrest and money laundering warrant. "
            "Do not disconnect. Transfer money immediately and share your OTP or police will arrive."
        ),
        "duration": 720,
        "video_call": True,
        "telecom_signals": {
            "network_asserted_number": "+441234567890",
            "attestation": "failed",
            "network_type": "voip",
            "carrier_risk_score": 91,
            "provider_reference": "carrier-test-1",
        },
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["spoof_detected"] is True
    assert body["spoof_score"] >= 80
    assert body["spoof_reasons"]
    assert body["external_actions"][0]["integration"] == "mha"
    assert body["external_actions"][0]["status"] == "not_configured"


@pytest.mark.asyncio
async def test_consent_gated_live_call_builds_and_finalizes_case(client, auth_headers):
    denied = await client.post("/digital-arrest/live/start", headers=auth_headers, json={
        "caller_number": "+919111222333", "consent_confirmed": False,
    })
    assert denied.status_code == 422
    started = await client.post("/digital-arrest/live/start", headers=auth_headers, json={
        "caller_number": "+919111222333", "consent_confirmed": True, "video_call": True,
        "telecom_signals": {"attestation": "partial", "network_type": "voip"},
    })
    assert started.status_code == 201
    session_id = started.json()["session_id"]
    first = await client.post(
        f"/digital-arrest/live/{session_id}/chunk", headers=auth_headers,
        json={"text": "I am calling from CBI about a money laundering case.", "duration": 25},
    )
    assert first.status_code == 200
    second = await client.post(
        f"/digital-arrest/live/{session_id}/chunk", headers=auth_headers,
        json={"text": "Stay on this call and transfer money immediately.", "duration": 55, "final": True},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "ready"
    finalized = await client.post(
        f"/digital-arrest/live/{session_id}/finalize", headers=auth_headers,
    )
    assert finalized.status_code == 200
    assert finalized.json()["case_id"]
    assert finalized.json()["risk_score"] >= 70


@pytest.mark.asyncio
async def test_multispectral_device_and_human_validation_workflow(client, auth_headers):
    scan = await client.post(
        "/currency/analyze-multispectral", headers=auth_headers,
        data={"location": "Forensic Lab"},
        files={
            "image": ("visible.png", note_bytes(), "image/png"),
            "uv_image": ("uv.png", note_bytes("uv"), "image/png"),
            "infrared_image": ("ir.png", note_bytes("ir"), "image/png"),
        },
    )
    assert scan.status_code == 200, scan.text
    body = scan.json()
    assert body["spectral_analysis"]["capture_type"] == "multispectral"
    assert body["spectral_analysis"]["uv"]["assessed"] is True
    assert body["model_provenance"]["independent_certification"] is False

    review = await client.post(
        f"/currency/{body['case_id']}/review", headers=auth_headers,
        json={"ground_truth": "genuine", "verification_method": "bank_forensic_lab"},
    )
    assert review.status_code == 201
    stats = await client.get("/currency/statistics", headers=auth_headers)
    assert stats.status_code == 200
    assert stats.json()["detection_accuracy"] is not None

    registered = await client.post("/currency/devices", headers=auth_headers, json={
        "name": "Branch Scanner 01", "device_type": "counting_machine",
        "organization": "Test Bank",
    })
    assert registered.status_code == 201
    key = registered.json()["api_key"]
    device_scan = await client.post(
        "/currency/device-scan", headers={
            **auth_headers, "X-Currency-Device-Key": key,
        },
        files={"image": ("note.png", note_bytes(), "image/png")},
    )
    assert device_scan.status_code == 200, device_scan.text
    devices = await client.get("/currency/devices", headers=auth_headers)
    assert devices.status_code == 200
    assert devices.json()[0]["last_seen_at"] is not None

    card = await client.get("/currency/model-card", headers=auth_headers)
    assert card.status_code == 200
    assert card.json()["independent_certification"] is False
