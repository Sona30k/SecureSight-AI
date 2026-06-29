import argparse
import json
import pickle
from pathlib import Path

from ai.config import settings
from ai.utils.lazy_imports import optional_import


def train(dataset: Path, output: Path) -> dict:
    pd, sklearn = optional_import("pandas"), optional_import("sklearn")
    if not pd or not sklearn:
        raise RuntimeError("Install pandas and scikit-learn to train the baseline")
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import FeatureUnion, Pipeline

    frame = pd.read_csv(dataset)
    train_x, test_x, train_y, test_y = train_test_split(frame["transcript"], frame["risk_label"], test_size=.2, stratify=frame["risk_label"], random_state=42)
    model = Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=25_000)), ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced"))])
    model.fit(train_x, train_y)
    probabilities = model.predict_proba(test_x)[:, 1]
    predictions = (probabilities >= .5).astype(int)
    metrics = {
        "accuracy": accuracy_score(test_y, predictions), "precision": precision_score(test_y, predictions),
        "recall": recall_score(test_y, predictions), "f1": f1_score(test_y, predictions),
        "roc_auc": roc_auc_score(test_y, probabilities),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        pickle.dump(model, handle)
    output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2))
    try:
        import matplotlib.pyplot as plt
        ConfusionMatrixDisplay.from_predictions(test_y, predictions, display_labels=["Safe", "Scam"])
        plt.tight_layout()
        plt.savefig(output.with_name(f"{output.stem}_confusion_matrix.png"), dpi=160)
        plt.close()
    except ImportError:
        pass
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=settings.datasets_dir / "scam_calls.csv")
    parser.add_argument("--output", type=Path, default=settings.artifacts_dir / "scam_baseline.pkl")
    args = parser.parse_args()
    print(train(args.dataset, args.output))
