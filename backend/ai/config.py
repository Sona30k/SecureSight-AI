from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AISettings:
    model_version: str = "v1.0"
    random_seed: int = 42
    datasets_dir: Path = ROOT / "datasets"
    artifacts_dir: Path = ROOT / "artifacts"
    device: str = "cpu"


settings = AISettings()
