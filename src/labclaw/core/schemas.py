"""Core schemas — base types, enums, and conventions for all layers.

Spec: docs/specs/cross-foundations.md
Design doc: sections 3, 4.3, 8.3
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Layer(str, Enum):
    HARDWARE = "hardware"
    INFRA = "infra"
    DISCOVERY = "discovery"
    OPTIMIZATION = "optimization"
    VALIDATION = "validation"
    MEMORY = "memory"
    PERSONA = "persona"
    EVOLUTION = "evolution"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    CALIBRATING = "calibrating"
    IN_USE = "in_use"
    RESERVED = "reserved"


class DeviceInterfaceType(str, Enum):
    FILE_BASED = "file_based"
    SERIAL = "serial"
    NETWORK_API = "network_api"
    GPIO_DAQ = "gpio_daq"
    SOFTWARE_BRIDGE = "software_bridge"


class SafetyLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    REQUIRES_APPROVAL = "requires_approval"
    BLOCKED = "blocked"


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    TESTING = "testing"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class EvolutionTarget(str, Enum):
    ANALYSIS_PARAMS = "analysis_params"
    PROMPTS = "prompts"
    ROUTING = "routing"
    HEURISTICS = "heuristics"
    STRATEGY = "strategy"


class EvolutionStage(str, Enum):
    BACKTEST = "backtest"
    SHADOW = "shadow"
    CANARY = "canary"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"


class QualityLevel(str, Enum):
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MemberRole(str, Enum):
    PI = "pi"
    POSTDOC = "postdoc"
    GRADUATE = "graduate"
    UNDERGRADUATE = "undergraduate"
    TECHNICIAN = "technician"
    DIGITAL_INTERN = "digital_intern"
    DIGITAL_ANALYST = "digital_analyst"
    DIGITAL_SPECIALIST = "digital_specialist"


# ---------------------------------------------------------------------------
# Event naming
# ---------------------------------------------------------------------------

class EventName(BaseModel):
    """Validated event name: {layer}.{module}.{action}."""

    layer: str
    module: str
    action: str

    @field_validator("layer", "module", "action")
    @classmethod
    def _no_dots_or_empty(cls, v: str) -> str:
        if not v or "." in v:
            raise ValueError(f"Event name component must be non-empty and dot-free, got {v!r}")
        return v

    @property
    def full(self) -> str:
        return f"{self.layer}.{self.module}.{self.action}"

    def __str__(self) -> str:
        return self.full

    @classmethod
    def parse(cls, name: str) -> EventName:
        parts = name.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"Event name must be '{{layer}}.{{module}}.{{action}}', got {name!r}"
            )
        return cls(layer=parts[0], module=parts[1], action=parts[2])


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------

def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class LabEvent(BaseModel):
    """Base class for all events emitted by any layer."""

    event_id: str = Field(default_factory=_uuid)
    event_name: EventName
    timestamp: datetime = Field(default_factory=_now)
    source_layer: Layer
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    actor_id: str | None = None


# ---------------------------------------------------------------------------
# Common value objects
# ---------------------------------------------------------------------------

class FileReference(BaseModel):
    """Reference to a file with integrity check."""

    path: Path
    sha256: str | None = None
    size_bytes: int | None = None
    mime_type: str | None = None


class QualityMetric(BaseModel):
    """A single quality measurement."""

    name: str
    value: float
    unit: str | None = None
    level: QualityLevel = QualityLevel.UNKNOWN
    timestamp: datetime = Field(default_factory=_now)
