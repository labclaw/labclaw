"""Tests for hardware interface base drivers: DAQ, SoftwareBridge, NetworkAPI, Serial.

Covers:
- src/labclaw/hardware/interfaces/daq.py
- src/labclaw/hardware/interfaces/software_bridge.py
- src/labclaw/hardware/interfaces/network_api.py
- src/labclaw/hardware/interfaces/serial.py
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.interfaces.daq import DAQDriver
from labclaw.hardware.interfaces.network_api import NetworkAPIDriver
from labclaw.hardware.interfaces.serial import SerialDriver
from labclaw.hardware.interfaces.software_bridge import SoftwareBridgeDriver
from labclaw.hardware.schemas import HardwareCommand

# ---------------------------------------------------------------------------
# Concrete DAQ subclass
# ---------------------------------------------------------------------------


class FakeDAQ(DAQDriver):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.open_called = False
        self.close_called = False
        self.should_fail = False

    def _open_device(self) -> None:
        if self.should_fail:
            raise RuntimeError("device error")
        self.open_called = True

    def _close_device(self) -> None:
        self.close_called = True

    def _read_channels(self) -> dict[str, Any]:
        return {"ch0": 1.5, "ch1": 2.3}

    def _write_channels(self, action: str, parameters: dict[str, Any]) -> None:
        if action == "fail":
            raise RuntimeError("write error")


# ---------------------------------------------------------------------------
# DAQDriver tests
# ---------------------------------------------------------------------------


class TestDAQDriver:
    @pytest.mark.asyncio
    async def test_daq_connect_success(self) -> None:
        daq = FakeDAQ(device_id="d1", device_type="daq")
        result = await daq.connect()
        assert result is True
        assert daq._connected is True
        assert daq.open_called is True

    @pytest.mark.asyncio
    async def test_daq_connect_failure(self) -> None:
        daq = FakeDAQ(device_id="d2", device_type="daq")
        daq.should_fail = True
        result = await daq.connect()
        assert result is False
        assert daq._connected is False

    @pytest.mark.asyncio
    async def test_daq_disconnect(self) -> None:
        daq = FakeDAQ(device_id="d3", device_type="daq")
        await daq.connect()
        await daq.disconnect()
        assert daq._connected is False
        assert daq.close_called is True

    @pytest.mark.asyncio
    async def test_daq_read(self) -> None:
        daq = FakeDAQ(device_id="d4", device_type="daq")
        await daq.connect()
        data = await daq.read()
        assert data == {"ch0": 1.5, "ch1": 2.3}

    @pytest.mark.asyncio
    async def test_daq_write_success(self) -> None:
        daq = FakeDAQ(device_id="d5", device_type="daq")
        await daq.connect()
        cmd = HardwareCommand(device_id="d5", action="set", parameters={})
        result = await daq.write(cmd)
        assert result is True

    @pytest.mark.asyncio
    async def test_daq_write_failure(self) -> None:
        daq = FakeDAQ(device_id="d6", device_type="daq")
        await daq.connect()
        cmd = HardwareCommand(device_id="d6", action="fail", parameters={})
        result = await daq.write(cmd)
        assert result is False

    @pytest.mark.asyncio
    async def test_daq_status_online(self) -> None:
        daq = FakeDAQ(device_id="d7", device_type="daq")
        await daq.connect()
        status = await daq.status()
        assert status == DeviceStatus.ONLINE

    @pytest.mark.asyncio
    async def test_daq_status_offline(self) -> None:
        daq = FakeDAQ(device_id="d8", device_type="daq")
        status = await daq.status()
        assert status == DeviceStatus.OFFLINE

    def test_daq_properties(self) -> None:
        daq = FakeDAQ(device_id="d9", device_type="gpio")
        assert daq.device_id == "d9"
        assert daq.device_type == "gpio"


# ---------------------------------------------------------------------------
# Concrete SoftwareBridge subclass
# ---------------------------------------------------------------------------


class FakeBridge(SoftwareBridgeDriver):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.open_called = False
        self.should_fail_open = False

    def _open_connection(self) -> None:
        if self.should_fail_open:
            raise RuntimeError("connection error")
        self.open_called = True

    def _close_connection(self) -> None:
        pass

    def _recv(self) -> dict[str, Any]:
        return {"frame": 42}

    def _send(self, action: str, parameters: dict[str, Any]) -> None:
        if action == "fail":
            raise RuntimeError("send error")


# ---------------------------------------------------------------------------
# SoftwareBridgeDriver tests
# ---------------------------------------------------------------------------


class TestSoftwareBridgeDriver:
    @pytest.mark.asyncio
    async def test_bridge_connect_success(self) -> None:
        bridge = FakeBridge(device_id="b1", device_type="zmq")
        result = await bridge.connect()
        assert result is True
        assert bridge._connected is True
        assert bridge.open_called is True

    @pytest.mark.asyncio
    async def test_bridge_connect_failure(self) -> None:
        bridge = FakeBridge(device_id="b2", device_type="zmq")
        bridge.should_fail_open = True
        result = await bridge.connect()
        assert result is False
        assert bridge._connected is False

    @pytest.mark.asyncio
    async def test_bridge_disconnect(self) -> None:
        bridge = FakeBridge(device_id="b3", device_type="zmq")
        await bridge.connect()
        await bridge.disconnect()
        assert bridge._connected is False

    @pytest.mark.asyncio
    async def test_bridge_read(self) -> None:
        bridge = FakeBridge(device_id="b4", device_type="zmq")
        await bridge.connect()
        data = await bridge.read()
        assert data == {"frame": 42}

    @pytest.mark.asyncio
    async def test_bridge_write_success(self) -> None:
        bridge = FakeBridge(device_id="b5", device_type="zmq")
        await bridge.connect()
        cmd = HardwareCommand(device_id="b5", action="start", parameters={})
        result = await bridge.write(cmd)
        assert result is True

    @pytest.mark.asyncio
    async def test_bridge_write_failure(self) -> None:
        bridge = FakeBridge(device_id="b6", device_type="zmq")
        await bridge.connect()
        cmd = HardwareCommand(device_id="b6", action="fail", parameters={})
        result = await bridge.write(cmd)
        assert result is False

    @pytest.mark.asyncio
    async def test_bridge_status_online(self) -> None:
        bridge = FakeBridge(device_id="b7", device_type="zmq")
        await bridge.connect()
        status = await bridge.status()
        assert status == DeviceStatus.ONLINE

    @pytest.mark.asyncio
    async def test_bridge_status_offline(self) -> None:
        bridge = FakeBridge(device_id="b8", device_type="zmq")
        status = await bridge.status()
        assert status == DeviceStatus.OFFLINE

    def test_bridge_properties(self) -> None:
        bridge = FakeBridge(device_id="b9", device_type="bonsai", endpoint="tcp://localhost:5555")
        assert bridge.device_id == "b9"
        assert bridge.device_type == "bonsai"


# ---------------------------------------------------------------------------
# NetworkAPIDriver tests
# ---------------------------------------------------------------------------


class TestNetworkAPIDriver:
    def test_network_api_init(self) -> None:
        driver = NetworkAPIDriver(
            device_id="net1",
            device_type="api",
            base_url="http://localhost:8080/",
        )
        assert driver.device_id == "net1"
        assert driver.device_type == "api"
        # Trailing slash must be stripped
        assert driver._base_url == "http://localhost:8080"

    @pytest.mark.asyncio
    async def test_network_api_status_offline(self) -> None:
        driver = NetworkAPIDriver(device_id="net2", device_type="api", base_url="http://x")
        status = await driver.status()
        assert status == DeviceStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_network_api_disconnect(self) -> None:
        driver = NetworkAPIDriver(device_id="net3", device_type="api", base_url="http://x")
        driver._connected = True
        await driver.disconnect()
        assert driver._connected is False

    @pytest.mark.asyncio
    async def test_network_api_connect_success(self) -> None:
        driver = NetworkAPIDriver(
            device_id="net4",
            device_type="api",
            base_url="http://localhost:8080/",
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        # httpx is imported lazily inside the method; patch the module-level name in httpx itself
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await driver.connect()
        assert result is True
        assert driver._connected is True

    @pytest.mark.asyncio
    async def test_network_api_connect_failure(self) -> None:
        driver = NetworkAPIDriver(device_id="net5", device_type="api", base_url="http://x")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=OSError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await driver.connect()
        assert result is False
        assert driver._connected is False

    @pytest.mark.asyncio
    async def test_network_api_read_success(self) -> None:
        driver = NetworkAPIDriver(device_id="net6", device_type="api", base_url="http://x")
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"temperature": 37.0})
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            data = await driver.read()
        assert data == {"temperature": 37.0}

    @pytest.mark.asyncio
    async def test_network_api_read_failure(self) -> None:
        driver = NetworkAPIDriver(device_id="net7", device_type="api", base_url="http://x")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=OSError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(OSError):
                await driver.read()

    @pytest.mark.asyncio
    async def test_network_api_write_success(self) -> None:
        driver = NetworkAPIDriver(device_id="net8", device_type="api", base_url="http://x")
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        cmd = HardwareCommand(device_id="net8", action="trigger", parameters={"v": 1})
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await driver.write(cmd)
        assert result is True

    @pytest.mark.asyncio
    async def test_network_api_write_failure(self) -> None:
        driver = NetworkAPIDriver(device_id="net9", device_type="api", base_url="http://x")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=OSError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        cmd = HardwareCommand(device_id="net9", action="go", parameters={})
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await driver.write(cmd)
        assert result is False


# ---------------------------------------------------------------------------
# SerialDriver tests
# ---------------------------------------------------------------------------


class TestSerialDriver:
    def test_serial_init(self) -> None:
        driver = SerialDriver(device_id="s1", device_type="arduino", port="/dev/ttyUSB0")
        assert driver.device_id == "s1"
        assert driver.device_type == "arduino"
        assert driver._port == "/dev/ttyUSB0"
        assert driver._baudrate == 9600
        assert driver._serial is None

    @pytest.mark.asyncio
    async def test_serial_status_offline(self) -> None:
        driver = SerialDriver(device_id="s2", device_type="arduino", port="/dev/ttyUSB0")
        status = await driver.status()
        assert status == DeviceStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_serial_disconnect(self) -> None:
        driver = SerialDriver(device_id="s3", device_type="arduino", port="/dev/ttyUSB0")
        mock_serial = MagicMock()
        mock_serial.is_open = True
        driver._serial = mock_serial
        await driver.disconnect()
        assert driver._serial is None
        mock_serial.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_serial_connect_success(self) -> None:
        driver = SerialDriver(
            device_id="s4",
            device_type="arduino",
            port="/dev/ttyUSB0",
            baudrate=115200,
        )
        mock_serial_instance = MagicMock()
        mock_serial_module = MagicMock()
        mock_serial_module.Serial.return_value = mock_serial_instance
        with patch.dict("sys.modules", {"serial": mock_serial_module}):
            result = await driver.connect()
        assert result is True
        assert driver._serial is mock_serial_instance

    @pytest.mark.asyncio
    async def test_serial_connect_failure(self) -> None:
        driver = SerialDriver(device_id="s5", device_type="arduino", port="/dev/ttyUSB0")
        mock_serial_module = MagicMock()
        mock_serial_module.Serial.side_effect = OSError("port not found")
        with patch.dict("sys.modules", {"serial": mock_serial_module}):
            result = await driver.connect()
        assert result is False
        assert driver._serial is None

    @pytest.mark.asyncio
    async def test_serial_read(self) -> None:
        driver = SerialDriver(device_id="s6", device_type="arduino", port="/dev/ttyUSB0")
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial.readline.return_value = b"VALUE=3.14\n"
        driver._serial = mock_serial
        result = await driver.read()
        assert result == {"response": "VALUE=3.14"}

    @pytest.mark.asyncio
    async def test_serial_read_not_connected(self) -> None:
        driver = SerialDriver(device_id="s7", device_type="arduino", port="/dev/ttyUSB0")
        with pytest.raises(RuntimeError, match="not connected"):
            await driver.read()

    @pytest.mark.asyncio
    async def test_serial_write_success(self) -> None:
        driver = SerialDriver(device_id="s8", device_type="arduino", port="/dev/ttyUSB0")
        mock_serial = MagicMock()
        mock_serial.is_open = True
        driver._serial = mock_serial
        cmd = HardwareCommand(device_id="s8", action="LED_ON", parameters={})
        result = await driver.write(cmd)
        assert result is True
        mock_serial.write.assert_called_once_with(b"LED_ON\n")

    @pytest.mark.asyncio
    async def test_serial_write_not_connected(self) -> None:
        driver = SerialDriver(device_id="s9", device_type="arduino", port="/dev/ttyUSB0")
        cmd = HardwareCommand(device_id="s9", action="go", parameters={})
        result = await driver.write(cmd)
        assert result is False

    def test_serial_parse_response(self) -> None:
        driver = SerialDriver(device_id="s10", device_type="arduino", port="/dev/ttyUSB0")
        result = driver.parse_response("HELLO")
        assert result == {"response": "HELLO"}
