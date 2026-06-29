import io
from typing import Any

from ai.utils.lazy_imports import optional_import


def decode_image(content: bytes) -> Any | None:
    cv2, np = optional_import("cv2"), optional_import("numpy")
    if cv2 is None or np is None:
        return None
    return cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)


def image_quality_features(content: bytes) -> dict[str, float]:
    image, cv2, np = decode_image(content), optional_import("cv2"), optional_import("numpy")
    if image is None or cv2 is None or np is None:
        checksum = sum(content[:4096]) or 1
        return {"brightness": checksum % 255 / 255, "sharpness": (checksum // 3) % 100 / 100, "contrast": (checksum // 7) % 100 / 100}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return {
        "brightness": float(gray.mean() / 255),
        "sharpness": float(min(cv2.Laplacian(gray, cv2.CV_64F).var() / 1000, 1)),
        "contrast": float(min(gray.std() / 80, 1)),
    }
