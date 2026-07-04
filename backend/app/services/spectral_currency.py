from __future__ import annotations

import io
from typing import Any

import numpy as np
from PIL import Image, ImageOps


class SpectralCurrencyAnalyzer:
    """Analyze aligned visible/UV/IR captures without simulating absent sensor data."""

    @staticmethod
    def _gray(content: bytes) -> np.ndarray:
        image = Image.open(io.BytesIO(content))
        image.verify()
        image = Image.open(io.BytesIO(content)).convert("L")
        image = ImageOps.exif_transpose(image)
        return np.asarray(image, dtype=np.float32) / 255.0

    def analyze(
        self, visible: bytes, uv: bytes | None = None, infrared: bytes | None = None,
    ) -> dict[str, Any]:
        base = self._gray(visible)
        result: dict[str, Any] = {
            "capture_type": "multispectral" if uv or infrared else "visible_only",
            "uv": {"assessed": False, "status": "NOT ASSESSED"},
            "infrared": {"assessed": False, "status": "NOT ASSESSED"},
            "limitations": [],
        }
        for name, content in (("uv", uv), ("infrared", infrared)):
            if not content:
                continue
            channel = self._gray(content)
            aspect_delta = abs(base.shape[1] / base.shape[0] - channel.shape[1] / channel.shape[0])
            if aspect_delta > .08:
                result[name] = {
                    "assessed": False, "status": "REJECTED",
                    "reason": "Spectral image aspect ratio does not match the visible capture",
                }
                continue
            resized = np.asarray(
                Image.fromarray((channel * 255).astype("uint8")).resize(
                    (base.shape[1], base.shape[0]), Image.Resampling.BILINEAR
                ),
                dtype=np.float32,
            ) / 255.0
            if name == "uv":
                bright_ratio = float((resized > .78).mean())
                contrast = float(resized.std())
                passed = .002 <= bright_ratio <= .28 and contrast >= .08
                result[name] = {
                    "assessed": True, "status": "PASS" if passed else "REVIEW",
                    "fluorescent_response_ratio": round(bright_ratio, 4),
                    "contrast": round(contrast, 4),
                    "explanation": (
                        "UV capture contains localized fluorescent response"
                        if passed else "UV response is absent, excessive, or too uniform; expert review is required"
                    ),
                }
            else:
                difference = float(np.mean(np.abs(base - resized)))
                dropout = float(((base > .35) & (resized < base * .55)).mean())
                passed = difference >= .035 and dropout >= .005
                result[name] = {
                    "assessed": True, "status": "PASS" if passed else "REVIEW",
                    "visible_ir_difference": round(difference, 4),
                    "ink_dropout_ratio": round(dropout, 4),
                    "explanation": (
                        "Infrared capture contains selective ink response"
                        if passed else "Expected selective infrared ink response was not clearly measured"
                    ),
                }
        if not uv:
            result["limitations"].append("No physical UV capture supplied; UV features were not simulated")
        if not infrared:
            result["limitations"].append("No physical infrared capture supplied")
        result["decision_policy"] = "Spectral evidence is reported independently and does not override the visible-image verdict without a validated model."
        return result
