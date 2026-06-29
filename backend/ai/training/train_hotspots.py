import json
import pickle
from pathlib import Path


def train(dataset: Path, output: Path) -> dict:
    try:
        import pandas as pd
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise RuntimeError("Install pandas and scikit-learn") from exc
    payload = json.loads(dataset.read_text())
    rows = [{"lat": x["geometry"]["coordinates"][1], "lon": x["geometry"]["coordinates"][0], "hour": __import__("datetime").datetime.fromisoformat(x["properties"]["timestamp"]).hour, "risk": x["properties"]["risk_score"]} for x in payload["features"]]
    frame = pd.DataFrame(rows)
    train_x, test_x, train_y, test_y = train_test_split(frame[["lat", "lon", "hour"]], frame["risk"], test_size=.2, random_state=42)
    model = RandomForestRegressor(
        n_estimators=60, max_depth=10, min_samples_leaf=3,
        random_state=42, n_jobs=-1,
    ).fit(train_x, train_y)
    prediction = model.predict(test_x)
    metrics = {"mae": mean_absolute_error(test_y, prediction), "r2": r2_score(test_y, prediction)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        pickle.dump(model, handle)
    output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics
