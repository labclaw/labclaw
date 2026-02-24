"""Tests for labclaw.core.safety — HardwareSafetyGuard."""

from __future__ import annotations

import time

import pytest

from labclaw.core.safety import HardwareSafetyGuard, SafetyCheckResult
from labclaw.core.schemas import DeviceStatus, SafetyLevel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def guard() -> HardwareSafetyGuard:
    return HardwareSafetyGuard(max_commands_per_minute=5, rate_limit_window=1.0)


# ---------------------------------------------------------------------------
# Emergency stop
# ---------------------------------------------------------------------------


class TestEmergencyStop:
    def test_emergency_stop_blocks_all(self, guard: HardwareSafetyGuard) -> None:
        guard.activate_emergency_stop("fire alarm")
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.ONLINE,
        )
        assert result.allowed is False
        assert "Emergency stop" in result.reason

    def test_emergency_stop_cleared(self, guard: HardwareSafetyGuard) -> None:
        guard.activate_emergency_stop("test")
        guard.clear_emergency_stop()
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.ONLINE,
        )
        assert result.allowed is True

    def test_emergency_stop_property(self, guard: HardwareSafetyGuard) -> None:
        assert guard.emergency_stopped is False
        guard.activate_emergency_stop("test")
        assert guard.emergency_stopped is True
        guard.clear_emergency_stop()
        assert guard.emergency_stopped is False


# ---------------------------------------------------------------------------
# Device status checks
# ---------------------------------------------------------------------------


class TestDeviceStatusChecks:
    def test_offline_device_blocked(self, guard: HardwareSafetyGuard) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.OFFLINE,
        )
        assert result.allowed is False
        assert "not commandable" in result.reason

    def test_error_device_blocked(self, guard: HardwareSafetyGuard) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="write",
            device_status=DeviceStatus.ERROR,
        )
        assert result.allowed is False

    def test_calibrating_device_blocked(self, guard: HardwareSafetyGuard) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.CALIBRATING,
        )
        assert result.allowed is False

    def test_online_device_allowed(self, guard: HardwareSafetyGuard) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.ONLINE,
        )
        assert result.allowed is True

    def test_in_use_device_allowed(self, guard: HardwareSafetyGuard) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.IN_USE,
        )
        assert result.allowed is True

    def test_reserved_device_blocked(self, guard: HardwareSafetyGuard) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.RESERVED,
        )
        assert result.allowed is False


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_rate_limit_exceeded(self, guard: HardwareSafetyGuard) -> None:
        # Send 5 commands (the limit)
        for _ in range(5):
            result = guard.check_command(
                device_id="dev1",
                action="read",
                device_status=DeviceStatus.ONLINE,
            )
            assert result.allowed is True

        # 6th command should be rate limited
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.ONLINE,
        )
        assert result.allowed is False
        assert "Rate limit" in result.reason

    def test_rate_limit_per_device(self, guard: HardwareSafetyGuard) -> None:
        # Fill rate limit for dev1
        for _ in range(5):
            guard.check_command(
                device_id="dev1",
                action="read",
                device_status=DeviceStatus.ONLINE,
            )

        # dev2 should still be allowed
        result = guard.check_command(
            device_id="dev2",
            action="read",
            device_status=DeviceStatus.ONLINE,
        )
        assert result.allowed is True

    def test_rate_limit_resets_after_window(self) -> None:
        guard = HardwareSafetyGuard(max_commands_per_minute=2, rate_limit_window=0.1)
        for _ in range(2):
            guard.check_command(
                device_id="dev1",
                action="read",
                device_status=DeviceStatus.ONLINE,
            )

        # Wait for window to expire
        time.sleep(0.15)

        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.ONLINE,
        )
        assert result.allowed is True


# ---------------------------------------------------------------------------
# Write command approval
# ---------------------------------------------------------------------------


class TestWriteCommandApproval:
    def test_write_needs_approval_blocked_without_it(
        self, guard: HardwareSafetyGuard,
    ) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="write",
            device_status=DeviceStatus.ONLINE,
            safety_level=SafetyLevel.REQUIRES_APPROVAL,
            approved=False,
        )
        assert result.allowed is False
        assert "requires approval" in result.reason

    def test_write_with_approval_allowed(
        self, guard: HardwareSafetyGuard,
    ) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="write",
            device_status=DeviceStatus.ONLINE,
            safety_level=SafetyLevel.REQUIRES_APPROVAL,
            approved=True,
        )
        assert result.allowed is True

    def test_execute_needs_approval_blocked(
        self, guard: HardwareSafetyGuard,
    ) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="execute",
            device_status=DeviceStatus.ONLINE,
            safety_level=SafetyLevel.REQUIRES_APPROVAL,
            approved=False,
        )
        assert result.allowed is False

    def test_read_does_not_need_approval(
        self, guard: HardwareSafetyGuard,
    ) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.ONLINE,
            safety_level=SafetyLevel.REQUIRES_APPROVAL,
            approved=False,
        )
        # Read is not a write action, so it passes even without approval
        assert result.allowed is True

    def test_safe_level_write_allowed_without_approval(
        self, guard: HardwareSafetyGuard,
    ) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="write",
            device_status=DeviceStatus.ONLINE,
            safety_level=SafetyLevel.SAFE,
            approved=False,
        )
        assert result.allowed is True

    def test_calibrate_is_write_action(
        self, guard: HardwareSafetyGuard,
    ) -> None:
        result = guard.check_command(
            device_id="dev1",
            action="calibrate",
            device_status=DeviceStatus.ONLINE,
            safety_level=SafetyLevel.REQUIRES_APPROVAL,
            approved=False,
        )
        assert result.allowed is False


# ---------------------------------------------------------------------------
# SafetyCheckResult model
# ---------------------------------------------------------------------------


class TestSafetyCheckResult:
    def test_defaults(self) -> None:
        result = SafetyCheckResult(allowed=True)
        assert result.reason == ""
        assert result.safety_level == SafetyLevel.SAFE

    def test_blocked(self) -> None:
        result = SafetyCheckResult(
            allowed=False,
            reason="test",
            safety_level=SafetyLevel.BLOCKED,
        )
        assert result.allowed is False
        assert result.safety_level == SafetyLevel.BLOCKED


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------


class TestCombinedScenarios:
    def test_emergency_stop_overrides_everything(
        self, guard: HardwareSafetyGuard,
    ) -> None:
        """Emergency stop blocks even approved commands on online devices."""
        guard.activate_emergency_stop("critical")
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.ONLINE,
            safety_level=SafetyLevel.SAFE,
            approved=True,
        )
        assert result.allowed is False
        assert "Emergency stop" in result.reason

    def test_offline_checked_before_rate_limit(
        self, guard: HardwareSafetyGuard,
    ) -> None:
        """Device status is checked before rate limit to avoid wasting rate limit slots."""
        result = guard.check_command(
            device_id="dev1",
            action="read",
            device_status=DeviceStatus.OFFLINE,
        )
        assert result.allowed is False
        assert "not commandable" in result.reason
