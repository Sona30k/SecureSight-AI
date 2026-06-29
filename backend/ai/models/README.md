# Model artifacts

Saved checkpoints are intentionally excluded from source control. Inference resolves artifacts from `ai/artifacts/`.

- `scam_baseline.pkl`: TF-IDF + logistic regression baseline
- `scam_transformer/`: DistilBERT or IndicBERT HuggingFace checkpoint
- `currency_v1/`: YOLOv8 training output or exported ResNet50
- `hotspot_rf.pkl`: random-forest hotspot regressor

Every provider has a deterministic fallback, so API development does not require model downloads.
