"""Training entrypoints for YOLOv8 localization and currency authenticity classification."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def train_yolo(data_yaml: Path, output: Path, epochs: int = 50):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install requirements-ai.txt to train YOLOv8") from exc
    model = YOLO("yolov8n.pt")
    return model.train(
        data=str(data_yaml), epochs=epochs, imgsz=960,
        project=str(output), name="banknote_yolov8", patience=12,
    )


def train_classifier(
    dataset: Path,
    output: Path,
    architecture: str = "efficientnet_b0",
    epochs: int = 20,
    batch_size: int = 16,
) -> dict[str, float]:
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, Subset
        from torchvision import datasets, models, transforms
    except ImportError as exc:
        raise RuntimeError("Install requirements-ai.txt to train the classifier") from exc
    if architecture not in {"resnet50", "efficientnet_b0"}:
        raise ValueError("architecture must be resnet50 or efficientnet_b0")

    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomAffine(degrees=3, translate=(.025, .025), scale=(.96, 1.04)),
        transforms.ColorJitter(brightness=.14, contrast=.14, saturation=.08),
        transforms.ToTensor(),
        transforms.Normalize([.485, .456, .406], [.229, .224, .225]),
    ])
    validation_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([.485, .456, .406], [.229, .224, .225]),
    ])
    train_source = datasets.ImageFolder(dataset, transform=train_transform)
    validation_source = datasets.ImageFolder(dataset, transform=validation_transform)
    if len(train_source.classes) != 2:
        raise ValueError("Dataset must contain exactly two class folders, for example fake/ and real/")

    rng = random.Random(42)
    train_indices: list[int] = []
    validation_indices: list[int] = []
    for class_index in range(len(train_source.classes)):
        indices = [index for index, label in enumerate(train_source.targets) if label == class_index]
        if len(indices) < 5:
            raise ValueError("Each class requires at least five independently sourced images")
        rng.shuffle(indices)
        split = max(1, round(len(indices) * .2))
        validation_indices.extend(indices[:split])
        train_indices.extend(indices[split:])

    train_loader = DataLoader(
        Subset(train_source, train_indices), batch_size=batch_size,
        shuffle=True, num_workers=0,
    )
    validation_loader = DataLoader(
        Subset(validation_source, validation_indices), batch_size=batch_size,
        shuffle=False, num_workers=0,
    )
    if architecture == "resnet50":
        model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        model.fc = nn.Linear(model.fc.in_features, 2)
    else:
        model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, 2)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    best_accuracy = 0.0
    best_state = None
    for _epoch in range(epochs):
        model.train()
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for images, labels in validation_loader:
                labels = labels.to(device)
                predictions = model(images.to(device)).argmax(dim=1)
                correct += int((predictions == labels).sum())
                total += labels.numel()
        accuracy = correct / max(total, 1)
        if accuracy >= best_accuracy:
            best_accuracy = accuracy
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}

    metrics = {
        "validation_accuracy": round(best_accuracy, 4),
        "train_images": float(len(train_indices)),
        "validation_images": float(len(validation_indices)),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": best_state,
        "architecture": architecture,
        "class_to_idx": train_source.class_to_idx,
        "input_size": [224, 224],
        "metrics": metrics,
    }, output)
    output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    yolo = subparsers.add_parser("yolo")
    yolo.add_argument("data_yaml", type=Path)
    yolo.add_argument("output", type=Path)
    yolo.add_argument("--epochs", type=int, default=50)
    classifier = subparsers.add_parser("classifier")
    classifier.add_argument("dataset", type=Path)
    classifier.add_argument("output", type=Path)
    classifier.add_argument("--architecture", choices=["resnet50", "efficientnet_b0"], default="efficientnet_b0")
    classifier.add_argument("--epochs", type=int, default=20)
    classifier.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.command == "yolo":
        train_yolo(args.data_yaml, args.output, args.epochs)
    else:
        print(train_classifier(
            args.dataset, args.output, args.architecture, args.epochs, args.batch_size,
        ))
