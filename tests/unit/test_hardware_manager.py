"""Tests for HardwareManager — covers manager.py lines 36-37, 41, 45, 53-73."""

from __future__ import annotations

from labclaw.core.schemas import DeviceStatus, SafetyLevel
from labclaw.hardware.manager import HardwareManager
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.safety import HardwareSafetyChecker
from labclaw.hardware.schemas import (
    DeviceCapabilities,
    DeviceRecord,
    HardwareCommand,
    SafetyCheckResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager() -> tuple[HardwareManager, DeviceRegistry, HardwareSafetyChecker]:
    registry = DeviceRegistry()
    safety = HardwareSafetyChecker(registry)
    manager = HardwareManager(registry, safety)
    return manager, registry, safety


def _online_device(device_id: str = "cam-01") -> DeviceRecord:
    return DeviceRecord(
        device_id=device_id,
        name="Test Camera",
        device_type="camera",
        status=DeviceStatus.ONLINE,
    )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestHardwareManagerInit:
    def test_init_stores_registry_and_safety(self) -> None:
        manager, registry, safety = _make_manager()
        assert manager.registry is registry
        assert manager.safety is safety


# ---------------------------------------------------------------------------
# execute_command
# ---------------------------------------------------------------------------


class TestExecuteCommand:
    def test_execute_command_passes_safety_for_registered_online_device(self) -> None:
        manager, registry, _ = _make_manager()
        device = _online_device("cam-01")
        registry.register(device)

        command = HardwareCommand(device_id="cam-01", action="capture")
        result = manager.execute_command(command)

        assert isinstance(result, SafetyCheckResult)
        assert result.passed is True
        assert result.level == SafetyLevel.SAFE

    def test_execute_command_fails_for_unregistered_device(self) -> None:
        manager, _, _ = _make_manager()
        command = HardwareCommand(device_id="ghost-device", action="capture")
        result = manager.execute_command(command)

        assert isinstance(result, SafetyCheckResult)
        assert result.passed is False
        assert result.level == SafetyLevel.BLOCKED

    def test_execute_command_fails_for_error_state_device(self) -> None:
        manager, registry, _ = _make_manager()
        device = DeviceRecord(
            device_id="cam-err",
            name="Error Camera",
            device_type="camera",
            status=DeviceStatus.ERROR,
        )
        registry.register(device)

        command = HardwareCommand(device_id="cam-err", action="capture")
        result = manager.execute_command(command)

        assert result.passed is False
        assert result.level == SafetyLevel.BLOCKED

    def test_execute_command_fails_for_disallowed_action(self) -> None:
        manager, registry, _ = _make_manager()
        device = DeviceRecord(
            device_id="cam-cap",
            name="Capable Camera",
            device_type="camera",
            status=DeviceStatus.ONLINE,
            capabilities=DeviceCapabilities(can_control=["capture"]),
        )
        registry.register(device)

        command = HardwareCommand(device_id="cam-cap", action="self_destruct")
        result = manager.execute_command(command)

        assert result.passed is False
        assert result.level == SafetyLevel.BLOCKED

    def test_execute_command_returns_safety_check_result_type(self) -> None:
        manager, registry, _ = _make_manager()
        registry.register(_online_device("cam-type"))
        command = HardwareCommand(device_id="cam-type", action="any_action")
        result = manager.execute_command(command)
        assert isinstance(result, SafetyCheckResult)
