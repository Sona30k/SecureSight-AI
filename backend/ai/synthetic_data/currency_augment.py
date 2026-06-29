from pathlib import Path

from ai.utils.lazy_imports import optional_import


def augment_currency(source: Path, output: Path) -> int:
    """Create brightness, rotation, blur, noise, contrast, crop and JPEG variants."""
    cv2, np = optional_import("cv2"), optional_import("numpy")
    if not cv2 or not np:
        raise RuntimeError("Install opencv-python-headless and numpy for image augmentation")
    output.mkdir(parents=True, exist_ok=True)
    generated = 0
    for image_path in list(source.glob("*.jpg")) + list(source.glob("*.png")):
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        h, w = image.shape[:2]
        variants = {
            "bright": cv2.convertScaleAbs(image, alpha=1.1, beta=30),
            "dark": cv2.convertScaleAbs(image, alpha=.7, beta=-15),
            "blur": cv2.GaussianBlur(image, (9, 9), 0),
            "rotate": cv2.warpAffine(image, cv2.getRotationMatrix2D((w / 2, h / 2), 7, 1), (w, h)),
            "noise": np.clip(image.astype(np.int16) + np.random.normal(0, 18, image.shape), 0, 255).astype(np.uint8),
            "crop": image[int(h*.03):int(h*.97), int(w*.03):int(w*.97)],
        }
        for name, variant in variants.items():
            cv2.imwrite(str(output / f"{image_path.stem}_{name}.jpg"), variant, [cv2.IMWRITE_JPEG_QUALITY, 72])
            generated += 1
    return generated
