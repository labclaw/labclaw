"""Extended API router tests — covers uncovered lines in:

- api/routers/agents.py:   51-56, 61-67, 81-84, 93-98, 104-105
- api/routers/orchestrator.py: 31-40, 46, 52-55
- api/routers/plugins.py:  15-16, 22-24
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all


@pytest.fixture(autouse=True)
def _reset_deps() -> None:
    """Clear cached singleton deps between tests."""
    reset_all()


# ---------------------------------------------------------------------------
# /api/agents — list tools (covers lines 104-105)
# ---------------------------------------------------------------------------


class TestAgentsTools:
    @pytest.mark.asyncio
    async def test_list_tools_returns_200(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/agents/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert isinstance(tools, list)
        assert len(tools) == 7
        names = {t["name"] for t in tools}
        assert "query_memory" in names

    @pytest.mark.asyncio
    async def test_list_tools_schema_fields(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/agents/tools")
        assert resp.status_code == 200
        for tool in resp.json():
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool


# ---------------------------------------------------------------------------
# /api/agents — _require_llm and _build_runtime (lines 51-56, 61-67, 81-84, 93-98)
# ---------------------------------------------------------------------------


class TestAgentsChat:
    @pytest.mark.asyncio
    async def test_lab_assistant_chat_no_llm_returns_503(self) -> None:
        """Without LLM configured, /api/agents/chat returns 503."""
        from labclaw.api.deps import get_llm_provider as _real_dep

        app.dependency_overrides[_real_dep] = lambda: None
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/api/agents/chat", json={"message": "hello"})
        finally:
            app.dependency_overrides.pop(_real_dep, None)
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_designer_chat_no_llm_returns_503(self) -> None:
        """Without LLM configured, /api/agents/designer/chat returns 503."""
        from labclaw.api.deps import get_llm_provider as _real_dep

        app.dependency_overrides[_real_dep] = lambda: None
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/agents/designer/chat", json={"message": "hello"}
                )
        finally:
            app.dependency_overrides.pop(_real_dep, None)
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_lab_assistant_chat_with_mock_llm(self) -> None:
        """With a mocked LLM, /api/agents/chat returns 200 with agent field."""
        from labclaw.api.deps import get_llm_provider as _real_dep

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="mock response")
        mock_llm.model_name = "mock-model"

        mock_runtime = MagicMock()
        mock_runtime.chat = AsyncMock(return_value="mock response")

        app.dependency_overrides[_real_dep] = lambda: mock_llm
        try:
            with patch("labclaw.api.routers.agents._build_runtime", return_value=mock_runtime):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post("/api/agents/chat", json={"message": "hello"})
        finally:
            app.dependency_overrides.pop(_real_dep, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"] == "lab-assistant"
        assert body["response"] == "mock response"

    @pytest.mark.asyncio
    async def test_designer_chat_with_mock_llm(self) -> None:
        """With a mocked LLM, /api/agents/designer/chat returns 200."""
        from labclaw.api.deps import get_llm_provider as _real_dep

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="design response")
        mock_llm.model_name = "mock-model"

        mock_runtime = MagicMock()
        mock_runtime.chat = AsyncMock(return_value="design response")

        app.dependency_overrides[_real_dep] = lambda: mock_llm
        try:
            with patch("labclaw.api.routers.agents._build_runtime", return_value=mock_runtime):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/agents/designer/chat", json={"message": "design this"}
                    )
        finally:
            app.dependency_overrides.pop(_real_dep, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"] == "experiment-designer"


# ---------------------------------------------------------------------------
# /api/orchestrator (lines 31-40, 46, 52-55)
# ---------------------------------------------------------------------------


class TestOrchestratorRoutes:
    @pytest.mark.asyncio
    async def test_run_cycle_returns_201(self) -> None:
        """POST /api/orchestrator/cycle runs a cycle and returns 201."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/orchestrator/cycle", json={"data_rows": []})
        assert resp.status_code == 201
        body = resp.json()
        assert "cycle_id" in body

    @pytest.mark.asyncio
    async def test_run_cycle_adds_to_history(self) -> None:
        """After running a cycle, GET /api/orchestrator/history returns it."""
        # Clear the module-level cycle history
        from labclaw.api.routers import orchestrator as orch_module

        orch_module._cycle_history.clear()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            post_resp = await client.post(
                "/api/orchestrator/cycle", json={"data_rows": []}
            )
            assert post_resp.status_code == 201
            cycle_id = post_resp.json()["cycle_id"]

            get_resp = await client.get("/api/orchestrator/history")
        assert get_resp.status_code == 200
        history = get_resp.json()
        assert any(c["cycle_id"] == cycle_id for c in history)

    @pytest.mark.asyncio
    async def test_get_cycle_by_id_found(self) -> None:
        """GET /api/orchestrator/history/{id} returns the specific cycle."""
        from labclaw.api.routers import orchestrator as orch_module

        orch_module._cycle_history.clear()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            post_resp = await client.post(
                "/api/orchestrator/cycle", json={"data_rows": []}
            )
            cycle_id = post_resp.json()["cycle_id"]
            get_resp = await client.get(f"/api/orchestrator/history/{cycle_id}")

        assert get_resp.status_code == 200
        assert get_resp.json()["cycle_id"] == cycle_id

    @pytest.mark.asyncio
    async def test_get_cycle_by_id_not_found(self) -> None:
        """GET /api/orchestrator/history/{id} with unknown id returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/orchestrator/history/nonexistent-id-xyz")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_run_cycle_with_data_rows(self) -> None:
        """POST /api/orchestrator/cycle with data_rows succeeds."""
        rows = [{"x": 1.0, "y": 2.0}, {"x": 3.0, "y": 4.0}]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/orchestrator/cycle", json={"data_rows": rows})
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# /api/plugins (lines 15-16, 22-24)
# ---------------------------------------------------------------------------


class TestPluginsRoutes:
    @pytest.mark.asyncio
    async def test_list_plugins_returns_200(self) -> None:
        """GET /api/plugins/ returns 200 with list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/plugins/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_plugins_by_type_returns_200(self) -> None:
        """GET /api/plugins/by-type/{type} returns 200."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/plugins/by-type/analysis")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_plugins_by_type_unknown(self) -> None:
        """GET /api/plugins/by-type/unknown returns 200 with empty list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/plugins/by-type/unknown_type_xyz")
        assert resp.status_code == 200
        assert resp.json() == []
