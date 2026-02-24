# Cross-Cutting Foundations Spec

**Layer:** Cross-cutting (all layers depend on this)
**Design doc reference:** Sections 3 (Architecture), 4.3 (Node Metadata), 8.3 (Evolution History)

## Purpose

Defines the base types, enums, and conventions that all layers share. This is the "language" of LabClaw — every event, graph node, and data record builds on these foundations.

---

## Pydantic Schemas

### Enums

```python
class Layer(str, Enum):
    HARDWARE = "hardware"        # L1
    INFRA = "infra"              # L2
    DISCOVERY = "discovery"      # L3
    OPTIMIZATION = "optimization"# L3
    VALIDATION = "validation"    # L3
    MEMORY = "memory"            # L4
    PERSONA = "persona"          # L5
    EVOLUTION = "evolution"      # L5

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
```

### LabEvent Base

The base class for all events in the system.

```python
class EventName(BaseModel):
    """Validated event name following {layer}.{module}.{action} convention."""
    layer: str
    module: str
    action: str

    @property
    def full(self) -> str:
        return f"{self.layer}.{self.module}.{self.action}"

class LabEvent(BaseModel):
    """Base class for all events emitted by any layer."""
    event_id: str           # UUID
    event_name: EventName   # e.g. memory.tier_a.updated
    timestamp: datetime     # ISO 8601
    source_layer: Layer
    payload: dict[str, Any] # Event-specific data
    correlation_id: str | None = None  # Links related events
    actor_id: str | None = None        # Who/what triggered this
```

### FileReference

```python
class FileReference(BaseModel):
    """Reference to a file with integrity check."""
    path: Path
    sha256: str | None = None
    size_bytes: int | None = None
    mime_type: str | None = None
```

### QualityMetric

```python
class QualityMetric(BaseModel):
    """A single quality measurement."""
    name: str
    value: float
    unit: str | None = None
    level: QualityLevel = QualityLevel.UNKNOWN
    timestamp: datetime
```

---

## Event Naming Convention

All events follow the pattern: `{layer}.{module}.{action}`

- **layer**: One of the Layer enum values (lowercase)
- **module**: The submodule within the layer (e.g., `tier_a`, `device`, `hypothesis`)
- **action**: Past tense verb describing what happened (e.g., `created`, `updated`, `registered`)

Examples:
```
memory.tier_a.updated         # Markdown memory was modified
hardware.device.registered    # A device registered itself
discovery.hypothesis.created  # A hypothesis was generated
evolution.cycle.completed     # An evolution cycle finished
validation.report.generated   # A validation report was produced
hardware.safety.checked       # Safety check was performed
```

---

## Event Registry

```python
class EventRegistry:
    """Central registry for event types. Layers register their own events at import."""

    def register(name: str, schema: type[LabEvent]) -> None
    def emit(name: str, payload: dict) -> LabEvent
    def get_schema(name: str) -> type[LabEvent] | None
    def list_events() -> list[str]

# Global singleton
event_registry = EventRegistry()
```

Layers register events like:
```python
# In memory/markdown.py
from labclaw.core.events import event_registry
event_registry.register("memory.tier_a.updated", MemoryUpdatedEvent)
```

---

## Boundary Contracts

- All timestamps MUST be timezone-aware UTC (`datetime` with `tzinfo=UTC`)
- All IDs MUST be valid UUIDs (generated via `uuid.uuid4()`)
- All file paths MUST be `pathlib.Path` objects
- JSON serialization: numpy types cast with `int()` / `float()`
- Event names MUST pass `EventName` validation (3 dot-separated parts)

## Error Conditions

- Invalid event name format → `ValueError` with descriptive message
- Duplicate event registration → `ValueError` (each name registered once)
- Emit for unregistered event → `KeyError` with available events listed

## Storage

- Enums stored as string values (not ordinals)
- Events serialized to JSON for persistence / Redis Streams
- All Pydantic models use `model_dump(mode="json")` for serialization

## Acceptance Criteria

- [ ] All enums are importable from `labclaw.core.schemas`
- [ ] `LabEvent` validates event name format on construction
- [ ] `EventRegistry.register()` prevents duplicate registration
- [ ] `EventRegistry.emit()` creates event with auto-generated ID and timestamp
- [ ] Event names follow `{layer}.{module}.{action}` convention
- [ ] All timestamps are UTC
- [ ] All models serialize cleanly to JSON
