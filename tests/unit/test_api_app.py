"""Tests for labclaw.api.app — global exception handler (lines 132-138)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all


@pytest.fixture(autouse=True)
def _reset_deps() -> None:
    reset_all()


class TestGlobal500Handler:
    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_500(self) -> None:
        @app.get("/test-500-handler")
        async def _raise() -> None:
            raise RuntimeError("boom")

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                resp = await client.get("/test-500-handler")
            assert resp.status_code == 500
            assert resp.json() == {"detail": "Internal server error"}
        finally:
            app.router.routes = [
                r for r in app.router.routes if getattr(r, "path", None) != "/test-500-handler"
            ]
