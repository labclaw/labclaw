# Plugin Development Guide

LabClaw uses a plugin system to extend functionality without modifying core code.
Plugins are standard Python packages discovered via entry points at startup.

---

## Plugin Types

LabClaw defines three plugin protocols. Each adds a different kind of extension.

| Type | Protocol | What it adds |
|------|----------|-------------|
| **Device** | `DevicePlugin` | Hardware drivers for new instruments |
| **Domain** | `DomainPlugin` | Domain-specific graph nodes, sentinel rules, hypothesis templates |
| **Analysis** | `AnalysisPlugin` | Custom mining algorithms and validators |

### DevicePlugin

```python
class DevicePlugin(Protocol):
    metadata: PluginMetadata

    def register_devices(self) -> list[dict[str, Any]]: ...
    def get_driver(self, device_type: str) -> Any: ...
```

### DomainPlugin

```python
class DomainPlugin(Protocol):
    metadata: PluginMetadata

    def get_sample_node_types(self) -> dict[str, type]: ...
    def get_sentinel_rules(self) -> list[dict[str, Any]]: ...
    def get_hypothesis_templates(self) -> list[dict[str, Any]]: ...
```

### AnalysisPlugin

```python
class AnalysisPlugin(Protocol):
    metadata: PluginMetadata

    def get_mining_algorithms(self) -> list[dict[str, Any]]: ...
    def get_validators(self) -> list[dict[str, Any]]: ...
```

---

## Quick Start: Scaffold a Plugin

Use the built-in scaffolding tool:

```bash
labclaw plugin create my-lab-pack --type domain
cd my-lab-pack
pip install -e .
```

This creates a ready-to-edit Python package:

```
my-lab-pack/
  pyproject.toml         # Entry points pre-configured
  src/my_lab_pack/
    __init__.py          # Plugin class with protocol stubs
  tests/
    __init__.py
  README.md
```

After `pip install -e .`, LabClaw discovers it automatically on next startup.

---

## Step-by-Step: Creating a Domain Plugin

Domain plugins add knowledge specific to your research area.

### 1. Scaffold

```bash
labclaw plugin create labclaw-chemistry --type domain
cd labclaw-chemistry
```

### 2. Define Custom Node Types

Edit `src/labclaw_chemistry/__init__.py`:

```python
"""LabClaw domain plugin: labclaw-chemistry."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from labclaw.core.graph import GraphNode
from labclaw.plugins.base import PluginMetadata


class CompoundNode(GraphNode):
    """A chemical compound in the knowledge graph."""

    node_type: str = "compound"
    formula: str = ""
    molecular_weight: float = 0.0
    smiles: str = ""


class LabclawChemistry:
    metadata = PluginMetadata(
        name="labclaw-chemistry",
        version="0.1.0",
        description="Chemistry domain pack for LabClaw",
        author="Your Name",
        plugin_type="domain",
    )

    def get_sample_node_types(self) -> dict[str, type]:
        return {"compound": CompoundNode}

    def get_sentinel_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "ph_out_of_range",
                "description": "pH reading outside safe range",
                "condition": {"column": "pH", "min": 2.0, "max": 12.0},
            },
        ]

    def get_hypothesis_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "template": "Changing {parameter} from {old} to {new} will affect yield by {direction}",
                "required_evidence": ["correlation"],
            },
        ]


def create_plugin() -> LabclawChemistry:
    return LabclawChemistry()
```

### 3. Configure Entry Points

The scaffold already creates the correct `pyproject.toml`:

```toml
[project.entry-points."labclaw.plugins"]
labclaw-chemistry = "labclaw_chemistry:create_plugin"
```

The entry point group must be `labclaw.plugins`. The value is `module:factory_function`.

### 4. Install and Verify

```bash
pip install -e .
labclaw plugin list
```

You should see your plugin in the output:

```
NAME                           TYPE         VERSION    DESCRIPTION
labclaw-chemistry              domain       0.1.0      Chemistry domain pack for LabClaw
```

---

## Step-by-Step: Creating a Device Driver Plugin

Device plugins add support for new lab instruments.

### 1. Scaffold

```bash
labclaw plugin create labclaw-microscope --type device
cd labclaw-microscope
```

### 2. Implement the Driver

Create a driver that implements the `DeviceDriver` protocol:

