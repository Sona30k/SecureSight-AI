import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai.config import settings

SCAM_LINES = [
    "I am calling from CBI and your Aadhaar has been linked to money laundering.",
    "Do not disconnect the call or tell anyone about this investigation.",
    "Transfer all funds immediately to the verification account.",
    "A customs parcel in your name contains illegal items.",
    "A digital arrest warrant has been issued and police will arrive.",
]
NORMAL_LINES = [
    "Your grocery delivery will arrive between four and five.",
    "Can we move tomorrow's project meeting to the afternoon?",
    "The bank branch is closed today due to a public holiday.",
    "Please call me when you reach home safely.",
    "Your appointment is confirmed for next Monday.",
]
AUTHORITY_LINES = [
    "This is an officer from {agency}; your identity is under investigation.",
    "Your Aadhaar has been connected to a money laundering case.",
    "A parcel held by Customs contains prohibited documents in your name.",
]
COERCION_LINES = [
    "Do not disconnect this video call or discuss the case with anyone.",
    "Your bank account will be frozen and an arrest team will arrive today.",
    "Transfer money to the verification account immediately and share the OTP.",
]
DISTRICTS = {
    "Central Delhi": (28.632, 77.219), "Jaipur": (26.912, 75.787),
    "Mumbai": (19.076, 72.878), "Pune": (18.521, 73.857),
    "Lucknow": (26.847, 80.946), "Bengaluru": (12.972, 77.595),
    "Kolkata": (22.573, 88.364), "Chennai": (13.083, 80.271),
}
NODE_TYPES = ["Citizen", "Phone", "Device", "BankAccount", "UPI", "IPAddress", "Complaint", "Transaction"]


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def scam_calls(count: int = 5000, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        scam = rng.random() < .52
        lines = rng.sample(SCAM_LINES if scam else NORMAL_LINES, k=rng.randint(1, 3 if scam else 2))
        previous = rng.randint(1, 12) if scam and rng.random() < .6 else rng.randint(0, 1)
        spoof = scam and rng.random() < .68
        rows.append({
            "caller_number": f"+91{rng.randint(6000000000, 9999999999)}",
            "duration": rng.randint(30, 2400), "keywords": "|".join(x for x in ("cbi", "aadhaar", "transfer immediately", "digital arrest") if x in " ".join(lines).lower()),
            "transcript": " ".join(lines), "video_call": rng.random() < (.57 if scam else .04),
            "spoof_detected": spoof, "previous_reports": previous, "risk_label": int(scam),
        })
    return rows


def digital_arrest_calls(scam_count: int = 500, normal_count: int = 200, repeat_numbers: int = 100, seed: int = 47) -> list[dict]:
    """Create the documented evaluation set with exact class and repeat-caller counts."""
    rng = random.Random(seed)
    agencies = ["CBI", "ED", "Income Tax", "Customs", "Police"]
    cities = list(DISTRICTS)
    repeated = [f"+91{7800000000 + index}" for index in range(repeat_numbers)]
    rows = []
    for index in range(scam_count):
        caller = repeated[index % repeat_numbers] if index < repeat_numbers * 3 else f"+91{rng.randint(6000000000, 9999999999)}"
        transcript = " ".join([
            rng.choice(AUTHORITY_LINES).format(agency=rng.choice(agencies)),
            rng.choice(COERCION_LINES), rng.choice(COERCION_LINES),
        ])
        rows.append({
            "case_id": f"DA-S-{index:04}", "caller_number": caller, "transcript": transcript,
            "duration": rng.randint(180, 2400), "video_call": rng.random() < .72,
            "location": rng.choice(cities), "country": "India",
            "spoof_detected": rng.random() < .76, "previous_reports": rng.randint(1, 18),
            "risk_label": 1, "expected_stage": "Financial Demand",
        })
    for index in range(normal_count):
        rows.append({
            "case_id": f"DA-N-{index:04}", "caller_number": f"+91{rng.randint(6000000000, 9999999999)}",
            "transcript": " ".join(rng.sample(NORMAL_LINES, k=2)),
            "duration": rng.randint(20, 480), "video_call": False,
            "location": rng.choice(cities), "country": "India",
            "spoof_detected": False, "previous_reports": 0,
            "risk_label": 0, "expected_stage": "Introduction",
        })
    rng.shuffle(rows)
    return rows


def caller_reputations(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["caller_number"], []).append(row)
    return [{
        "caller_number": number, "reports": sum(item["risk_label"] for item in items),
        "average_risk": round(sum(88 if item["risk_label"] else 12 for item in items) / len(items), 1),
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "total_victims": sum(item["risk_label"] for item in items),
        "reputation_score": max(0, 100 - sum(item["risk_label"] for item in items) * 20),
    } for number, items in grouped.items()]


def fraud_reports(count: int = 3000, seed: int = 43) -> list[dict]:
    rng = random.Random(seed)
    categories = ["digital_arrest", "upi_fraud", "phishing", "counterfeit", "scam_call"]
    return [{"report_id": f"SX-{100000+i}", "category": rng.choice(categories), "district": rng.choice(list(DISTRICTS)), "amount": rng.randint(0, 800000), "risk_score": rng.randint(15, 99), "status": rng.choice(["submitted", "verified", "investigating", "resolved"])} for i in range(count)]


def counterfeit_cases(count: int = 2000, seed: int = 44) -> list[dict]:
    rng = random.Random(seed)
    return [{"case_id": f"CC-{i:05}", "denomination": rng.choice([100, 200, 500, 2000]), "security_thread": rng.random() > .28, "watermark": rng.random() > .24, "serial_valid": rng.random() > .2, "brightness": round(rng.uniform(.3, .8), 3), "blur": round(rng.random(), 3), "risk_label": int(rng.random() < .36)} for i in range(count)]


def crime_geojson(count: int = 10000, seed: int = 45) -> dict:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    features = []
    crime_risk = {"Digital Arrest": 22, "UPI Fraud": 17, "Phishing": 12, "Counterfeit": 10, "Scam Call": 14}
    district_risk = {name: index * 3 for index, name in enumerate(DISTRICTS)}
    for index in range(count):
        district = rng.choice(list(DISTRICTS))
        lat, lon = DISTRICTS[district]
        timestamp = now - timedelta(hours=rng.randint(0, 24 * 365))
        crime_type = rng.choice(list(crime_risk))
        evening_risk = 14 if timestamp.hour >= 18 or timestamp.hour < 2 else 0
        risk_score = round(max(5, min(99, 25 + district_risk[district] + crime_risk[crime_type] + evening_risk + rng.gauss(0, 7))))
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon + rng.gauss(0, .025), lat + rng.gauss(0, .025)]}, "properties": {"id": index, "crime_type": crime_type, "timestamp": timestamp.isoformat(), "district": district, "risk_score": risk_score}})
    return {"type": "FeatureCollection", "features": features}


