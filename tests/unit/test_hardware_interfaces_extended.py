"""Extended tests for hardware interface drivers — covers remaining uncovered lines.

Targets:
- hardware/interfaces/serial.py:   58-59, 129-130, 139-145, 150
- hardware/interfaces/driver.py:   48, 52, 56, 60, 64  (Protocol stubs are not
  executable; covered by structural isinstance and property checks)
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.interfaces.driver import DeviceDriver
from labclaw.hardware.interfaces.serial import SerialDriver
from labclaw.hardware.schemas import HardwareCommand

# ---------------------------------------------------------------------------
# SerialDriver — ImportError branch (lines 58-59)
# ---------------------------------------------------------------------------


class TestSerialImportError:
    @pytest.mark.asyncio
    async def test_connect_raises_import_error_when_serial_missing(self) -> None:
        """Removing 'serial' from sys.modules makes the import fail → ImportError."""
        driver = SerialDriver(device_id="imp1", device_type="arduino", port="/dev/ttyS0")

        # Save and remove serial from sys.modules to simulate missing pyserial
        saved = sys.modules.pop("serial", None)
        try:
            with patch.dict("sys.modules", {"serial": None}):
                with pytest.raises(ImportError, match="pyserial is required"):
                    await driver.connect()
        finally:
            if saved is not None:
                sys.modules["serial"] = saved


# ---------------------------------------------------------------------------
# SerialDriver — write with parameters (lines 129-130)
# ---------------------------------------------------------------------------


class TestSerialWriteWithParameters:
    @pytest.mark.asyncio
    async def test_write_with_non_empty_parameters_sends_json(self) -> None:
        """write() with non-empty parameters appends JSON to action string."""
        import json

        driver = SerialDriver(device_id="wp1", device_type="arduino", port="/dev/ttyUSB0")
        mock_serial = MagicMock()
        mock_serial.is_open = True
        driver._serial = mock_serial

        cmd = HardwareCommand(device_id="wp1", action="SET_TEMP", parameters={"value": 37.5})
        result = await driver.write(cmd)

        assert result is True
        # The written bytes must include action + space + json params
        written_bytes = mock_serial.write.call_args[0][0]
        written_str = written_bytes.decode("utf-8")
        assert written_str.startswith("SET_TEMP ")
        payload = json.loads(written_str[len("SET_TEMP ") :].strip())
        assert payload["value"] == 37.5


# ---------------------------------------------------------------------------
# SerialDriver — write exception (lines 139-145)
# ---------------------------------------------------------------------------


class TestSerialWriteException:
    @pytest.mark.asyncio
    async def test_write_exception_returns_false(self) -> None:
        """If serial.write raises, write() returns False."""
        driver = SerialDriver(device_id="we1", device_type="arduino", port="/dev/ttyUSB0")
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial.write.side_effect = OSError("serial write failed")
        driver._serial = mock_serial

        cmd = HardwareCommand(device_id="we1", action="GO", parameters={})
        result = await driver.write(cmd)

        assert result is False

    @pytest.mark.asyncio
    async def test_write_exception_with_parameters_returns_false(self) -> None:
        """Exception during write with parameters also returns False."""
        driver = SerialDriver(device_id="we2", device_type="arduino", port="/dev/ttyUSB0")
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial.write.side_effect = RuntimeError("port disconnected")
        driver._serial = mock_serial

        cmd = HardwareCommand(device_id="we2", action="CMD", parameters={"speed": 100})
        result = await driver.write(cmd)

        assert result is False


# ---------------------------------------------------------------------------
# SerialDriver — status ONLINE (line 150)
# ---------------------------------------------------------------------------


class TestSerialStatusOnline:
    @pytest.mark.asyncio
    async def test_status_online_when_serial_open(self) -> None:
        """status() returns ONLINE when _serial is set and is_open=True."""
        driver = SerialDriver(device_id="so1", device_type="arduino", port="/dev/ttyUSB0")
        mock_serial = MagicMock()
        mock_serial.is_open = True
        driver._serial = mock_serial

        status = await driver.status()
        assert status == DeviceStatus.ONLINE


# ---------------------------------------------------------------------------
# DeviceDriver Protocol — structural checks (lines 48, 52, 56, 60, 64)
# ---------------------------------------------------------------------------


class TestDeviceDriverProtocol:
    def test_serial_driver_satisfies_protocol(self) -> None:
        """SerialDriver is runtime-checkable against DeviceDriver Protocol."""
        driver = SerialDriver(device_id="p1", device_type="daq", port="/dev/ttyUSB0")
        assert isinstance(driver, DeviceDriver)

    def test_device_driver_is_runtime_checkable(self) -> None:
        """DeviceDriver is decorated with @runtime_checkable."""

        # A plain object without the required methods must NOT satisfy the protocol
        class NotADriver:
            pass

        assert not isinstance(NotADriver(), DeviceDriver)

    def test_mock_satisfying_protocol(self) -> None:
        """A MagicMock with the right attributes satisfies the Protocol."""
        mock_driver = MagicMock(spec=DeviceDriver)
        # MagicMock with spec provides all protocol attributes
        assert hasattr(mock_driver, "device_id")
        assert hasattr(mock_driver, "device_type")
        assert hasattr(mock_driver, "connect")
        assert hasattr(mock_driver, "disconnect")
        assert hasattr(mock_driver, "read")
        assert hasattr(mock_driver, "write")
        assert hasattr(mock_driver, "status")
