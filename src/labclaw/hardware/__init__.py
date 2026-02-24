"""Hardware — device management, interfaces, and safety.

Bridges the physical lab (instruments, sensors, actuators) to the
software layer (agents, memory, pipelines). Every device is a managed
resource with its own SOUL.md and MEMORY.md, just like human and
digital members.
"""

from labclaw.hardware.manager import HardwareManager
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.safety import HardwareSafetyChecker
from labclaw.hardware.schemas import (
    CalibrationRecord,
    DeviceCapabilities,
    DeviceRecord,
    HardwareCommand,
    SafetyCheckResult,
)

__all__ = [
    "CalibrationRecord",
    "DeviceCapabilities",
    "DeviceRecord",
    "DeviceRegistry",
    "HardwareCommand",
    "HardwareManager",
    "HardwareSafetyChecker",
    "SafetyCheckResult",
]
