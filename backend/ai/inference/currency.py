from __future__ import annotations

import asyncio
import base64
import io
import re
import threading
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


@dataclass(frozen=True)
class NoteDetection:
    box: tuple[int, int, int, int]
    confidence: float
    class_name: str


class YOLOBoundaryProvider:
    """YOLOv8 banknote-localization adapter with an explicit confidence threshold."""

    def __init__(self, path: str | Path | None, confidence: float = .55):
        self.model = None
        self._inference_lock = threading.Lock()
        self.confidence = confidence
        self.checkpoint = str(path) if path else None
        if path and Path(path).exists():
            ultralytics = optional_import("ultralytics")
            if ultralytics:
                self.model = ultralytics.YOLO(str(path))

    @property
    def available(self) -> bool:
        return self.model is not None

    def detect(self, image: Image.Image) -> list[NoteDetection]:
        if self.model is None:
            return []
        with self._inference_lock:
            result = self.model.predict(
                np.asarray(image), verbose=False, conf=self.confidence, max_det=5,
            )[0]
        names = getattr(result, "names", {}) or {}
        detections: list[NoteDetection] = []
        boxes = result.boxes
        for box, confidence, class_id in zip(
            boxes.xyxy.cpu().numpy().tolist(),
            boxes.conf.cpu().numpy().tolist(),
            boxes.cls.cpu().numpy().tolist(),
        ):
            detections.append(NoteDetection(
                box=tuple(map(int, box)),
                confidence=float(confidence),
                class_name=str(names.get(int(class_id), "banknote")),
            ))
        return sorted(detections, key=lambda item: item.confidence, reverse=True)


class TorchForgeryProvider:
    """Fine-tuned ResNet50/EfficientNet-B0 classifier with prediction-targeted Grad-CAM."""

    supported_architectures = {"resnet50", "efficientnet_b0"}

    def __init__(self, path: str | Path | None, architecture: str = "efficientnet_b0"):
        self.model = self.torch = self.target_layer = None
        self._inference_lock = threading.Lock()
        self.architecture = architecture
        self.checkpoint = str(path) if path else None
        self.class_to_idx = {"counterfeit": 0, "genuine": 1}
        if architecture not in self.supported_architectures or not path or not Path(path).exists():
            return
        torch, torchvision = optional_import("torch"), optional_import("torchvision")
        if not torch or not torchvision:
            return
        state = torch.load(str(path), map_location="cpu", weights_only=True)
        metadata = state if isinstance(state, dict) else {}
        checkpoint_arch = str(metadata.get("architecture", architecture))
        if checkpoint_arch in self.supported_architectures:
            self.architecture = checkpoint_arch
        if isinstance(metadata.get("class_to_idx"), dict):
            self.class_to_idx = {
                str(label).lower(): int(index)
                for label, index in metadata["class_to_idx"].items()
            }
        if self.architecture == "resnet50":
            model = torchvision.models.resnet50(weights=None)
            model.fc = torch.nn.Linear(model.fc.in_features, 2)
            target_layer = model.layer4[-1]
        else:
            model = torchvision.models.efficientnet_b0(weights=None)
            model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, 2)
            target_layer = model.features[-1]
        state_dict = metadata.get("state_dict", state)
        state_dict = {
            str(key).removeprefix("module."): value
            for key, value in state_dict.items()
        }
        model.load_state_dict(state_dict)
        model.eval()
        self.model, self.torch, self.target_layer = model, torch, target_layer

    @property
    def available(self) -> bool:
        return self.model is not None

    def predict(self, note: Image.Image) -> dict[str, Any] | None:
        if self.model is None or self.torch is None or self.target_layer is None:
            return None
        with self._inference_lock:
            return self._predict(note)

    def _predict(self, note: Image.Image) -> dict[str, Any]:
        torch = self.torch
        image = note.resize((224, 224), Image.Resampling.BILINEAR)
        array = np.asarray(image).astype(np.float32) / 255
        array = (array - np.array([.485, .456, .406])) / np.array([.229, .224, .225])
        tensor = torch.from_numpy(array.transpose(2, 0, 1)).float().unsqueeze(0)
        activations = []
        def capture_activation(_module, _inputs, output):
            output.retain_grad()
            activations.append(output)
        forward = self.target_layer.register_forward_hook(capture_activation)
        logits = self.model(tensor)
        probabilities = torch.softmax(logits, dim=1)[0]
        genuine_index = next(
            (index for label, index in self.class_to_idx.items() if label in {"genuine", "real"}),
            1,
        )
        genuine_probability = float(probabilities[genuine_index].detach())
        target_index = int(torch.argmax(probabilities))
        predicted_label = next(
            (label for label, index in self.class_to_idx.items() if index == target_index),
            "genuine" if target_index == genuine_index else "counterfeit",
        )
        self.model.zero_grad()
        logits[0, target_index].backward()
        forward.remove()
        gradients = activations[0].grad
        weights = gradients.mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * activations[0]).sum(dim=1))[0]
        cam = cam / max(float(cam.max().detach()), 1e-6)
        cam_image = Image.fromarray((cam.detach().numpy() * 255).astype("uint8")).resize(note.size, Image.Resampling.BILINEAR)
        return {
            "genuine_probability": genuine_probability,
            "predicted_label": predicted_label,
            "prediction_confidence": float(probabilities[target_index].detach()),
            "gradcam": cam_image,
            "architecture": self.architecture,
        }


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


