"""Request logging middleware for the LabClaw API."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("labclaw.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every API request with method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response  # type: ignore[no-any-return]
