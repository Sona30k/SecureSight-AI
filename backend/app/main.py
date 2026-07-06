from contextlib import asynccontextmanager
from uuid import UUID

import redis.asyncio as redis
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import select, text, update
from starlette.responses import Response

from app.api.v1.router import api_router
from app.config.settings import settings
from app.auth.security import decode_token
from app.database import AsyncSessionLocal, engine
from app.graph import Neo4jClient
from app.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.models import SpeechStream, User
from app.realtime import hub
from app.schemas import HealthResponse
from app.utils.logging import configure_logging

configure_logging()
REQUESTS = Counter("shieldiq_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("shieldiq_http_request_duration_seconds", "Request duration", ["path"])
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(SpeechStream)
            .where(SpeechStream.status == "active")
            .values(status="abandoned")
        )
        await db.commit()
    yield
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered public safety intelligence for citizens, agencies, banks and telecom providers.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID", "X-Response-Time-MS"],
)


@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    route_path = request.url.path
    with LATENCY.labels(route_path).time():
        response = await call_next(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", route_path)
    REQUESTS.labels(request.method, route_path, response.status_code).inc()
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={
        "error": "internal_server_error", "message": "An unexpected error occurred",
        "request_id": request.headers.get("x-request-id"),
    })


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={
        "error": "validation_error",
        "message": "The request contains invalid data",
        "details": jsonable_encoder(exc.errors()),
        "request_id": request.headers.get("x-request-id"),
    })


@app.get("/", tags=["System"])
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health(request: Request):
    services = {
        "api": "healthy", "database": "unavailable",
        "redis": "unavailable", "neo4j": "unavailable",
    }
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception:
        pass
    try:
        if await request.app.state.redis.ping():
            services["redis"] = "healthy"
    except Exception:
        pass
    graph = Neo4jClient()
    try:
        if await graph.verify():
            services["neo4j"] = "healthy"
    finally:
        await graph.close()
    overall = "healthy" if services["database"] == "healthy" else "degraded"
    return HealthResponse(status=overall, version=settings.app_version, environment=settings.environment, services=services)


@app.get("/metrics", tags=["System"], include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.websocket("/ws/{channel}")
async def websocket_updates(websocket: WebSocket, channel: str, token: str):
    if channel not in {"dashboard", "alerts", "reports", "graph", "heatmap", "digital-arrest", "speech"}:
        await websocket.close(code=4404)
        return
    try:
        payload = decode_token(token)
        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.id == UUID(payload["sub"]), User.is_active.is_(True)))
        if not user or user.token_version != payload.get("ver"):
            raise ValueError
    except (ValueError, TypeError):
        await websocket.close(code=4401)
        return
    await hub.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(channel, websocket)


app.include_router(api_router)
