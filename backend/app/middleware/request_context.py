import time
from uuid import UUID
from uuid import uuid4

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.security import decode_token
from app.database import AsyncSessionLocal
from app.models import AuditLog

logger = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed", request_id=request_id, path=request.url.path)
            raise
        duration = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-MS"] = str(duration)
        logger.info("request_completed", request_id=request_id, method=request.method, path=request.url.path, status=response.status_code, duration_ms=duration)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.url.path.startswith("/auth"):
            try:
                authorization = request.headers.get("authorization", "")
                payload = decode_token(authorization.removeprefix("Bearer ").strip()) if authorization.startswith("Bearer ") else {}
                user_id = UUID(payload["sub"]) if payload.get("sub") else None
                resource = request.url.path.strip("/").split("/", 1)[0] or "system"
                async with AsyncSessionLocal() as db:
                    db.add(AuditLog(
                        user_id=user_id,
                        action=f"http.{request.method.lower()}",
                        status="success" if response.status_code < 400 else "failure",
                        resource=resource,
                        resource_id=request.url.path[:100],
                        ip_address=request.client.host if request.client else None,
                        details={
                            "path": request.url.path,
                            "status_code": response.status_code,
                            "request_id": request_id,
                            "duration_ms": duration,
                        },
                    ))
                    await db.commit()
            except Exception:
                logger.warning("audit_write_failed", request_id=request_id, path=request.url.path)
        return response
