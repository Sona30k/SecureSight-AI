from pathlib import Path
import random
import io

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


def generate_currency_dataset(root: Path, per_class: int = 4, seed: int = 2026) -> int:
    """Generate abstract, labelled banknote-like samples for pipeline and augmentation tests."""
    pil_image = optional_import("PIL.Image")
    pil_draw = optional_import("PIL.ImageDraw")
    pil_enhance = optional_import("PIL.ImageEnhance")
    pil_filter = optional_import("PIL.ImageFilter")
    np = optional_import("numpy")
    if not all((pil_image, pil_draw, pil_enhance, pil_filter, np)):
        raise RuntimeError("Pillow and NumPy are required for currency dataset generation")
    rng = random.Random(seed)
    denominations = ("10", "20", "50", "100", "200", "500", "2000")
    colors = {
        "10": (126, 91, 66), "20": (172, 155, 84), "50": (74, 135, 166),
        "100": (142, 121, 157), "200": (198, 151, 57), "500": (126, 127, 124),
        "2000": (157, 84, 135),
    }
    generated = 0
    for label in ("real", "fake"):
        for denomination in denominations:
            target = root / label / denomination
            target.mkdir(parents=True, exist_ok=True)
            for index in range(per_class):
                image = pil_image.new("RGB", (960, 400), colors[denomination])
                draw = pil_draw.Draw(image)
                draw.rectangle((8, 8, 951, 391), outline=(35, 35, 40), width=5)
                draw.ellipse((485, 65, 700, 335), outline=(55, 50, 65), width=10)
                if label == "real":
                    draw.rectangle((280, 18, 297, 382), fill=(82, 76, 92))
                    for x in range(35, 930, 22):
                        draw.line((x, 30, x + 18, 370), fill=(75 + x % 90, 65, 105), width=2)
                else:
                    draw.rectangle((420, 25, 430, 375), fill=(145, 140, 150))
                    draw.rectangle((520, 100, 820, 220), fill=tuple(min(255, c + 25) for c in colors[denomination]))
                draw.text((48, 46), f"SYNTHETIC TEST NOTE {denomination}", fill=(20, 20, 25))
                draw.text((600, 340), f"TST{index:06d}", fill=(25, 25, 30))
                angle = rng.uniform(-3.5, 3.5)
                image = image.rotate(angle, resample=pil_image.Resampling.BICUBIC, fillcolor=(235, 235, 235))
                image = pil_enhance.Brightness(image).enhance(rng.uniform(.78, 1.18))
                image = pil_enhance.Contrast(image).enhance(rng.uniform(.78, 1.28))
                if index % 3 == 1:
                    image = image.filter(pil_filter.GaussianBlur(rng.uniform(.3, 1.2)))
                array = np.asarray(image).astype(np.int16)
                noise = np.random.default_rng(seed + generated).normal(0, 4 + index, array.shape)
                array = np.clip(array + noise, 0, 255).astype(np.uint8)
                image = pil_image.fromarray(array)
                if index % 4 == 3:
                    shadow = pil_image.new("RGBA", image.size, (0, 0, 0, 0))
                    pil_draw.Draw(shadow).polygon([(0, 0), (240, 0), (520, 400), (250, 400)], fill=(0, 0, 0, 45))
                    image = pil_image.alpha_composite(image.convert("RGBA"), shadow).convert("RGB")
                image.save(target / f"sample_{index:03}.jpg", quality=70 + index % 25)
                generated += 1
    return generated
