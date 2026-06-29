from pathlib import Path


def validate_audio(filename: str, content: bytes, max_mb: int = 25) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".ogg", ".webm"}:
        raise ValueError("Unsupported audio format")
    if not content or len(content) > max_mb * 1024 * 1024:
        raise ValueError(f"Audio must be between 1 byte and {max_mb} MB")
    return suffix
