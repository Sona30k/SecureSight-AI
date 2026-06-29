import time
from uuid import uuid4

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

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
        return response
