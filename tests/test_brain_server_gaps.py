"""Cover brain/server.py uncovered lines 68, 104, 120, 133.

Line 68:   _load_api_keys returns None for cached empty set.
Line 104:  Rate limit exceeded handler returns 429.
Line 120:  Request body too large returns 413.
Line 133:  Response truncation when serialized > 100KB.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from labclaw.brain.server import _reset_api_keys, _truncate_response, app
from labclaw.brain.types import HealthStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_state():
    import labclaw.brain as brain_mod

    brain_mod._registry = None
    _reset_api_keys()
    yield
    brain_mod._registry = None
    _reset_api_keys()


@pytest.fixture()
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _mock_brain_health():
    return patch(
        "labclaw.brain.server.brain.health",
        new_callable=AsyncMock,
        return_value=HealthStatus(status="ok", skills={}, tool_count=0, version="0.0.1"),
    )


# ---------------------------------------------------------------------------
# Line 68: cached empty _api_keys set returns None
# ---------------------------------------------------------------------------


class TestCachedEmptyApiKeys:
    """When _api_keys was previously loaded as empty set, returns None."""

    async def test_cached_empty_set_allows_anonymous(self, client, monkeypatch):
        # First call: load empty env (no keys configured)
        monkeypatch.delenv("LABCLAW_API_KEYS", raising=False)
        _reset_api_keys()

        from labclaw.brain.server import _load_api_keys

        first = _load_api_keys()
        assert first is None  # empty env => None

        # Second call: hits the cached empty-set branch (line 68)
        second = _load_api_keys()
        assert second is None  # cached empty set => None

        # Verify request goes through without auth
        with _mock_brain_health():
            resp = await client.get("/brain/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Line 104: rate limit exceeded handler
# ---------------------------------------------------------------------------


class TestRateLimitHandler:
    """The _rate_limit_handler returns proper 429 with Retry-After header."""

    async def test_rate_limit_handler_returns_429(self, client):
        from limits import parse
        from slowapi.errors import RateLimitExceeded
        from slowapi.wrappers import Limit

        from labclaw.brain.server import _rate_limit_handler

        lim = Limit(
            limit=parse("60/minute"),
            key_func=lambda: "test",
            scope=None,
            per_method=False,
            methods=None,
            error_message=None,
            exempt_when=None,
            cost=1,
            override_defaults=False,
        )
        exc = RateLimitExceeded(lim)
        request = type("FakeRequest", (), {})()

        response = await _rate_limit_handler(request, exc)  # type: ignore[arg-type]

        assert response.status_code == 429
        body = json.loads(response.body)
        assert body["detail"] == "Rate limit exceeded"
        assert "Retry-After" in response.headers


# ---------------------------------------------------------------------------
# Line 120: request body too large middleware
# ---------------------------------------------------------------------------


class TestRequestBodyTooLarge:
    """Middleware returns 413 when Content-Length exceeds limit."""

    async def test_rejects_oversized_request_body(self, client):
        with _mock_brain_health():
            resp = await client.get(
                "/brain/health",
                headers={"content-length": "9999999999"},
            )
        assert resp.status_code == 413
        assert resp.json()["detail"] == "Request body too large"


# ---------------------------------------------------------------------------
# Line 133: response truncation
# ---------------------------------------------------------------------------


class TestResponseTruncation:
    """_truncate_response truncates when serialized size > _MAX_RESPONSE_SIZE."""

    def test_truncates_large_response(self):
        large_data = [{"data": "x" * 1000} for _ in range(200)]
        result = _truncate_response(large_data)

        assert isinstance(result, dict)
        assert result["truncated"] is True
        assert "message" in result
