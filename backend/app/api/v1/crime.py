from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_db
from app.models import CrimeLocation
from app.realtime import hub
from app.schemas import CrimeCreate

router = APIRouter(prefix="/crime", tags=["Crime Intelligence & Heatmap"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/report", status_code=201)
async def report_crime(payload: CrimeCreate, user: CurrentUser, db: DB):
    item = CrimeLocation(
        latitude=payload.latitude, longitude=payload.longitude, district=payload.district,
        crime_type=payload.crime_type, occurred_at=payload.timestamp,
        description=payload.description, risk_score=payload.risk_score, reported_by=user.id,
    )
    db.add(item)
    await db.commit()
    await hub.broadcast("heatmap", "crime.reported", {"id": str(item.id), "district": item.district, "risk_score": item.risk_score})
    return {"id": item.id, "status": "reported"}


def _filters(district: str | None, crime_type: str | None, start: datetime | None, end: datetime | None):
    result = []
    if district: result.append(CrimeLocation.district == district)
    if crime_type: result.append(CrimeLocation.crime_type == crime_type)
    if start: result.append(CrimeLocation.occurred_at >= start)
    if end: result.append(CrimeLocation.occurred_at <= end)
    return result


@router.get("/heatmap")
async def heatmap(
    user: CurrentUser, db: DB, district: str | None = None, crime_type: str | None = None,
    start: datetime | None = None, end: datetime | None = None,
):
    items = (await db.scalars(select(CrimeLocation).where(*_filters(district, crime_type, start, end)).limit(5000))).all()
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [x.longitude, x.latitude]},
        "properties": {"id": str(x.id), "district": x.district, "crime_type": x.crime_type, "risk_score": x.risk_score, "timestamp": x.occurred_at.isoformat()},
    } for x in items]}


@router.get("/hotspots")
async def hotspots(user: CurrentUser, db: DB, limit: int = Query(10, ge=1, le=100)):
    rows = (await db.execute(
        select(CrimeLocation.district, func.count().label("incidents"), func.avg(CrimeLocation.risk_score).label("risk"))
        .group_by(CrimeLocation.district).order_by(desc("risk")).limit(limit)
    )).all()
    return [{"district": row.district, "incidents": row.incidents, "predicted_risk": round(float(row.risk), 1)} for row in rows]


@router.get("/statistics")
async def statistics(user: CurrentUser, db: DB):
    total = await db.scalar(select(func.count(CrimeLocation.id))) or 0
    by_type = (await db.execute(select(CrimeLocation.crime_type, func.count()).group_by(CrimeLocation.crime_type))).all()
    return {"total_incidents": total, "by_crime_type": [{"crime_type": x[0], "count": x[1]} for x in by_type]}
