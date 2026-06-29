"""Optional Ultralytics YOLOv8 currency detector training."""
from pathlib import Path


def train_yolo(data_yaml: Path, output: Path, epochs: int = 30):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install ultralytics to train YOLOv8") from exc
    model = YOLO("yolov8n.pt")
    return model.train(data=str(data_yaml), epochs=epochs, imgsz=640, project=str(output), name="currency_v1")
