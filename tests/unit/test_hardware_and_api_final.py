"""Final coverage tests — closes the remaining small gaps.

Targets:
- hardware/interfaces/daq.py:             82-83  (disconnect exception)
- hardware/interfaces/software_bridge.py: 87-88  (disconnect exception)
- api/routers/memory.py:                  72, 85 (success response for soul/memory)
- api/routers/devices.py:                 68-69  (409 on duplicate register)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all
from labclaw.hardware.interfaces.daq import DAQDriver
from labclaw.hardware.interfaces.software_bridge import SoftwareBridgeDriver

# ---------------------------------------------------------------------------
# DAQDriver — disconnect exception (lines 82-83)
# ---------------------------------------------------------------------------


class FakeDAQCloseError(DAQDriver):
    def _open_device(self) -> None:
        pass

    def _close_device(self) -> None:
        raise RuntimeError("close failed")

    def _read_channels(self) -> dict[str, Any]:
        return {}

    def _write_channels(self, action: str, parameters: dict[str, Any]) -> None:
        pass


class TestDAQDisconnectException:
    @pytest.mark.asyncio
    async def test_disconnect_exception_is_logged_not_raised(self) -> None:
        """_close_device() raises during disconnect — exception is swallowed (82-83)."""
        daq = FakeDAQCloseError(device_id="d_exc", device_type="daq")
        await daq.connect()
        assert daq._connected is True

        # Must not raise — exception is caught and logged
        await daq.disconnect()
        assert daq._connected is False


# ---------------------------------------------------------------------------
# SoftwareBridgeDriver — disconnect exception (lines 87-88)
# ---------------------------------------------------------------------------


class FakeBridgeCloseError(SoftwareBridgeDriver):
    def _open_connection(self) -> None:
        pass

    def _close_connection(self) -> None:
        raise RuntimeError("close failed")

    def _recv(self) -> dict[str, Any]:
        return {}

    def _send(self, action: str, parameters: dict[str, Any]) -> None:
        pass


class TestSoftwareBridgeDisconnectException:
    @pytest.mark.asyncio
    async def test_disconnect_exception_is_logged_not_raised(self) -> None:
        """_close_connection() raises during disconnect — exception is swallowed (87-88)."""
        bridge = FakeBridgeCloseError(device_id="b_exc", device_type="zmq")
        await bridge.connect()
        assert bridge._connected is True

        # Must not raise
        await bridge.disconnect()
        assert bridge._connected is False


# ---------------------------------------------------------------------------
# api/routers/memory — success response paths (lines 72, 85)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_deps() -> None:
    reset_all()


class TestMemorySuccessPaths:
    @pytest.mark.asyncio
    async def test_read_soul_success(self, tmp_path) -> None:
        """GET /api/memory/{id}/soul returns 200 when SOUL.md exists (line 72)."""
        from labclaw.api.deps import set_memory_root

        # Create a real SOUL.md for entity "lab"
        entity_dir = tmp_path / "lab"
        entity_dir.mkdir()
        soul_file = entity_dir / "SOUL.md"
        soul_file.write_text("---\ntitle: Lab\n---\nThis is the lab.\n")

        set_memory_root(tmp_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/memory/lab/soul")

        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert "path" in body

    @pytest.mark.asyncio
    async def test_read_memory_success(self, tmp_path) -> None:
        """GET /api/memory/{id}/memory returns 200 when MEMORY.md exists (line 85)."""
        from labclaw.api.deps import set_memory_root

        entity_dir = tmp_path / "lab"
        entity_dir.mkdir()
        memory_file = entity_dir / "MEMORY.md"
        memory_file.write_text("---\ntitle: Lab Memory\n---\nSome memories.\n")

        set_memory_root(tmp_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/memory/lab/memory")

        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body


# ---------------------------------------------------------------------------
# api/routers/devices — 409 on ValueError (lines 68-69)
# ---------------------------------------------------------------------------


class TestDevicesConflict:
    @pytest.mark.asyncio
    async def test_register_raises_409_on_value_error(self) -> None:
        """When registry.register() raises ValueError → 409 (lines 68-69)."""
        from labclaw.api.deps import get_device_registry

        mock_registry = MagicMock()
        mock_registry.register.side_effect = ValueError("duplicate device")

        app.dependency_overrides[get_device_registry] = lambda: mock_registry
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                resp = await c.post(
                    "/api/devices/",
                    json={"name": "CamX", "device_type": "camera"},
                )
        finally:
            app.dependency_overrides.pop(get_device_registry, None)

        assert resp.status_code == 409
        assert "duplicate device" in resp.json()["detail"]
