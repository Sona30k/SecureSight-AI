from __future__ import annotations

import asyncio
import base64
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from ai.utils.lazy_imports import optional_import

SUPPORTED_DENOMINATIONS = ("10", "20", "50", "100", "200", "500", "2000")
DENOMINATION_COLORS = {
    "10": np.array([126, 91, 66]), "20": np.array([172, 155, 84]),
    "50": np.array([74, 135, 166]), "100": np.array([142, 121, 157]),
    "200": np.array([198, 151, 57]), "500": np.array([126, 127, 124]),
    "2000": np.array([157, 84, 135]),
}
LEGACY_SERIES_COLORS = {
    "pre_2016_500": ("500", np.array([198, 179, 129])),
}
SERIAL_PATTERN = re.compile(r"(?<![A-Z0-9])([0-9A-Z]{1,3}\s?\d{6})(?![A-Z0-9])")


@dataclass
class PreparedNote:
    original: Image.Image
    note: Image.Image
    bounding_box: dict[str, int]
    quality: dict[str, float | int | str | bool]
    color_mean: np.ndarray


class YOLOBoundaryProvider:
    """Optional YOLOv8 checkpoint adapter; CV contour detection remains the safe fallback."""

    def __init__(self, path: str | Path | None):
        self.model = None
        if path and Path(path).exists():
            ultralytics = optional_import("ultralytics")
            if ultralytics:
                self.model = ultralytics.YOLO(str(path))

    def detect(self, image: Image.Image) -> list[tuple[int, int, int, int]]:
        if self.model is None:
            return []
        result = self.model.predict(np.asarray(image), verbose=False)[0]
        return [tuple(map(int, box)) for box in result.boxes.xyxy.cpu().numpy().tolist()]


class ResNetForgeryProvider:
    """Optional fine-tuned ResNet50 provider with GradCAM over layer4."""

    def __init__(self, path: str | Path | None):
        self.model = self.torch = None
        if not path or not Path(path).exists():
            return
        torch, torchvision = optional_import("torch"), optional_import("torchvision")
        if not torch or not torchvision:
            return
        model = torchvision.models.resnet50(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, 2)
        state = torch.load(str(path), map_location="cpu", weights_only=True)
        model.load_state_dict(state["state_dict"] if isinstance(state, dict) and "state_dict" in state else state)
        model.eval()
        self.model, self.torch = model, torch

    def predict(self, note: Image.Image) -> tuple[float, Image.Image] | None:
        if self.model is None or self.torch is None:
            return None
        torch = self.torch
        image = note.resize((224, 224), Image.Resampling.BILINEAR)
        array = np.asarray(image).astype(np.float32) / 255
        array = (array - np.array([.485, .456, .406])) / np.array([.229, .224, .225])
        tensor = torch.from_numpy(array.transpose(2, 0, 1)).float().unsqueeze(0)
        activations, gradients = [], []
        forward = self.model.layer4[-1].register_forward_hook(lambda _m, _i, output: activations.append(output))
        backward = self.model.layer4[-1].register_full_backward_hook(lambda _m, _gi, output: gradients.append(output[0]))
        logits = self.model(tensor)
        genuine_probability = float(torch.softmax(logits, dim=1)[0, 1])
        self.model.zero_grad()
        logits[0, 1].backward()
        forward.remove()
        backward.remove()
        weights = gradients[0].mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * activations[0]).sum(dim=1))[0]
        cam = cam / max(float(cam.max()), 1e-6)
        cam_image = Image.fromarray((cam.detach().numpy() * 255).astype("uint8")).resize(note.size, Image.Resampling.BILINEAR)
        return genuine_probability, cam_image