def fraud_network(nodes: int = 3000, networks: int = 500, seed: int = 46) -> dict:
    rng = random.Random(seed)
    node_items = [{"id": f"N{i:05}", "type": rng.choice(NODE_TYPES), "label": f"{rng.choice(NODE_TYPES)} {i}", "risk_score": rng.randint(5, 99), "cluster_id": f"C{rng.randint(1, networks):04}"} for i in range(nodes)]
    edges = []
    relations = ["CALLED", "TRANSFERRED", "USES", "CONNECTED_TO", "HAS_DEVICE", "APPEARED_IN"]
    by_cluster: dict[str, list[dict]] = {}
    for node in node_items:
        by_cluster.setdefault(node["cluster_id"], []).append(node)
    for members in by_cluster.values():
        for node in members[1:]:
            edges.append({"source": members[0]["id"], "target": node["id"], "type": rng.choice(relations), "amount": rng.randint(0, 500000)})
        if len(members) > 2:
            edges.append({"source": members[1]["id"], "target": members[-1]["id"], "type": rng.choice(relations), "amount": rng.randint(0, 500000)})
    return {"nodes": node_items, "edges": edges, "network_count": networks}


def generate_all(output: Path = settings.datasets_dir) -> dict[str, int]:
    output.mkdir(parents=True, exist_ok=True)
    digital_arrest = digital_arrest_calls()
    _write_csv(output / "scam_calls.csv", scam_calls())
    _write_csv(output / "digital_arrest_calls.csv", digital_arrest)
    _write_csv(output / "caller_reputations.csv", caller_reputations(digital_arrest))
    _write_csv(output / "fraud_reports.csv", fraud_reports())
    _write_csv(output / "counterfeit_cases.csv", counterfeit_cases())
    (output / "crime_incidents.geojson").write_text(json.dumps(crime_geojson()), encoding="utf-8")
    (output / "fraud_network.json").write_text(json.dumps(fraud_network()), encoding="utf-8")
    manifest = {
        "scam_calls": 5000, "digital_arrest_scam_calls": 500,
        "digital_arrest_normal_calls": 200, "digital_arrest_repeat_numbers": 100,
        "caller_reputations": len(caller_reputations(digital_arrest)),
        "fraud_reports": 3000, "counterfeit_cases": 2000,
        "crime_incidents": 10000, "fraud_network_nodes": 3000, "fraud_networks": 500,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=settings.datasets_dir)
    args = parser.parse_args()
    print(json.dumps(generate_all(args.output), indent=2))
