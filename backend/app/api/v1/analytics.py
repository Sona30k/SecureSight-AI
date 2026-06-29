from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_roles
from app.database import get_db
from app.models import CounterfeitCase, CrimeLocation, DigitalArrestCase, FraudReport, User, UserRole

router = APIRouter(prefix="/analytics", tags=["Analytics"])
AnalyticsUser = Annotated[
    User,
    Depends(require_roles(UserRole.police, UserRole.bank, UserRole.telecom_provider)),
]


@router.get("/dashboard")
async def dashboard(user: AnalyticsUser, db: Annotated[AsyncSession, Depends(get_db)]):
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = today - timedelta(days=29)
    today_frauds = await db.scalar(select(func.count(FraudReport.id)).where(FraudReport.created_at >= today)) or 0
    counterfeit = await db.scalar(select(func.count(CounterfeitCase.id)).where(CounterfeitCase.prediction == "Fake")) or 0
    money_saved = await db.scalar(select(func.sum(FraudReport.money_involved)).where(FraudReport.status == "resolved")) or 0
    trends = (await db.execute(
        select(func.date(FraudReport.created_at).label("date"), func.count().label("count"))
        .where(FraudReport.created_at >= month).group_by(func.date(FraudReport.created_at)).order_by("date")
    )).all()
    districts = (await db.execute(
        select(CrimeLocation.district, func.count().label("incidents"))
        .group_by(CrimeLocation.district).order_by(func.count().desc()).limit(10)
    )).all()
    risks = (await db.execute(
        select(
            func.sum(case((FraudReport.risk_score < 30, 1), else_=0)).label("low"),
            func.sum(case((FraudReport.risk_score.between(30, 59), 1), else_=0)).label("medium"),
            func.sum(case((FraudReport.risk_score.between(60, 79), 1), else_=0)).label("high"),
            func.sum(case((FraudReport.risk_score >= 80, 1), else_=0)).label("critical"),
        )
    )).one()
    return {
        "today_frauds": today_frauds,
        "monthly_trends": [{"date": str(x.date), "count": x.count} for x in trends],
        "counterfeit_detected": counterfeit,
        "money_saved": float(money_saved),
        "district_rankings": [{"district": x.district, "incidents": x.incidents} for x in districts],
        "risk_distribution": {k: int(getattr(risks, k) or 0) for k in ("low", "medium", "high", "critical")},
        "digital_arrest_cases": await db.scalar(select(func.count(DigitalArrestCase.id))) or 0,
    }