```python
"""LabClaw device plugin: labclaw-microscope."""

from __future__ import annotations

from typing import Any

from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.interfaces.driver import DeviceDriver
from labclaw.hardware.schemas import HardwareCommand
from labclaw.plugins.base import PluginMetadata


class MicroscopeDriver:
    """Driver for Acme Microscope 3000."""

    def __init__(self, connection_string: str = "localhost:5000") -> None:
        self._connection = connection_string
        self._device_id = "microscope-acme-3000"
        self._connected = False

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def device_type(self) -> str:
        return "microscope"

    async def connect(self) -> bool:
        # Connect to the microscope hardware
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def read(self) -> dict[str, Any]:
        # Read current state from microscope
        return {
            "magnification": 40,
            "light_intensity": 75,
            "stage_x": 100.0,
            "stage_y": 200.0,
        }

    async def write(self, command: HardwareCommand) -> bool:
        # Send command to microscope
        return True

    async def status(self) -> DeviceStatus:
        return DeviceStatus.ONLINE if self._connected else DeviceStatus.OFFLINE


class LabclawMicroscope:
    metadata = PluginMetadata(
        name="labclaw-microscope",
        version="0.1.0",
        description="Acme Microscope 3000 driver",
        author="Your Name",
        plugin_type="device",
    )

    def register_devices(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "Acme Microscope 3000",
                "device_type": "microscope",
                "model": "AM-3000",
                "manufacturer": "Acme",
            },
        ]

    def get_driver(self, device_type: str) -> Any:
        if device_type == "microscope":
            return MicroscopeDriver()
        raise NotImplementedError(device_type)


def create_plugin() -> LabclawMicroscope:
    return LabclawMicroscope()
```

### 3. Install

```bash
pip install -e .
labclaw plugin list
```

---

## Step-by-Step: Creating an Analysis Plugin

Analysis plugins add custom pattern mining algorithms.

```python
from __future__ import annotations

from typing import Any

from labclaw.plugins.base import PluginMetadata


class LabclawSpectral:
    metadata = PluginMetadata(
        name="labclaw-spectral",
        version="0.1.0",
        description="Spectral analysis algorithms",
        plugin_type="analysis",
    )

    def get_mining_algorithms(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "spectral_coherence",
                "description": "Cross-spectral coherence between signals",
                "function": self._compute_coherence,
            },
        ]

    def get_validators(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "spectral_significance",
                "description": "Permutation test for spectral peaks",
                "function": self._validate_peaks,
            },
        ]

    def _compute_coherence(self, data: list[dict]) -> list[dict]:
        # Implementation here
        return []

    def _validate_peaks(self, pattern: dict, data: list[dict]) -> dict:
        # Implementation here
        return {"valid": True}


def create_plugin() -> LabclawSpectral:
    return LabclawSpectral()
```

---

## Plugin Discovery

LabClaw discovers plugins from two sources:

### 1. Entry Points (recommended)

Add to your plugin's `pyproject.toml`:

```toml
[project.entry-points."labclaw.plugins"]
my-plugin = "my_package:create_plugin"
```

Entry point plugins work anywhere LabClaw is installed.

### 2. Local Directory

Place plugin directories in `plugins/` under your project root. Each must contain
an `__init__.py` with a `create_plugin()` factory function.

```
my-lab/
  plugins/
    my-local-plugin/
      __init__.py        # Must define create_plugin()
```

Local plugins are loaded at daemon startup if the directory exists.

---

## Testing Your Plugin

### Unit Test

```python
import pytest
from labclaw_chemistry import create_plugin


def test_plugin_metadata():
    plugin = create_plugin()
    assert plugin.metadata.name == "labclaw-chemistry"
    assert plugin.metadata.plugin_type == "domain"


def test_sample_node_types():
    plugin = create_plugin()
    types = plugin.get_sample_node_types()
    assert "compound" in types


def test_sentinel_rules():
    plugin = create_plugin()
    rules = plugin.get_sentinel_rules()
    assert len(rules) > 0
    assert rules[0]["name"] == "ph_out_of_range"
```

### Integration Test

Verify it loads correctly with LabClaw:

```python
from labclaw.plugins.loader import PluginLoader
from labclaw.plugins.registry import PluginRegistry


def test_plugin_loads():
    registry = PluginRegistry()
    loader = PluginLoader(registry=registry)
    loaded = loader.discover_entry_points()
    assert "labclaw-chemistry" in loaded
```

Run tests:

```bash
cd labclaw-chemistry
pytest
```

---

## Publishing to PyPI

1. Update version in `pyproject.toml`.
2. Build:

```bash
pip install build
python -m build
```

3. Upload:

```bash
pip install twine
twine upload dist/*
```

Users install with:

```bash
pip install labclaw-chemistry
```

LabClaw discovers it automatically via the `labclaw.plugins` entry point group.