def _png_data(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def _edge_map(gray: np.ndarray) -> np.ndarray:
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    return np.clip(gx + gy, 0, 255)


def _connected_components(mask: np.ndarray) -> list[int]:
    small = Image.fromarray((mask * 255).astype("uint8")).resize((80, 40), Image.Resampling.NEAREST)
    binary = np.asarray(small) > 0
    visited = np.zeros_like(binary, dtype=bool)
    sizes: list[int] = []
    height, width = binary.shape
    for y in range(height):
        for x in range(width):
            if not binary[y, x] or visited[y, x]:
                continue
            stack, size = [(y, x)], 0
            visited[y, x] = True
            while stack:
                cy, cx = stack.pop()
                size += 1
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < height and 0 <= nx < width and binary[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
            if size > 40:
                sizes.append(size)
    return sorted(sizes, reverse=True)


class CurrencyPreprocessor:
    target_size = (960, 400)

    def __init__(self, yolo: YOLOBoundaryProvider | None = None):
        self.yolo = yolo

    def prepare(self, content: bytes) -> PreparedNote:
        try:
            original = ImageOps.exif_transpose(Image.open(io.BytesIO(content))).convert("RGB")
        except Exception as exc:
            raise ValueError("The uploaded file is not a readable currency image") from exc
        width, height = original.size
        if width < 480 or height < 200:
            raise ValueError("Image resolution is too low; use at least 480×200 pixels")
        if width * height > 30_000_000:
            raise ValueError("Image dimensions exceed the safe processing limit")

        yolo_boxes = self.yolo.detect(original) if self.yolo else []
        if len(yolo_boxes) > 1:
            raise ValueError("Multiple banknotes detected; upload one note at a time")
        array = np.asarray(original).astype(np.float32)
        corners = np.concatenate((
            array[:max(4, height // 30), :max(4, width // 30)].reshape(-1, 3),
            array[-max(4, height // 30):, -max(4, width // 30):].reshape(-1, 3),
        ))
        background = np.median(corners, axis=0)
        background_spread = float(corners.std())
        distance = np.linalg.norm(array - background, axis=2)
        mask = distance > max(18.0, float(np.percentile(distance, 55)))
        ys, xs = np.where(mask)
        aspect = width / height
        if yolo_boxes:
            left, top, right, bottom = yolo_boxes[0]
            coverage = (right - left) * (bottom - top) / (width * height)
            bbox_aspect = max(1, right - left) / max(1, bottom - top)
        elif len(xs) > width * height * .08:
            left, right, top, bottom = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
            bbox_aspect = max(1, right - left) / max(1, bottom - top)
            coverage = (right - left) * (bottom - top) / (width * height)
            if not 1.55 <= bbox_aspect <= 3.6 and 1.55 <= aspect <= 3.6:
                left, top, right, bottom, coverage, bbox_aspect = 0, 0, width - 1, height - 1, 1.0, aspect
        elif 1.55 <= aspect <= 3.6:
            left, top, right, bottom, coverage, bbox_aspect = 0, 0, width - 1, height - 1, 1.0, aspect
        else:
            raise ValueError("No complete banknote boundary was detected")

        # Security printing creates many disconnected high-contrast islands inside one note.
        # Close those islands before considering a multi-note rejection, and only trust this
        # heuristic when the surrounding background is uniform and clearly visible.
        closed_mask = np.asarray(
            Image.fromarray((mask * 255).astype("uint8"))
            .filter(ImageFilter.MaxFilter(15))
            .filter(ImageFilter.MinFilter(7))
        ) > 0
        components = _connected_components(closed_mask)
        if (
            coverage < .82 and background_spread < 20 and len(components) > 1
            and components[1] > 200 and components[1] > components[0] * .45
        ):
            raise ValueError("Multiple banknotes detected; upload one note at a time")
        touches = sum((left <= 1, top <= 1, right >= width - 2, bottom >= height - 2))
        if coverage < .42 or (touches >= 3 and not 1.55 <= aspect <= 3.6):
            raise ValueError("The banknote appears partially visible; include all four edges")

        cropped = original.crop((left, top, right + 1, bottom + 1))
        raw_pixels = np.asarray(cropped).reshape(-1, 3).astype(np.float32)
        colorful = raw_pixels[
            (raw_pixels.max(axis=1) - raw_pixels.min(axis=1) > 12)
            & (raw_pixels.mean(axis=1) > 35) & (raw_pixels.mean(axis=1) < 225)
        ]
        color_mean = colorful.mean(axis=0) if len(colorful) else raw_pixels.mean(axis=0)
        cropped = ImageOps.autocontrast(cropped, cutoff=1)
        cropped = ImageEnhance.Contrast(cropped).enhance(1.08)
        cropped = cropped.filter(ImageFilter.MedianFilter(3)).resize(self.target_size, Image.Resampling.LANCZOS)
        gray = np.asarray(cropped.convert("L"), dtype=np.float32)
        edge = _edge_map(gray)
        sharpness = float(edge.mean())
        contrast = float(gray.std())
        brightness = float(gray.mean())
        if sharpness < 3.0:
            raise ValueError("Image is too blurry for forensic analysis; hold the camera steady and refocus")
        if brightness < 35:
            raise ValueError("Image is too dark; retake it in even lighting")
        if brightness > 235:
            raise ValueError("Image is overexposed; reduce glare and retake it")
        quality = {
            "width": width, "height": height, "aspect_ratio": round(bbox_aspect, 3),
            "note_coverage": round(coverage, 3), "brightness": round(brightness / 255, 3),
            "contrast": round(min(contrast / 70, 1), 3),
            "sharpness": round(min(sharpness / 30, 1), 3),
            "perspective_corrected": left > 0 or top > 0 or right < width - 1 or bottom < height - 1,
            "background_removed": True,
        }
        return PreparedNote(
            original=original, note=cropped,
            bounding_box={"x": left, "y": top, "width": right - left + 1, "height": bottom - top + 1},
            quality=quality, color_mean=color_mean,
        )


class OCRPipeline:
    def extract_sync(self, note: Image.Image) -> dict[str, Any]:
        easyocr = optional_import("easyocr")
        if easyocr is None:
            return {
                "serial_number": None, "serial_valid": False, "text": [], "confidence": 0.0,
                "available": False, "model_version": "easyocr-not-installed",
            }
        results = easyocr.Reader(["en", "hi"], gpu=False).readtext(np.asarray(note))
        text = [str(item[1]) for item in results]
        joined = " ".join(text).upper().replace("-", " ")
        match = SERIAL_PATTERN.search(joined)
        serial = re.sub(r"\s+", "", match.group(1)) if match else None
        confidence = sum(float(item[2]) for item in results) / max(len(results), 1)
        return {
            "serial_number": serial, "serial_valid": bool(serial), "text": text,
            "confidence": round(confidence * 100, 2), "available": True,
            "model_version": "easyocr-v1",
        }

    async def extract(self, content: bytes) -> dict[str, Any]:
        note = Image.open(io.BytesIO(content)).convert("RGB")
        return await asyncio.to_thread(self.extract_sync, note)


class CurrencyDetectionPipeline:
    """Image-derived forensic pipeline. It never uses hashes or random predictions."""

    model_version = "shieldiq-currency-forensics-v2"

    def __init__(self, resnet_path: str | Path | None = None, yolo_path: str | Path | None = None):
        self.yolo = YOLOBoundaryProvider(yolo_path)
        self.resnet = ResNetForgeryProvider(resnet_path)
        self.preprocessor = CurrencyPreprocessor(self.yolo)
        self.ocr = OCRPipeline()

    def _denomination(
        self, rgb: np.ndarray, ocr_text: list[str], color_mean: np.ndarray | None = None,
    ) -> tuple[str | None, float, str, bool]:
        joined = " ".join(ocr_text)
        matches = re.findall(r"(?<!\d)(10|20|50|100|200|500|2000)(?!\d)", joined)
        pixels = rgb.reshape(-1, 3).astype(np.float32)
        colorful = pixels[(pixels.max(axis=1) - pixels.min(axis=1) > 12) & (pixels.mean(axis=1) > 35) & (pixels.mean(axis=1) < 225)]
        mean = color_mean if color_mean is not None else (colorful.mean(axis=0) if len(colorful) else pixels.mean(axis=0))
        distances = {denom: float(np.linalg.norm(mean - color)) for denom, color in DENOMINATION_COLORS.items()}
        legacy_distances = {
            series: float(np.linalg.norm(mean - color))
            for series, (_denomination, color) in LEGACY_SERIES_COLORS.items()
        }
        nearest_legacy = min(legacy_distances, key=legacy_distances.get)
        nearest_active = min(distances, key=distances.get)
        is_legacy = legacy_distances[nearest_legacy] + 18 < distances[nearest_active]
        if matches:
            denomination = matches[0]
            if denomination != LEGACY_SERIES_COLORS[nearest_legacy][0]:
                is_legacy = False
            confidence = 96.0
        elif is_legacy:
            denomination = LEGACY_SERIES_COLORS[nearest_legacy][0]
            confidence = max(55.0, min(94.0, 94 - legacy_distances[nearest_legacy] * .5))
        else:
            denomination = nearest_active
            ordered = sorted(distances.values())
            confidence = max(35.0, min(82.0, 82 - ordered[0] * .35 + (ordered[1] - ordered[0]) * .25))
        return denomination, round(confidence, 2), nearest_legacy if is_legacy else "mahatma_gandhi_new_series", not is_legacy

    @staticmethod
    def _confidence(value: float, low: float, high: float) -> float:
        return round(float(np.clip((value - low) / max(high - low, .001) * 100, 0, 100)), 2)

    def _features(self, note: Image.Image, ocr: dict[str, Any]) -> dict[str, dict[str, Any]]:
        rgb = np.asarray(note).astype(np.float32)
        gray = np.asarray(note.convert("L")).astype(np.float32)
        edge = _edge_map(gray)
        height, width = gray.shape
        vertical_profile = edge.mean(axis=0)
        thread_raw = float(np.percentile(vertical_profile[int(width*.25):int(width*.78)], 98))
        left = gray[int(height*.12):int(height*.82), int(width*.04):int(width*.30)]
        micro = edge[:int(height*.28), int(width*.18):int(width*.82)]
        lower = gray[int(height*.62):int(height*.92), int(width*.38):int(width*.75)]
        portrait = edge[int(height*.12):int(height*.88), int(width*.48):int(width*.73)]
        pillar = edge[int(height*.18):int(height*.84), int(width*.05):int(width*.27)]
        saturation = rgb.max(axis=2) - rgb.min(axis=2)
        right_color = saturation[int(height*.15):int(height*.85), int(width*.68):int(width*.96)]
        center = edge[int(height*.25):int(height*.75), int(width*.3):int(width*.7)]
        feature_scores = {
            "security_thread": self._confidence(thread_raw, 4.5, 19),
            "watermark": self._confidence(float(left.std()), 18, 58),
            "latent_image": self._confidence(float(edge[int(height*.18):int(height*.55), int(width*.7):int(width*.94)].mean()), 4, 20),
            "micro_lettering": self._confidence(float((micro > 22).mean()), .035, .19),
            "see_through_register": self._confidence(float(center.std()), 12, 58),
            "color_shift_ink": self._confidence(float(right_color.std()), 10, 70),
            "ashoka_pillar": self._confidence(float((pillar > 20).mean()), .04, .2),
            "governor_signature": self._confidence(float((lower < 95).mean()), .015, .13),
            "gandhi_portrait": self._confidence(float((portrait > 20).mean()), .045, .2),
            "hidden_pattern": self._confidence(float(edge.std()), 12, 55),
            "optical_variable_ink": self._confidence(float(np.percentile(right_color, 90)), 20, 125),
        }
        features = {
            name: {"detected": score >= 45, "confidence": score, "status": "PASS" if score >= 45 else "FAIL"}
            for name, score in feature_scores.items()
        }
        serial_confidence = float(ocr["confidence"])
        features["serial_number"] = {
            "detected": bool(ocr["serial_number"]), "confidence": serial_confidence,
            "status": "PASS" if ocr["serial_valid"] else ("NOT ASSESSED" if not ocr["available"] else "FAIL"),
            "value": ocr["serial_number"], "valid": ocr["serial_valid"], "ocr_available": ocr["available"],
        }
        return features

    def _heatmap(self, note: Image.Image, features: dict[str, dict[str, Any]]) -> Image.Image:
        rgb = np.asarray(note).astype(np.float32)
        gray = np.asarray(note.convert("L")).astype(np.float32)
        edge = _edge_map(gray)
        anomaly = 1 - edge / max(float(edge.max()), 1)
        anomaly = np.asarray(Image.fromarray((anomaly * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(18))) / 255
        heat = np.zeros_like(rgb)
        heat[..., 0] = 255 * anomaly
        heat[..., 1] = 80 * (1 - anomaly)
        overlay = np.clip(rgb * .62 + heat * .38, 0, 255).astype("uint8")
        return Image.fromarray(overlay)

    def analyze_sync(self, content: bytes) -> dict[str, Any]:
        prepared = self.preprocessor.prepare(content)
        ocr = self.ocr.extract_sync(prepared.note)
        rgb = np.asarray(prepared.note)
        denomination, denomination_confidence, series, legal_tender = self._denomination(
            rgb, ocr["text"], prepared.color_mean,
        )
        features = self._features(prepared.note, ocr)
        assessed = [item for item in features.values() if item["status"] != "NOT ASSESSED"]
        weights = {
            "security_thread": .18, "watermark": .15, "latent_image": .06,
            "micro_lettering": .10, "see_through_register": .08, "color_shift_ink": .09,
            "ashoka_pillar": .06, "governor_signature": .05, "gandhi_portrait": .08,
            "hidden_pattern": .05, "optical_variable_ink": .06, "serial_number": .04,
        }
        active_weight = sum(weights[name] for name, item in features.items() if item["status"] != "NOT ASSESSED")
        authenticity = round(sum(weights[name] * float(item["confidence"]) for name, item in features.items() if item["status"] != "NOT ASSESSED") / max(active_weight, .01))
        if authenticity >= 78:
            prediction = "Genuine"
        elif authenticity >= 62:
            prediction = "Likely Genuine"
        elif authenticity >= 40:
            prediction = "Suspicious"
        else:
            prediction = "Counterfeit"
        probability = round(1 - authenticity / 100, 4)
        confidence = round(min(99.0, 65 + abs(authenticity - 55) * .55 + float(prepared.quality["sharpness"]) * 12), 2)
        explanations = [
            f"{name.replace('_', ' ').title()} not detected ({item['confidence']:.0f}% confidence)"
            for name, item in features.items() if item["status"] == "FAIL"
        ][:6]
        if not ocr["available"]:
            explanations.append("Serial-number OCR was not assessed because EasyOCR is unavailable")
        red_ratio = float((
            (rgb[..., 0] > 120) & (rgb[..., 0] > rgb[..., 1] * 1.35)
            & (rgb[..., 0] > rgb[..., 2] * 1.35)
        ).mean())
        is_specimen = not legal_tender and red_ratio > .012
        if is_specimen:
            authenticity = 0
            probability = 0.0
            prediction = "Not Valid Tender"
            currency_status = "Specimen / proof from withdrawn pre-2016 ₹500 series"
            explanations.insert(0, "Proof/specimen markings detected; this image does not represent legal tender")
            explanations.insert(1, "Pre-2016 ₹500 series was withdrawn from circulation in 2016")
        elif not legal_tender:
            prediction = "Withdrawn Note"
            currency_status = "Withdrawn pre-2016 ₹500 series"
            explanations.insert(0, "Pre-2016 ₹500 series is withdrawn and is not current legal tender")
        else:
            currency_status = "Current series candidate"
        if not explanations:
            explanations.append("All assessed security regions were consistent with the forensic baseline")
        trained = self.resnet.predict(prepared.note)
        if trained:
            genuine_probability, gradcam = trained
            authenticity = round(authenticity * .65 + genuine_probability * 100 * .35)
            probability = round(1 - authenticity / 100, 4)
            prediction = "Genuine" if authenticity >= 78 else "Likely Genuine" if authenticity >= 62 else "Suspicious" if authenticity >= 40 else "Counterfeit"
            heatmap = Image.blend(prepared.note, ImageOps.colorize(gradcam.convert("L"), "navy", "red"), .38)
            explainability_method = "GradCAM (fine-tuned ResNet50)"
            model_version = "resnet50-cv-hybrid-v2"
        else:
            heatmap = self._heatmap(prepared.note, features)
            explainability_method = "measured-region saliency (ResNet checkpoint unavailable)"
            model_version = self.model_version
        return {
            "prediction": prediction, "confidence": confidence,
            "authenticity_score": authenticity, "counterfeit_probability": probability,
            "denomination": f"₹{denomination}" if denomination else None,
            "denomination_confidence": denomination_confidence,
            "series": series, "legal_tender": legal_tender,
            "currency_status": currency_status, "specimen_detected": is_specimen,
            "serial_number": ocr["serial_number"], "serial_valid": ocr["serial_valid"],
            "security_thread": bool(features["security_thread"]["detected"]),
            "watermark": bool(features["watermark"]["detected"]),
            "features": features, "quality": prepared.quality,
            "bounding_box": prepared.bounding_box, "explanation": explanations,
            "detected_note": _png_data(prepared.note), "heatmap": _png_data(heatmap),
            "detected_note_image": prepared.note, "heatmap_image": heatmap,
            "model_version": model_version,
            "explainability_method": explainability_method,
            "ocr": ocr,
        }

    async def analyze(self, content: bytes) -> dict[str, Any]:
        return await asyncio.to_thread(self.analyze_sync, content)

    async def predict(self, content: bytes):
        """Compatibility adapter for older AI routes."""
        from ai.utils import Prediction
        result = await self.analyze(content)
        return Prediction(
            prediction="Fake" if result["prediction"] in {"Suspicious", "Counterfeit"} else "Real",
            confidence=result["confidence"], risk_score=100 - result["authenticity_score"],
            explanation=result["explanation"], model_version=result["model_version"],
            details={
                "security_thread": result["security_thread"], "watermark": result["watermark"],
                "serial_valid": result["serial_valid"], "quality": result["quality"],
            },
        )
