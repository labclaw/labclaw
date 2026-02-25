"""Hardware safety — command validation before execution.

All hardware commands pass through this layer:
  - Device existence check
  - Device status check (must be online or in_use)
  - Capability validation (action must be in can_control)
  - Emergency block (error state blocks all commands)

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import logging

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus, SafetyLevel
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.schemas import HardwareCommand, SafetyCheckResult

logger = logging.getLogger(__name__)

# Register safety event at import time
_SAFETY_EVENTS = [
    "hardware.safety.checked",
]

for _evt in _SAFETY_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)

# Statuses that allow command execution
_COMMAND_ALLOWED_STATUSES = {DeviceStatus.ONLINE, DeviceStatus.IN_USE}


class HardwareSafetyChecker:
    """Validates hardware commands before execution."""

    def __init__(self, registry: DeviceRegistry) -> None:
        self._registry = registry
        from collections import deque

        self._history: deque[SafetyCheckResult] = deque(maxlen=10_000)

    def check(self, command: HardwareCommand) -> SafetyCheckResult:
        """Validate a command against device state and capabilities.

        Returns a SafetyCheckResult. Does not raise on failure — callers
        inspect the ``passed`` field.
        """
        # 1. Device existence
        try:
            device = self._registry.get(command.device_id)
        except KeyError:
            result = SafetyCheckResult(
                device_id=command.device_id,
                check_type="pre_command",
                passed=False,
                level=SafetyLevel.BLOCKED,
                details=f"Device {command.device_id!r} not found in registry",
            )
            self._record_and_emit(result, command.action)
            return result

        # 2. Device status
        if device.status == DeviceStatus.ERROR:
            result = SafetyCheckResult(
                device_id=command.device_id,
                check_type="pre_command",
                passed=False,
                level=SafetyLevel.BLOCKED,
                details="Device is in ERROR state",
            )
            self._record_and_emit(result, command.action)
            return result

        if device.status not in _COMMAND_ALLOWED_STATUSES:
            result = SafetyCheckResult(
                device_id=command.device_id,
                check_type="pre_command",
                passed=False,
                level=SafetyLevel.BLOCKED,
                details=f"Device status is {device.status.value!r}, must be online or in_use",
            )
            self._record_and_emit(result, command.action)
            return result

        # 3. Capability check
        if (
            device.capabilities
            and device.capabilities.can_control
            and command.action not in device.capabilities.can_control
        ):
            result = SafetyCheckResult(
                device_id=command.device_id,
                check_type="pre_command",
                passed=False,
                level=SafetyLevel.BLOCKED,
                details=(
                    f"Action {command.action!r} not in device capabilities: "
                    f"{device.capabilities.can_control}"
                ),
            )
            self._record_and_emit(result, command.action)
            return result

        # 4. All checks passed
        result = SafetyCheckResult(
            device_id=command.device_id,
            check_type="pre_command",
            passed=True,
            level=SafetyLevel.SAFE,
            details="All safety checks passed",
        )
        self._record_and_emit(result, command.action)
        return result

    def get_safety_history(self, device_id: str) -> list[SafetyCheckResult]:
        """Return all safety check results for a device."""
        return [r for r in self._history if r.device_id == device_id]

    def _record_and_emit(self, result: SafetyCheckResult, action: str) -> None:
        """Store result and emit event."""
        self._history.append(result)
        event_registry.emit(
            "hardware.safety.checked",
            payload={
                "device_id": result.device_id,
                "action": action,
                "passed": result.passed,
                "level": result.level.value,
            },
        )
