from collections import Counter
from datetime import timezone
from typing import Any

from faker import Faker
from sqlalchemy import and_, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CrimeLocation, User

SYNTHETIC_MARKER = "[SYNTHETIC:city-cluster-v1]"
LEGACY_DESCRIPTION = "Synthetic hackathon demonstration record; replace with an authorized GIS feed."
LEGACY_POINTS = (
    ("Central Delhi", 28.6315, 77.2167, 94),
    ("Jaipur", 26.9124, 75.7873, 76),
)
INCIDENTS_PER_CITY = 1_500

CITY_HOTSPOTS: dict[str, tuple[tuple[str, float, float, int], ...]] = {
    "Delhi": (
        ("Connaught Place", 28.6315, 77.2167, 84),
        ("Rohini", 28.7495, 77.0565, 72),
        ("Dwarka", 28.5921, 77.0460, 77),
        ("Saket", 28.5245, 77.2066, 68),
    ),
    "Mumbai": (
        ("Andheri", 19.1136, 72.8697, 86),
        ("Bandra", 19.0596, 72.8295, 74),
        ("Dadar", 19.0178, 72.8478, 79),
        ("Powai", 19.1176, 72.9060, 70),
    ),
    "Bangalore": (
        ("MG Road", 12.9756, 77.6063, 78),
        ("Whitefield", 12.9698, 77.7500, 83),
        ("Koramangala", 12.9352, 77.6245, 72),
        ("Yeshwanthpur", 13.0285, 77.5463, 69),
    ),
    "Hyderabad": (
        ("Hitech City", 17.4435, 78.3772, 85),
        ("Banjara Hills", 17.4126, 78.4347, 73),
        ("Secunderabad", 17.4399, 78.4983, 77),
        ("Gachibowli", 17.4401, 78.3489, 81),
    ),
    "Chennai": (
        ("T Nagar", 13.0418, 80.2341, 82),
        ("Anna Nagar", 13.0850, 80.2101, 71),
        ("Velachery", 12.9815, 80.2180, 76),
        ("Guindy", 13.0067, 80.2206, 69),
    ),
}

CRIME_TYPES = (
    "Digital Arrest",
    "UPI Fraud",
    "Bank Impersonation",
    "Investment Scam",
    "Phishing",
    "OTP Fraud",
    "Job Scam",
    "Counterfeit Currency",
)


def build_city_incidents(seed: int = 20260706) -> list[dict[str, Any]]:
    """Generate deterministic city-scale data concentrated around known synthetic hotspots."""
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    records: list[dict[str, Any]] = []
    for city, hotspots in CITY_HOTSPOTS.items():
        for index in range(INCIDENTS_PER_CITY):
            hotspot, center_latitude, center_longitude, base_risk = fake.random_element(hotspots)
            broad_point = fake.random_int(1, 100) <= 8
            deviation = .055 if broad_point else .012
            latitude = fake.random.gauss(center_latitude, deviation)
            longitude = fake.random.gauss(center_longitude, deviation)
            crime_type = fake.random_element(CRIME_TYPES)
            type_adjustment = {
                "Digital Arrest": 8,
                "Investment Scam": 6,
                "Counterfeit Currency": 4,
                "Phishing": -5,
            }.get(crime_type, 0)
            risk_score = max(25, min(99, base_risk + type_adjustment + fake.random_int(-14, 12)))
            records.append({
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "district": city,
                "crime_type": crime_type,
                "occurred_at": fake.date_time_between(
                    start_date="-180d", end_date="now", tzinfo=timezone.utc,
                ),
                "description": (
                    f"{SYNTHETIC_MARKER} {hotspot}: synthetic {crime_type.lower()} "
                    "incident generated for map clustering and demonstration."
                ),
                "risk_score": risk_score,
            })
    return records


async def seed_city_incidents(db: AsyncSession, admin: User) -> dict[str, Any]:
    # Clean up the superseded 20-record demo even on idempotent reruns.
    legacy_points = or_(*(
        and_(
            CrimeLocation.district == district,
            CrimeLocation.latitude == latitude,
            CrimeLocation.longitude == longitude,
            CrimeLocation.risk_score == risk_score,
            CrimeLocation.description.is_(None),
        )
        for district, latitude, longitude, risk_score in LEGACY_POINTS
    ))
    await db.execute(delete(CrimeLocation).where(
        (CrimeLocation.description == LEGACY_DESCRIPTION) | legacy_points
    ))
    existing = await db.scalar(
        select(func.count(CrimeLocation.id)).where(CrimeLocation.description.like(f"{SYNTHETIC_MARKER}%"))
    ) or 0
    target = INCIDENTS_PER_CITY * len(CITY_HOTSPOTS)
    if existing >= target:
        await db.commit()
        return {"created": False, "incidents": existing, "cities": len(CITY_HOTSPOTS)}

    records = build_city_incidents()
    for record in records:
        record["reported_by"] = admin.id
    await db.execute(insert(CrimeLocation), records)
    await db.commit()
    counts = Counter(record["district"] for record in records)
    return {
        "created": True,
        "incidents": len(records),
        "cities": len(counts),
        "per_city": dict(counts),
    }
