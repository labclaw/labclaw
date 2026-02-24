"""Hardware manager — coordinates registry and safety for command execution.

Manages the lifecycle of every device:
  - Command execution with safety validation
  - Calibration tracking (future)
  - Health metric collection (future)

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import logging

from labclaw.core.events import event_registry
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.safety import HardwareSafetyChecker
from labclaw.hardware.schemas import HardwareCommand, SafetyCheckResult

logger = logging.getLogger(__name__)

# Register command execution event at import time
_MANAGER_EVENTS = [
    "hardware.command.executed",
]

for _evt in _MANAGER_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


class HardwareManager:
    """Coordinates device registry and safety checker for command execution."""

    def __init__(self, registry: DeviceRegistry, safety: HardwareSafetyChecker) -> None:
        self._registry = registry
        self._safety = safety

    @property
    def registry(self) -> DeviceRegistry:
        return self._registry

    @property
    def safety(self) -> HardwareSafetyChecker:
        return self._safety

    def execute_command(self, command: HardwareCommand) -> SafetyCheckResult:
        """Run safety check, then execute if safe.

        Returns the SafetyCheckResult. Actual device communication is
        delegated to the appropriate interface adapter (future).
        """
        result = self._safety.check(command)

        if result.passed:
            logger.info(
                "Executing command %s on device %s",
                command.action,
                command.device_id,
            )
            # Future: dispatch to interface adapter for actual execution

        event_registry.emit(
            "hardware.command.executed",
            payload={
                "device_id": command.device_id,
                "action": command.action,
                "passed": result.passed,
                "level": result.level.value,
            },
        )

        return result
