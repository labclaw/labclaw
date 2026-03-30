"""Tests for Cloud Brain REST API server edge cases.

Covers: cached API key early return (line 68), rate limit handler (line 104),
request body size middleware (line 120), response truncation (lines 132-137).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from labclaw.brain.server import (
    _MAX_REQUEST_BODY,
    _MAX_RESPONSE_SIZE,
    _limit_request_body,
    _load_api_keys,
    _rate_limit_handler,
    _reset_api_keys,
    _truncate_response,
    app,
)


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


# ---------------------------------------------------------------------------
# Line 68: _load_api_keys cached early return
# ---------------------------------------------------------------------------


class TestApiKeyCacheHit:
    """Cover line 68: _api_keys already cached (the early return path)."""

    def test_cached_empty_set_returns_none(self) -> None:
        """When _api_keys is cached as empty set, _load_api_keys returns None."""
        import labclaw.brain.server as srv

        srv._api_keys = set()  # cached as empty set
        result = _load_api_keys()
        assert result is None

    def test_cached_nonempty_set_returns_keys(self) -> None:
        """When _api_keys is cached with values. _load_api_keys returns the set."""
        import labclaw.brain.server as srv

        srv._api_keys = {"key1", "key2"}
        result = _load_api_keys()
        assert result == {"key1", "key2"}


# ---------------------------------------------------------------------------
# Lines 104-108: _rate_limit_handler returns 429
# ---------------------------------------------------------------------------


class TestRateLimitHandler:
    """Cover lines 104-108: the rate limit exception handler."""

    async def test_rate_limit_handler_returns_429(self) -> None:
        """The _rate_limit_handler returns a 429 JSONResponse with Retry-After."""
        from slowapi.errors import RateLimitExceeded

        mock_request = MagicMock()
        # Create a proper RateLimitExceeded with a limit-like object
        fake_limit = type("L", (), {"error_message": None, "limit": "60/minute"})()
        exc = RateLimitExceeded(fake_limit)
        exc.retry_after = 60

        response = await _rate_limit_handler(mock_request, exc)
        assert response.status_code == 429
        body = json.loads(response.body.decode())
        assert body["detail"] == "Rate limit exceeded"
        assert response.headers.get("Retry-After") == "60"


# ---------------------------------------------------------------------------
# Line 120: request body size middleware
# ---------------------------------------------------------------------------


class TestRequestBodySizeLimit:
    """Cover line 120: _limit_request_body rejects oversized requests."""

    async def test_body_size_middleware_rejects_large(self) -> None:
        """Direct test of _limit_request_body middleware with large body."""
        mock_request = MagicMock()
        mock_request.headers = {"content-length": str(_MAX_REQUEST_BODY + 1)}
        mock_request.get = lambda k, d="": mock_request.headers.get(k, d)

        response = await _limit_request_body(mock_request, lambda r: None)
        assert response.status_code == 413
        body = json.loads(response.body.decode())
        assert "too large" in body["detail"].lower()

    async def test_body_size_allows_normal(self) -> None:
        """_limit_request_body passes through normal-sized requests."""
        mock_request = MagicMock()
        mock_request.headers = {"content-length": "100"}
        mock_request.get = lambda k, d="": mock_request.headers.get(k, d)
        expected_response = MagicMock()
        expected_response.status_code = 200

        async def _async_call_next(r: object) -> object:
            return expected_response

        response = await _limit_request_body(mock_request, _async_call_next)
        assert response is expected_response


# ---------------------------------------------------------------------------
# Lines 132-137: _truncate_response
# ---------------------------------------------------------------------------


class TestResponseTruncation:
    """Cover lines 132-137: _truncate_response when data exceeds size limit."""

    def test_truncate_large_response(self) -> None:
        """Response exceeding _MAX_RESPONSE_SIZE gets truncated."""
        large_data = {"result": "x" * (_MAX_RESPONSE_SIZE + 1000)}
        result = _truncate_response(large_data)
        assert isinstance(result, dict)
        assert result["truncated"] is True
        assert "Response truncated" in result["message"]
        assert isinstance(result["data"], str)

    def test_no_truncate_small_response(self) -> None:
        """Response under _MAX_RESPONSE_SIZE is returned as-is."""
        small_data = {"result": "ok"}
        result = _truncate_response(small_data)
        assert result == small_data

    def test_truncate_list_response(self) -> None:
        """Large list response gets truncated."""
        large_list = [{"name": f"tool_{i}", "desc": "x" * 1000} for i in range(200)]
        result = _truncate_response(large_list)
        assert isinstance(result, dict)
        assert result["truncated"] is True
