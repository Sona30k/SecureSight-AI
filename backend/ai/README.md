# ShieldIQ AI/ML

Modular hackathon-ready AI subsystem for scam calls, counterfeit currency, OCR, fraud graphs, hotspot prediction, voice analysis, explainable hybrid risk scoring and citizen assistance.

## Design

Each inference module exposes a stable service contract and works in two modes:

1. **Portable baseline** — deterministic, explainable and runnable without model downloads.
2. **Model-backed** — activates when trained HuggingFace, YOLO/ResNet, EasyOCR, Whisper, Random Forest/XGBoost or SHAP dependencies and artifacts are available.

No proprietary government data is used. The generator produces realistic but entirely synthetic records.

## Generate datasets

```bash
cd backend
source .venv/bin/activate
python -m ai.synthetic_data.generate
```

The manifest records the expected counts. Currency image variations can be generated from legally usable sample images:

```python
from pathlib import Path
from ai.synthetic_data.currency_augment import augment_currency
augment_currency(Path("source_notes"), Path("ai/datasets/currency_dataset/fake"))
```

This produces brightness, rotation, blur, noise, cropping, contrast and JPEG-compression variants.

## Train

Lightweight text baseline:

```bash
python -m ai.training.train_scam
```

Optional DistilBERT/IndicBERT:

```bash
python -m ai.training.train_transformer ai/datasets/scam_calls.csv ai/artifacts/scam_transformer
```

The evaluation helper writes accuracy, precision, recall, F1, ROC-AUC and a confusion-matrix image.

## API

The main FastAPI app exposes:

- `POST /ai/scam-detection`
- `POST /ai/currency-detection`
- `POST /ai/voice-analysis`
- `POST /ai/ocr`
- `GET /ai/fraud-network`
- `GET /ai/high-risk-nodes`
- `GET /ai/hotspots`
- `POST /ai/risk-score`
- `POST /ai/chat`

Every endpoint is authenticated and every predictive response uses the common shape:

```json
{
  "prediction": "Scam",
  "confidence": 98.4,
  "risk_score": 92,
  "explanation": ["Spoofed caller number (+24.0)"],
  "model_version": "v1.0"
}
```

## Production replacement

- Point `ScamDetectionPipeline` at a saved HuggingFace artifact.
- Replace the currency baseline with exported YOLO/ResNet weights.
- Configure EasyOCR and Whisper through the optional AI image.
- Move the filesystem `ModelRegistry` to MLflow or encrypted object storage.
- Connect graph ingestion to the existing Neo4j adapter.
- Implement the OpenAI, Gemini or Llama provider classes without changing assistant callers.

The AI Docker image is intentionally separate because Torch, Whisper and computer-vision dependencies are large. The standard API image retains lightweight baseline behavior.
