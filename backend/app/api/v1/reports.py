import math
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_db
from app.models import FraudReport, UserRole
from app.schemas import Paginated, ReportCreate, ReportRead, ReportUpdate

router = APIRouter(prefix="/reports", tags=["Citizen Fraud Reports"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=ReportRead, status_code=201)
async def create_report(payload: ReportCreate, user: CurrentUser, db: DB):
    report = FraudReport(**payload.model_dump(), reporter_id=user.id)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


@router.get("", response_model=Paginated[ReportRead])
async def list_reports(
    user: CurrentUser, db: DB, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str | None = None, category: str | None = None, status: str | None = None,
    sort_by: Literal["created_at", "risk_score", "title"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
):
    filters = []
    if user.role == UserRole.citizen:
        filters.append(FraudReport.reporter_id == user.id)
    if search:
        filters.append(or_(FraudReport.title.ilike(f"%{search}%"), FraudReport.description.ilike(f"%{search}%")))
    if category:
        filters.append(FraudReport.category == category)
    if status:
        filters.append(FraudReport.status == status)
    total = await db.scalar(select(func.count(FraudReport.id)).where(*filters)) or 0
    column = getattr(FraudReport, sort_by)
    order = asc(column) if sort_order == "asc" else desc(column)
    items = (await db.scalars(select(FraudReport).where(*filters).order_by(order).offset((page - 1) * page_size).limit(page_size))).all()
    return Paginated(items=list(items), total=total, page=page, page_size=page_size, pages=math.ceil(total / page_size))


async def _get_visible(report_id: UUID, user: CurrentUser, db: AsyncSession) -> FraudReport:
    report = await db.get(FraudReport, report_id)
    if not report or (user.role == UserRole.citizen and report.reporter_id != user.id):
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}", response_model=ReportRead)
async def get_report(report_id: UUID, user: CurrentUser, db: DB):
    return await _get_visible(report_id, user, db)


@router.put("/{report_id}", response_model=ReportRead)
async def update_report(report_id: UUID, payload: ReportUpdate, user: CurrentUser, db: DB):
    report = await _get_visible(report_id, user, db)
    changes = payload.model_dump(exclude_unset=True)
    if user.role == UserRole.citizen:
        changes.pop("status", None)
        changes.pop("risk_score", None)
    for key, value in changes.items():
        setattr(report, key, value)
    await db.commit()
    await db.refresh(report)
    return report


@router.delete("/{report_id}", status_code=204)
async def delete_report(report_id: UUID, user: CurrentUser, db: DB):
    report = await _get_visible(report_id, user, db)
    await db.delete(report)
    await db.commit()
    return Response(status_code=204)
