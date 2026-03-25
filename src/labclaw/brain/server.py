"""Cloud Brain REST API — FastAPI server for scientific tool execution."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

import labclaw.brain as brain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_MAX_REQUEST_BODY = 1 * 1024 * 1024  # 1 MB
_MAX_RESPONSE_SIZE = 100 * 1024  # 100 KB
_RATE_LIMIT = os.environ.get("LABCLAW_RATE_LIMIT", "60/minute")

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ExecuteRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = {}


class ReasonRequest(BaseModel):
    question: str
    domain: str = "general"
    context: str = ""


class WriteRequest(BaseModel):
    section: str
    context: str


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_api_keys: set[str] | None = None


def _load_api_keys() -> set[str] | None:
    """Load API keys from LABCLAW_API_KEYS env var (comma-separated)."""
    global _api_keys
    if _api_keys is not None:
        return _api_keys if _api_keys else None
    raw = os.environ.get("LABCLAW_API_KEYS", "")
    if raw.strip():
        _api_keys = {k.strip() for k in raw.split(",") if k.strip()}
    else:
        _api_keys = set()
    return _api_keys if _api_keys else None


def _reset_api_keys() -> None:
    """Reset cached API keys (for testing)."""
    global _api_keys
    _api_keys = None


async def verify_api_key(request: Request) -> None:
    """Verify X-API-Key header when keys are configured."""
    keys = _load_api_keys()
    if keys is None:
        return  # No keys configured — allow anonymous
    provided = request.headers.get("X-API-Key", "")
    if provided not in keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Cloud Brain", description="2400+ scientific tools", version="0.0.1")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )


# ---------------------------------------------------------------------------
# Middleware: request body size limit
# ---------------------------------------------------------------------------


@app.middleware("http")
async def _limit_request_body(request: Request, call_next: Any) -> Response:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_REQUEST_BODY:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Response truncation helper
# ---------------------------------------------------------------------------


def _truncate_response(data: Any) -> Any:
    """Truncate response data if serialized size exceeds limit."""
    serialized = json.dumps(data, default=str)
    if len(serialized.encode()) > _MAX_RESPONSE_SIZE:
        return {
            "truncated": True,
            "message": f"Response truncated (>{_MAX_RESPONSE_SIZE} bytes)",
            "data": serialized[:_MAX_RESPONSE_SIZE].rstrip(),
        }
    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/brain/health")
@limiter.limit(_RATE_LIMIT)
async def get_health(request: Request) -> dict:
    """Check Cloud Brain health."""
    status = await brain.health()
    return status.model_dump()


@app.get("/brain/tools")
@limiter.limit(_RATE_LIMIT)
async def get_tools(request: Request, category: str = "") -> list:
    """List available tools, optionally filtered by category."""
    tools = await brain.list_tools(category=category)
    result = [t.model_dump() for t in tools]
    return _truncate_response(result)


@app.post("/brain/execute", dependencies=[Depends(verify_api_key)])
@limiter.limit(_RATE_LIMIT)
async def post_execute(request: Request, body: ExecuteRequest) -> dict:
    """Execute a scientific tool by name."""
    result = await brain.execute(body.tool_name, **body.arguments)
    return _truncate_response(result.model_dump())


@app.post("/brain/reason", dependencies=[Depends(verify_api_key)])
@limiter.limit(_RATE_LIMIT)
async def post_reason(request: Request, body: ReasonRequest) -> dict:
    """Life science domain reasoning."""
    result = await brain.reason(body.question, domain=body.domain, context=body.context)
    return _truncate_response(result.model_dump())


@app.post("/brain/write", dependencies=[Depends(verify_api_key)])
@limiter.limit(_RATE_LIMIT)
async def post_write(request: Request, body: WriteRequest) -> dict:
    """Generate a scientific writing section."""
    result = await brain.write(section=body.section, context=body.context)
    return _truncate_response(result.model_dump())