class OpenCVPerspectiveRectifier:
    """Find four note corners and apply a true homography with OpenCV."""

    target_size = (960, 400)

    def __init__(self):
        self.cv2 = optional_import("cv2")

    @property
    def available(self) -> bool:
        return self.cv2 is not None

    @staticmethod
    def _ordered(points: np.ndarray) -> np.ndarray:
        points = points.astype("float32")
        ordered = np.zeros((4, 2), dtype="float32")
        sums, differences = points.sum(axis=1), np.diff(points, axis=1).reshape(-1)
        ordered[0], ordered[2] = points[np.argmin(sums)], points[np.argmax(sums)]
        ordered[1], ordered[3] = points[np.argmin(differences)], points[np.argmax(differences)]
        return ordered

    def rectify(
        self, image: Image.Image, bounding_box: tuple[int, int, int, int],
    ) -> tuple[Image.Image, bool, str]:
        left, top, right, bottom = bounding_box
        fallback = image.crop((left, top, right + 1, bottom + 1))
        if self.cv2 is None:
            return fallback.resize(self.target_size, Image.Resampling.LANCZOS), False, "crop_resize"

        cv2 = self.cv2
        rgb = np.asarray(image)
        roi = rgb[top:bottom + 1, left:right + 1]
        if roi.size == 0:
            return fallback.resize(self.target_size, Image.Resampling.LANCZOS), False, "crop_resize"
        gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 45, 140)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        roi_area = float(max(1, roi.shape[0] * roi.shape[1]))
        quadrilateral = None
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
            if cv2.contourArea(contour) < roi_area * .22:
                continue
            perimeter = cv2.arcLength(contour, True)
            approximation = cv2.approxPolyDP(contour, .02 * perimeter, True)
            if len(approximation) == 4 and cv2.isContourConvex(approximation):
                quadrilateral = approximation.reshape(4, 2)
                break
        if quadrilateral is None:
            return fallback.resize(self.target_size, Image.Resampling.LANCZOS), False, "crop_resize"

        source = self._ordered(quadrilateral)
        top_width = np.linalg.norm(source[1] - source[0])
        bottom_width = np.linalg.norm(source[2] - source[3])
        left_height = np.linalg.norm(source[3] - source[0])
        right_height = np.linalg.norm(source[2] - source[1])
        output_width = max(int(top_width), int(bottom_width))
        output_height = max(int(left_height), int(right_height))
        if output_width < 100 or output_height < 45:
            return fallback.resize(self.target_size, Image.Resampling.LANCZOS), False, "crop_resize"
        destination = np.array([
            [0, 0], [output_width - 1, 0],
            [output_width - 1, output_height - 1], [0, output_height - 1],
        ], dtype="float32")
        matrix = cv2.getPerspectiveTransform(source, destination)
        warped = cv2.warpPerspective(
            roi, matrix, (output_width, output_height),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
        )
        if output_height > output_width:
            warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
        aspect = warped.shape[1] / max(1, warped.shape[0])
        if not 1.45 <= aspect <= 4.0:
            return fallback.resize(self.target_size, Image.Resampling.LANCZOS), False, "crop_resize"
        corrected = Image.fromarray(warped).resize(self.target_size, Image.Resampling.LANCZOS)
        return corrected, True, "opencv_homography"


class CurrencyPreprocessor:
    target_size = (960, 400)

    def __init__(
        self, yolo: YOLOBoundaryProvider | None = None,
        rectifier: OpenCVPerspectiveRectifier | None = None,
    ):
        self.yolo = yolo
        self.rectifier = rectifier or OpenCVPerspectiveRectifier()

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

        yolo_detections = self.yolo.detect(original) if self.yolo else []
        if len(yolo_detections) > 1:
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
        if yolo_detections:
            left, top, right, bottom = yolo_detections[0].box
            left, top = max(0, left), max(0, top)
            right, bottom = min(width - 1, right), min(height - 1, bottom)
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

        raw_crop = original.crop((left, top, right + 1, bottom + 1))
        raw_pixels = np.asarray(raw_crop).reshape(-1, 3).astype(np.float32)
        colorful = raw_pixels[
            (raw_pixels.max(axis=1) - raw_pixels.min(axis=1) > 12)
            & (raw_pixels.mean(axis=1) > 35) & (raw_pixels.mean(axis=1) < 225)
        ]
        color_mean = colorful.mean(axis=0) if len(colorful) else raw_pixels.mean(axis=0)
        cropped, perspective_corrected, correction_method = self.rectifier.rectify(
            original, (left, top, right, bottom),
        )
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
            "perspective_corrected": perspective_corrected,
            "perspective_correction_method": correction_method,
            "boundary_detector": "yolov8" if yolo_detections else "image_contour_fallback",
            "detector_confidence": round(yolo_detections[0].confidence, 4) if yolo_detections else 0.0,
            "background_removed": True,
        }
        return PreparedNote(
            original=original, note=cropped,
            bounding_box={"x": left, "y": top, "width": right - left + 1, "height": bottom - top + 1},
            quality=quality, color_mean=color_mean,
        )


