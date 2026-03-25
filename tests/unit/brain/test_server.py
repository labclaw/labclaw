"""Tests for the Cloud Brain REST API server."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from slowapi.middleware import SlowAPIMiddleware

from labclaw.brain.server import _reset_api_keys, app
from labclaw.brain.types import BrainResult, HealthStatus, ToolInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_brain_state():
    """Reset global state between tests."""
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


def _mock_brain(
    *,
    execute_result: BrainResult | None = None,
    tools: list[ToolInfo] | None = None,
    health_status: HealthStatus | None = None,
):
    """Return a dict of patches for brain module functions."""
    patches = {}
    patches["execute"] = patch(
        "labclaw.brain.server.brain.execute",
        new_callable=AsyncMock,
        return_value=execute_result or BrainResult(success=True, data="ok"),
    )
    patches["list_tools"] = patch(
        "labclaw.brain.server.brain.list_tools",
        new_callable=AsyncMock,
        return_value=tools or [],
    )
    patches["health"] = patch(
        "labclaw.brain.server.brain.health",
        new_callable=AsyncMock,
        return_value=health_status
        or HealthStatus(status="ok", skills={"test": True}, tool_count=1, version="0.0.1"),
    )
    patches["reason"] = patch(
        "labclaw.brain.server.brain.reason",
        new_callable=AsyncMock,
        return_value=execute_result or BrainResult(success=True, data="reasoning"),
    )
    patches["write"] = patch(
        "labclaw.brain.server.brain.write",
        new_callable=AsyncMock,
        return_value=execute_result or BrainResult(success=True, data="text"),
    )
    return patches


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    async def test_returns_health(self, client):
        patches = _mock_brain()
        with patches["health"]:
            resp = await client.get("/brain/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["tool_count"] == 1
        assert data["version"] == "0.0.1"

    async def test_includes_skills(self, client):
        hs = HealthStatus(
            status="degraded",
            skills={"tooluniverse": True, "lifesci": False},
            tool_count=5,
            version="0.0.1",
        )
        patches = _mock_brain(health_status=hs)
        with patches["health"]:
            resp = await client.get("/brain/health")

        data = resp.json()
        assert data["status"] == "degraded"
        assert data["skills"]["lifesci"] is False


# ---------------------------------------------------------------------------
# Tools endpoint
# ---------------------------------------------------------------------------


class TestToolsEndpoint:
    async def test_returns_tools(self, client):
        tools = [
            ToolInfo(name="t1", description="desc1", skill="s1", category="bio"),
            ToolInfo(name="t2", description="desc2", skill="s2"),
        ]
        patches = _mock_brain(tools=tools)
        with patches["list_tools"] as mock_lt:
            resp = await client.get("/brain/tools")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "t1"
        mock_lt.assert_awaited_once_with(category="")

    async def test_filters_by_category(self, client):
        patches = _mock_brain()
        with patches["list_tools"] as mock_lt:
            resp = await client.get("/brain/tools?category=chemistry")

        assert resp.status_code == 200
        mock_lt.assert_awaited_once_with(category="chemistry")


# ---------------------------------------------------------------------------
# Execute endpoint
# ---------------------------------------------------------------------------


class TestExecuteEndpoint:
    async def test_execute_success(self, client):
        result = BrainResult(success=True, data={"pmids": [123]})
        patches = _mock_brain(execute_result=result)
        with patches["execute"] as mock_ex:
            resp = await client.post(
                "/brain/execute",
                json={"tool_name": "search_pubmed", "arguments": {"query": "CRISPR"}},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        mock_ex.assert_awaited_once_with("search_pubmed", query="CRISPR")

    async def test_execute_with_empty_arguments(self, client):
        patches = _mock_brain()
        with patches["execute"] as mock_ex:
            resp = await client.post("/brain/execute", json={"tool_name": "some_tool"})

        assert resp.status_code == 200
        mock_ex.assert_awaited_once_with("some_tool")


# ---------------------------------------------------------------------------
# Reason endpoint
# ---------------------------------------------------------------------------


class TestReasonEndpoint:
    async def test_reason_success(self, client):
        result = BrainResult(success=True, data="CRISPR explanation")
        patches = _mock_brain(execute_result=result)
        with patches["reason"] as mock_r:
            resp = await client.post(
                "/brain/reason",
                json={"question": "What is CRISPR?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        mock_r.assert_awaited_once_with("What is CRISPR?", domain="general", context="")

    async def test_reason_with_domain(self, client):
        patches = _mock_brain()
        with patches["reason"] as mock_r:
            resp = await client.post(
                "/brain/reason",
                json={
                    "question": "Q?",
                    "domain": "neuroscience",
                    "context": "fMRI",
                },
            )

        assert resp.status_code == 200
        mock_r.assert_awaited_once_with("Q?", domain="neuroscience", context="fMRI")


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------


class TestWriteEndpoint:
    async def test_write_success(self, client):
        result = BrainResult(success=True, data="Abstract text...")
        patches = _mock_brain(execute_result=result)
        with patches["write"] as mock_w:
            resp = await client.post(
                "/brain/write",
                json={"section": "abstract", "context": "CRISPR study"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        mock_w.assert_awaited_once_with(section="abstract", context="CRISPR study")


# ---------------------------------------------------------------------------
# API key auth
# ---------------------------------------------------------------------------


class TestApiKeyAuth:
    async def test_no_keys_configured_allows_anonymous(self, client):
        patches = _mock_brain()
        with patches["execute"]:
            resp = await client.post("/brain/execute", json={"tool_name": "t"})
        assert resp.status_code == 200

    async def test_valid_key_accepted(self, client, monkeypatch):
        monkeypatch.setenv("LABCLAW_API_KEYS", "key1,key2")
        _reset_api_keys()

        patches = _mock_brain()
        with patches["execute"]:
            resp = await client.post(
                "/brain/execute",
                json={"tool_name": "t"},
                headers={"X-API-Key": "key1"},
            )
        assert resp.status_code == 200

    async def test_invalid_key_rejected(self, client, monkeypatch):
        monkeypatch.setenv("LABCLAW_API_KEYS", "key1,key2")
        _reset_api_keys()

        patches = _mock_brain()
        with patches["execute"]:
            resp = await client.post(
                "/brain/execute",
                json={"tool_name": "t"},
                headers={"X-API-Key": "wrong"},
            )
        assert resp.status_code == 401

    async def test_missing_key_rejected_when_keys_configured(self, client, monkeypatch):
        monkeypatch.setenv("LABCLAW_API_KEYS", "secret")
        _reset_api_keys()

        patches = _mock_brain()
        with patches["execute"]:
            resp = await client.post("/brain/execute", json={"tool_name": "t"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting headers
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_limiter_is_configured(self):
        """Verify the limiter is attached to app state."""
        from labclaw.brain.server import limiter

        assert app.state.limiter is limiter

    def test_slowapi_middleware_registered(self):
        """Verify SlowAPIMiddleware is in the app middleware stack."""
        middleware_classes = [m.cls for m in app.user_middleware]
        assert SlowAPIMiddleware in middleware_classes
