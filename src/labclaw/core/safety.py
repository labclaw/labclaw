"""Hardware safety guard — validates commands before they reach devices.

Provides rate limiting, device status checks, emergency stop,
and safety-level enforcement for hardware commands.

Design doc: section 8.2 (Two-Layer Safety)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus, SafetyLevel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register safety events
# ---------------------------------------------------------------------------

_SAFETY_EVENTS = [
    "safety.command.approved",
    "safety.command.blocked",
    "safety.emergency_stop.activated",
    "safety.emergency_stop.cleared",
    "safety.rate_limit.exceeded",
]

for _evt in _SAFETY_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SafetyCheckResult(BaseModel):
    """Result of a hardware safety check."""

    allowed: bool
    reason: str = ""
    safety_level: SafetyLevel = SafetyLevel.SAFE


class CommandRecord(BaseModel):
    """Tracks a command for rate limiting."""

    device_id: str
    action: str
    timestamp: float


# ---------------------------------------------------------------------------
# HardwareSafetyGuard
# ---------------------------------------------------------------------------


class HardwareSafetyGuard:
    """Validates hardware commands before execution.

    Checks:
    1. Emergency stop is not active
    2. Device is in a valid state for the command
    3. Rate limits are not exceeded
    4. Safety level allows the action (write commands need approval)
    """

    # Actions that modify device state
    WRITE_ACTIONS = frozenset(
        {
            "write",
            "execute",
            "calibrate",
            "set",
            "configure",
            "reset",
            "start",
            "stop",
        }
    )

    # Device states that allow commands
    COMMANDABLE_STATES = frozenset(
        {
            DeviceStatus.ONLINE,
            DeviceStatus.IN_USE,
        }
    )

    def __init__(
        self,
        max_commands_per_minute: int = 60,
        rate_limit_window: float = 60.0,
    ) -> None:
        self._emergency_stop = False
        self._lock = threading.Lock()
        self._command_history: dict[str, list[float]] = defaultdict(list)
        self._max_commands_per_minute = max_commands_per_minute
        self._rate_limit_window = rate_limit_window

    @property
    def emergency_stopped(self) -> bool:
        with self._lock:
            return self._emergency_stop

    def activate_emergency_stop(self, reason: str = "") -> None:
        """Activate emergency stop — blocks ALL hardware commands."""
        with self._lock:
            self._emergency_stop = True
        event_registry.emit(
            "safety.emergency_stop.activated",
            payload={"reason": reason},
        )
        logger.critical("EMERGENCY STOP activated: %s", reason)

    def clear_emergency_stop(self) -> None:
        """Clear emergency stop — re-enables hardware commands."""
        with self._lock:
            self._emergency_stop = False
        event_registry.emit("safety.emergency_stop.cleared", payload={})
        logger.warning("Emergency stop cleared")

    def check_command(
        self,
        device_id: str,
        action: str,
        device_status: DeviceStatus,
        safety_level: SafetyLevel = SafetyLevel.SAFE,
        approved: bool = False,
        context: dict[str, Any] | None = None,
    ) -> SafetyCheckResult:
        """Validate a hardware command before execution.

        Args:
            device_id: Target device identifier.
            action: Command action (read, write, execute, etc.).
            device_status: Current device status.
            safety_level: Safety classification of the command.
            approved: Whether the command has been approved (for write commands).
            context: Additional context for logging.

        Returns:
            SafetyCheckResult with allowed=True/False and reason.
        """
        # 1. Emergency stop
        if self.emergency_stopped:
            result = SafetyCheckResult(
                allowed=False,
                reason="Emergency stop is active",
                safety_level=SafetyLevel.BLOCKED,
            )
            self._emit_blocked(device_id, action, result.reason)
            return result

        # 2. Device status check
        if device_status not in self.COMMANDABLE_STATES:
            result = SafetyCheckResult(
                allowed=False,
                reason=f"Device {device_id} is {device_status.value}, not commandable",
                safety_level=SafetyLevel.BLOCKED,
            )
            self._emit_blocked(device_id, action, result.reason)
            return result

        # 3. Rate limit check
        if not self._check_rate_limit(device_id):
            result = SafetyCheckResult(
                allowed=False,
                reason=f"Rate limit exceeded for device {device_id}",
                safety_level=SafetyLevel.BLOCKED,
            )
            event_registry.emit(
                "safety.rate_limit.exceeded",
                payload={"device_id": device_id, "action": action},
            )
            return result

        # 4. Reject explicitly BLOCKED safety level
        if safety_level == SafetyLevel.BLOCKED:
            result = SafetyCheckResult(
                allowed=False,
                reason=f"Action '{action}' blocked by safety level BLOCKED",
                safety_level=SafetyLevel.BLOCKED,
            )
            self._emit_blocked(device_id, action, result.reason)
            return result

        # 5. Write command approval check
        if action in self.WRITE_ACTIONS and safety_level == SafetyLevel.REQUIRES_APPROVAL:
            if not approved:
                result = SafetyCheckResult(
                    allowed=False,
                    reason=(
                        f"Write action '{action}' requires approval"
                        f" at safety level {safety_level.value}"
                    ),
                    safety_level=SafetyLevel.REQUIRES_APPROVAL,
                )
                self._emit_blocked(device_id, action, result.reason)
                return result

        # All checks passed — record command and approve
        self._record_command(device_id, action)
        event_registry.emit(
            "safety.command.approved",
            payload={"device_id": device_id, "action": action},
        )
        return SafetyCheckResult(allowed=True, safety_level=safety_level)

    def _check_rate_limit(self, device_id: str) -> bool:
        """Check if a device has exceeded its rate limit."""
        now = time.monotonic()
        cutoff = now - self._rate_limit_window
        with self._lock:
            timestamps = self._command_history[device_id]
            # Prune old entries
            self._command_history[device_id] = [t for t in timestamps if t > cutoff]
            return len(self._command_history[device_id]) < self._max_commands_per_minute

    def _record_command(self, device_id: str, action: str) -> None:
        """Record a command timestamp for rate limiting."""
        with self._lock:
            self._command_history[device_id].append(time.monotonic())

    def _emit_blocked(self, device_id: str, action: str, reason: str) -> None:
        event_registry.emit(
            "safety.command.blocked",
            payload={"device_id": device_id, "action": action, "reason": reason},
        )
