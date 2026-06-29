from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_roles
from app.graph import Neo4jClient
from app.models import User, UserRole
from app.schemas import GraphReport

router = APIRouter(prefix="/graph", tags=["Fraud Network Graph"])
GraphUser = Annotated[
    User,
    Depends(require_roles(UserRole.police, UserRole.bank, UserRole.telecom_provider)),
]


async def _client() -> Neo4jClient:
    return Neo4jClient()


@router.post("/create-report", status_code=201)
async def create_graph_report(payload: GraphReport, user: GraphUser):
    client = await _client()
    try:
        return await client.create_report(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Graph database is unavailable") from exc
    finally:
        await client.close()


@router.get("/network/{case_id}")
async def network(case_id: str, user: GraphUser):
    client = await _client()
    try:
        return await client.network(case_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Graph database is unavailable") from exc
    finally:
        await client.close()


@router.get("/cluster/{cluster_id}")
async def cluster(cluster_id: str, user: GraphUser):
    client = await _client()
    try:
        return await client.network(cluster_id)
    finally:
        await client.close()


@router.get("/high-risk")
async def high_risk(user: GraphUser, minimum: int = Query(70, ge=0, le=100)):
    client = await _client()
    try:
        return {"items": await client.high_risk(minimum)}
    finally:
        await client.close()
