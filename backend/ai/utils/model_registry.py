import json
from pathlib import Path
from typing import Any

from ai.config import settings


class ModelRegistry:
    """Small filesystem registry; replace with MLflow/S3 in production."""

    def __init__(self, root: Path = settings.artifacts_dir):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_metadata(self, name: str, metadata: dict[str, Any]) -> Path:
        target = self.root / f"{name}.json"
        target.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return target

    def load_metadata(self, name: str) -> dict[str, Any]:
        target = self.root / f"{name}.json"
        return json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
