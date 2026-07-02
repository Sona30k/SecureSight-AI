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
            db.add_all([
                CrimeLocation(latitude=28.6315, longitude=77.2167, district="Central Delhi", crime_type="Digital Arrest", occurred_at=datetime.now(timezone.utc), risk_score=94, reported_by=admin.id),
                CrimeLocation(latitude=26.9124, longitude=75.7873, district="Jaipur", crime_type="UPI Fraud", occurred_at=datetime.now(timezone.utc)-timedelta(hours=3), risk_score=76, reported_by=admin.id),
            ])
        await db.commit()
    print("Demo seed complete. Accounts use password ShieldIQ!2026; disable DEMO_MODE outside hackathon environments.")


if __name__ == "__main__":
    asyncio.run(seed())