class OCRPipeline:
    _readers: dict[tuple[tuple[str, ...], bool, bool], Any] = {}
    _reader_lock = threading.Lock()

    def __init__(
        self, languages: tuple[str, ...] = ("en", "hi"), gpu: bool = False,
        download_enabled: bool = False,
    ):
        self.languages = languages
        self.gpu = gpu
        self.download_enabled = download_enabled
        self._inference_lock = threading.Lock()

    def _reader(self, easyocr):
        key = (self.languages, self.gpu, self.download_enabled)
        if key not in self._readers:
            with self._reader_lock:
                if key not in self._readers:
                    self._readers[key] = easyocr.Reader(
                        list(self.languages), gpu=self.gpu,
                        download_enabled=self.download_enabled,
                    )
        return self._readers[key]

    def extract_sync(self, note: Image.Image) -> dict[str, Any]:
        easyocr = optional_import("easyocr")
        if easyocr is None:
            return {
                "serial_number": None, "serial_valid": False, "text": [], "confidence": 0.0,
                "available": False, "model_version": "easyocr-not-installed",
            }
        try:
            with self._inference_lock:
                results = self._reader(easyocr).readtext(
                    np.asarray(note), detail=1, paragraph=False,
                    allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789₹ ",
                )
        except Exception as exc:
            return {
                "serial_number": None, "serial_valid": False, "text": [], "confidence": 0.0,
                "available": False, "model_version": f"easyocr-unavailable:{type(exc).__name__}",
            }
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

    model_version = "shieldiq-currency-forensics-v3"

    def __init__(
        self,
        classifier_path: str | Path | None = None,
        classifier_arch: str = "efficientnet_b0",
        yolo_path: str | Path | None = None,
        yolo_confidence: float = .55,
        ocr_gpu: bool = False,
        ocr_download_enabled: bool = False,
        resnet_path: str | Path | None = None,
    ):
        # resnet_path remains accepted for backward-compatible deployments.
        checkpoint = classifier_path or resnet_path
        self.yolo = YOLOBoundaryProvider(yolo_path, yolo_confidence)
        self.classifier = TorchForgeryProvider(checkpoint, classifier_arch)
        self.rectifier = OpenCVPerspectiveRectifier()
        self.preprocessor = CurrencyPreprocessor(self.yolo, self.rectifier)
        self.ocr = OCRPipeline(gpu=ocr_gpu, download_enabled=ocr_download_enabled)

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
        trained = self.classifier.predict(prepared.note) if legal_tender else None
        if trained:
            genuine_probability = float(trained["genuine_probability"])
            authenticity = round(authenticity * .65 + genuine_probability * 100 * .35)
            probability = round(1 - authenticity / 100, 4)
            prediction = "Genuine" if authenticity >= 78 else "Likely Genuine" if authenticity >= 62 else "Suspicious" if authenticity >= 40 else "Counterfeit"
            heatmap = Image.blend(
                prepared.note,
                ImageOps.colorize(trained["gradcam"].convert("L"), "navy", "red"),
                .38,
            )
            architecture = str(trained["architecture"])
            explainability_method = f"Grad-CAM ({architecture}, predicted class: {trained['predicted_label']})"
            model_version = f"{architecture}-yolov8-easyocr-gradcam-v3"
            explanations.insert(
                0,
                f"{architecture} classified the note as {trained['predicted_label']} "
                f"with {float(trained['prediction_confidence']) * 100:.1f}% confidence",
            )
        else:
            heatmap = self._heatmap(prepared.note, features)
            explainability_method = "measured-region saliency (trained classifier checkpoint unavailable)"
            model_version = self.model_version
        pipeline_stages = {
            "note_detection": {
                "provider": "YOLOv8" if self.yolo.available else "image contour fallback",
                "checkpoint_configured": self.yolo.available,
                "confidence": prepared.quality["detector_confidence"],
            },
            "perspective_correction": {
                "provider": prepared.quality["perspective_correction_method"],
                "opencv_available": self.rectifier.available,
                "applied": prepared.quality["perspective_corrected"],
            },
            "serial_ocr": {
                "provider": ocr["model_version"],
                "available": ocr["available"],
                "confidence": ocr["confidence"],
            },
            "classification": {
                "provider": self.classifier.architecture,
                "checkpoint_configured": self.classifier.available,
                "prediction": trained["predicted_label"] if trained else None,
                "confidence": round(float(trained["prediction_confidence"]) * 100, 2) if trained else None,
            },
            "explainability": {
                "provider": "Grad-CAM" if trained else "measured-region saliency",
                "target": trained["predicted_label"] if trained else "forensic feature anomalies",
            },
        }
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
            "pipeline_stages": pipeline_stages,
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
