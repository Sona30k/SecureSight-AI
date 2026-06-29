import json
from pathlib import Path


def classification_report(y_true, probabilities, output: Path) -> dict:
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
    predictions = (probabilities >= .5).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y_true, predictions)), "precision": float(precision_score(y_true, predictions)),
        "recall": float(recall_score(y_true, predictions)), "f1": float(f1_score(y_true, predictions)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
    }
    output.mkdir(parents=True, exist_ok=True)
    ConfusionMatrixDisplay.from_predictions(y_true, predictions)
    plt.tight_layout()
    plt.savefig(output / "confusion_matrix.png", dpi=160)
    plt.close()
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics
