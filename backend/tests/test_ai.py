import json
import io

import pytest
from PIL import Image, ImageDraw

from ai.inference.risk import HybridRiskEngine
from ai.inference.scam import ScamDetectionPipeline
from ai.synthetic_data.generate import crime_geojson, digital_arrest_calls, fraud_network, scam_calls
from app.services.chat import ChatService
from app.services.digital_arrest import DigitalArrestRiskEngine
from ai.inference.currency import (
    CurrencyDetectionPipeline, OpenCVPerspectiveRectifier, TorchForgeryProvider,
)


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


def _synthetic_note_bytes() -> bytes:
    image = Image.new("RGB", (960, 400), (142, 121, 157))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 951, 391), outline=(40, 35, 55), width=5)
    draw.ellipse((480, 70, 690, 330), outline=(55, 48, 70), width=12)
    draw.rectangle((285, 25, 301, 375), fill=(92, 84, 104))
    for x in range(40, 920, 24):
        draw.line((x, 35, x + 15, 365), fill=(80 + x % 90, 70, 115), width=2)
    draw.text((55, 55), "RESERVE BANK OF INDIA 100", fill=(25, 25, 30))
    draw.text((600, 335), "4DF291084", fill=(20, 20, 25))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def test_currency_pipeline_uses_measured_pixels_and_returns_forensics():
    result = CurrencyDetectionPipeline().analyze_sync(_synthetic_note_bytes())
    assert result["denomination"] in {f"₹{value}" for value in ("10", "20", "50", "100", "200", "500", "2000")}
    assert len(result["features"]) == 12
    assert result["detected_note"].startswith("data:image/png;base64,")
    assert result["heatmap"].startswith("data:image/png;base64,")
    assert 0 <= result["authenticity_score"] <= 100
    assert set(result["pipeline_stages"]) == {
        "note_detection", "perspective_correction", "serial_ocr",
        "classification", "explainability",
    }
    assert result["pipeline_stages"]["classification"]["checkpoint_configured"] is False


def test_opencv_applies_four_point_perspective_correction():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (1200, 700), "white")
    draw = ImageDraw.Draw(image)
    corners = [(120, 170), (1070, 90), (1110, 540), (170, 610)]
    draw.polygon(corners, fill=(142, 121, 157), outline=(25, 25, 35), width=12)
    for offset in range(80, 850, 55):
        draw.line((160 + offset, 170, 180 + offset, 570), fill=(55, 48, 80), width=5)
    corrected, applied, method = OpenCVPerspectiveRectifier().rectify(
        image, (80, 60, 1140, 640),
    )
    assert applied is True
    assert method == "opencv_homography"
    assert corrected.size == (960, 400)


def test_efficientnet_checkpoint_produces_prediction_targeted_gradcam(tmp_path):
    torch = pytest.importorskip("torch")
    torchvision = pytest.importorskip("torchvision")
    model = torchvision.models.efficientnet_b0(weights=None)
    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, 2)
    checkpoint = tmp_path / "efficientnet.pt"
    torch.save({
        "state_dict": model.state_dict(),
        "architecture": "efficientnet_b0",
        "class_to_idx": {"counterfeit": 0, "genuine": 1},
    }, checkpoint)
    provider = TorchForgeryProvider(checkpoint, "efficientnet_b0")
    result = provider.predict(Image.new("RGB", (960, 400), (130, 120, 145)))
    assert result is not None
    assert result["architecture"] == "efficientnet_b0"
    assert result["predicted_label"] in {"counterfeit", "genuine"}
    assert result["gradcam"].size == (960, 400)


def test_currency_pipeline_rejects_blurry_flat_image():
    image = Image.new("RGB", (960, 400), (130, 130, 130))
    output = io.BytesIO()
    image.save(output, "PNG")
    with pytest.raises(ValueError, match="blurry"):
        CurrencyDetectionPipeline().analyze_sync(output.getvalue())


def test_single_textured_note_is_not_misclassified_as_multiple_notes():
    canvas = Image.new("RGB", (1200, 700), (238, 238, 235))
    note = Image.new("RGB", (960, 400), (128, 126, 122))
    draw = ImageDraw.Draw(note)
    draw.rectangle((5, 5, 954, 394), outline=(30, 35, 42), width=6)
    for x in range(35, 930, 38):
        draw.rectangle((x, 35, x + 12, 365), fill=(55 + x % 120, 65, 85))
    draw.ellipse((500, 65, 705, 335), outline=(40, 45, 55), width=12)
    canvas.paste(note, (120, 150))
    output = io.BytesIO()
    canvas.save(output, "JPEG", quality=88)
    result = CurrencyDetectionPipeline().analyze_sync(output.getvalue())
    assert result["bounding_box"]["width"] > 700


def test_withdrawn_500_proof_design_is_not_presented_as_active_genuine_tender():
    image = Image.new("RGB", (960, 400), (198, 179, 129))
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 5, 954, 394), outline=(35, 35, 30), width=6)
    draw.ellipse((610, 55, 835, 345), outline=(45, 42, 35), width=12)
    for x in range(30, 930, 24):
        draw.line((x, 25, x + 18, 375), fill=(80 + x % 100, 72, 48), width=2)
    draw.text((105, 175), "PROOF", fill=(180, 20, 25))
    draw.text((620, 25), "000 000000", fill=(180, 20, 25))
    output = io.BytesIO()
    image.save(output, "PNG")
    result = CurrencyDetectionPipeline().analyze_sync(output.getvalue())
    assert result["denomination"] == "₹500"
    assert result["prediction"] == "Not Valid Tender"
    assert result["authenticity_score"] == 0
    assert result["legal_tender"] is False


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
