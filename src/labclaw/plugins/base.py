"""Plugin protocol definitions — three plugin types: device, domain, analysis.

Spec: docs/specs/cross-foundations.md
Design doc: section 3 (Architecture), plugin extension points
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class PluginMetadata(BaseModel):
    """Plugin identity."""

    name: str
    version: str
    description: str
    author: str = ""
    plugin_type: str  # "device", "domain", "analysis"


@runtime_checkable
class DevicePlugin(Protocol):
    """Adds hardware device drivers."""

    metadata: PluginMetadata

    def register_devices(self) -> list[dict[str, Any]]: ...

    def get_driver(self, device_type: str) -> Any: ...  # Returns DeviceDriver


@runtime_checkable
class DomainPlugin(Protocol):
    """Adds domain-specific knowledge."""

    metadata: PluginMetadata

    def get_sample_node_types(self) -> dict[str, type]: ...

    def get_sentinel_rules(self) -> list[dict[str, Any]]: ...

    def get_hypothesis_templates(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class AnalysisPlugin(Protocol):
    """Adds analysis algorithms."""

    metadata: PluginMetadata

    def get_mining_algorithms(self) -> list[dict[str, Any]]: ...

    def get_validators(self) -> list[dict[str, Any]]: ...
