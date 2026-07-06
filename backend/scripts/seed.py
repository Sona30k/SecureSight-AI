import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.auth.security import hash_password
from app.database import AsyncSessionLocal
from app.models import AccountStatus, CrimeLocation, FraudReport, ReportStatus, User, UserRole


async def seed():
    async with AsyncSessionLocal() as db:
        demo_users = [
            ("citizen@shieldiq.demo", "Demo Citizen", UserRole.citizen),
            ("police@shieldiq.demo", "Demo Police Officer", UserRole.police),
            ("bank@shieldiq.demo", "Demo Bank Analyst", UserRole.bank),
            ("telecom@shieldiq.demo", "Demo Telecom Analyst", UserRole.telecom_provider),
            ("admin@shieldiq.gov.in", "ShieldIQ Administrator", UserRole.administrator),
        ]
        admin = None
        for email, full_name, role in demo_users:
            user = await db.scalar(select(User).where(User.email == email))
            if not user:
                user = User(
                    email=email, full_name=full_name, hashed_password=hash_password("ShieldIQ!2026"),
                    role=role, account_status=AccountStatus.verified, is_active=True,
                    email_verified=True, phone_verified=True,
                )
                db.add(user)
                await db.flush()
            if role == UserRole.administrator:
                admin = user
        assert admin is not None
        if not await db.scalar(select(FraudReport).limit(1)):
            db.add_all([
                FraudReport(title="CBI digital arrest attempt", description="Caller requested an urgent verification transfer and threatened arrest.", category="digital_arrest", location="Central Delhi", status=ReportStatus.investigating, risk_score=94, money_involved=240000, reporter_id=admin.id),
                FraudReport(title="Suspicious UPI collect request", description="Unknown merchant sent a collect request after a marketplace conversation.", category="upi_fraud", location="Jaipur", status=ReportStatus.resolved, risk_score=76, money_involved=48000, reporter_id=admin.id),
            ])
        demo_crimes = [
            ("Central Delhi", 28.6315, 77.2167, "Digital Arrest", 94),
            ("Jaipur", 26.9124, 75.7873, "UPI Fraud", 76),
            ("Mumbai", 19.0760, 72.8777, "Investment Scam", 88),
            ("Bengaluru Urban", 12.9716, 77.5946, "Phishing", 71),
            ("Kolkata", 22.5726, 88.3639, "Bank Impersonation", 83),
            ("Chennai", 13.0827, 80.2707, "Digital Arrest", 91),
            ("Hyderabad", 17.3850, 78.4867, "UPI Fraud", 79),
            ("Pune", 18.5204, 73.8567, "Job Scam", 66),
            ("Ahmedabad", 23.0225, 72.5714, "Investment Scam", 74),
            ("Lucknow", 26.8467, 80.9462, "OTP Fraud", 82),
            ("Patna", 25.5941, 85.1376, "Bank Impersonation", 69),
            ("Bhopal", 23.2599, 77.4126, "UPI Fraud", 73),
            ("Guwahati", 26.1445, 91.7362, "Digital Arrest", 86),
            ("Bhubaneswar", 20.2961, 85.8245, "Phishing", 64),
            ("Kochi", 9.9312, 76.2673, "Investment Scam", 77),
            ("Chandigarh", 30.7333, 76.7794, "OTP Fraud", 68),
            ("Ranchi", 23.3441, 85.3096, "Job Scam", 72),
            ("Raipur", 21.2514, 81.6296, "UPI Fraud", 67),
            ("Dehradun", 30.3165, 78.0322, "Bank Impersonation", 75),
            ("Srinagar", 34.0837, 74.7973, "Phishing", 62),
        ]
        existing_districts = set(await db.scalars(select(CrimeLocation.district)))
        now = datetime.now(timezone.utc)
        db.add_all([
            CrimeLocation(
                latitude=latitude, longitude=longitude, district=district,
                crime_type=crime_type, occurred_at=now - timedelta(minutes=index * 19),
                description="Synthetic hackathon demonstration record; replace with an authorized GIS feed.",
                risk_score=risk_score, reported_by=admin.id,
            )
            for index, (district, latitude, longitude, crime_type, risk_score) in enumerate(demo_crimes)
            if district not in existing_districts
        ])
        await db.commit()
    print("Demo seed complete. Accounts use password ShieldIQ!2026; disable DEMO_MODE outside hackathon environments.")


if __name__ == "__main__":
    asyncio.run(seed())
