"""Hardware layer Pydantic schemas.

Spec: docs/specs/L1-hardware.md
Design doc: section 3.1 (Hardware Layer)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.schemas import DeviceInterfaceType, DeviceStatus, SafetyLevel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class DeviceCapabilities(BaseModel):
    """What a device can observe, control, and produce."""

    can_observe: list[str] = Field(default_factory=list)
    can_control: list[str] = Field(default_factory=list)
    data_formats: list[str] = Field(default_factory=list)
    supports_streaming: bool = False


class DeviceRecord(BaseModel):
    """Full identity and state of a registered device."""

    device_id: str = Field(default_factory=_uuid)
    name: str
    device_type: str
    model: str = ""
    manufacturer: str = ""
    location: str = ""
    interface_type: DeviceInterfaceType = DeviceInterfaceType.FILE_BASED
    status: DeviceStatus = DeviceStatus.OFFLINE
    capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)
    watch_path: Path | None = None
    registered_at: datetime = Field(default_factory=_now)
    last_seen: datetime = Field(default_factory=_now)


class HardwareCommand(BaseModel):
    """A command to be executed on a device."""

    command_id: str = Field(default_factory=_uuid)
    device_id: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_by: str | None = None
    approved_by: str | None = None


class SafetyCheckResult(BaseModel):
    """Result of a hardware safety check."""

    device_id: str
    check_type: str
    passed: bool
    level: SafetyLevel
    details: str = ""
    timestamp: datetime = Field(default_factory=_now)


class CalibrationRecord(BaseModel):
    """Record of a device calibration event."""

    device_id: str
    calibrated_by: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_now)
    next_due: datetime | None = None
