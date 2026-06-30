from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_roles
from app.database import get_db
from app.models import CounterfeitCase, CrimeLocation, DigitalArrestCase, FraudReport, ReportStatus, User, UserRole

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
    totals = (await db.execute(select(
        func.count(FraudReport.id).filter(FraudReport.created_at >= today).label("today_frauds"),
        func.coalesce(func.sum(FraudReport.money_involved).filter(FraudReport.status == ReportStatus.resolved), 0).label("money_saved"),
        func.count(FraudReport.id).filter(FraudReport.status.in_([ReportStatus.assigned, ReportStatus.investigating])).label("active_investigations"),
        func.count(FraudReport.id.distinct()).filter(FraudReport.status == ReportStatus.resolved).label("protected_citizens"),
    ))).one()
    case_totals = (await db.execute(select(
        select(func.count(CounterfeitCase.id)).where(CounterfeitCase.prediction == "Fake").scalar_subquery().label("counterfeit"),
        select(func.count(DigitalArrestCase.id)).where(DigitalArrestCase.risk_score >= 75).scalar_subquery().label("high_risk_calls"),
        select(func.count(DigitalArrestCase.id)).scalar_subquery().label("digital_arrest_cases"),
    ))).one()
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
    recent = (await db.scalars(select(FraudReport).order_by(FraudReport.created_at.desc()).limit(6))).all()
    return {
        "today_frauds": totals.today_frauds,
        "monthly_trends": [{"date": str(x.date), "count": x.count} for x in trends],
        "counterfeit_detected": case_totals.counterfeit,
        "money_saved": float(totals.money_saved),
        "active_investigations": totals.active_investigations,
        "protected_citizens": totals.protected_citizens,
        "high_risk_calls": case_totals.high_risk_calls,
        "district_rankings": [{"district": x.district, "incidents": x.incidents} for x in districts],
        "risk_distribution": {k: int(getattr(risks, k) or 0) for k in ("low", "medium", "high", "critical")},
        "digital_arrest_cases": case_totals.digital_arrest_cases,
        "recent_reports": [
            {"id": str(item.id), "title": item.title, "category": item.category, "status": item.status.value, "risk_score": item.risk_score, "created_at": item.created_at.isoformat()}
            for item in recent
        ],
    }
