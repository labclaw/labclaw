"""Plugin registry — central store for all loaded plugins.

Spec: docs/specs/cross-foundations.md
"""

from __future__ import annotations

import logging

from labclaw.core.events import event_registry
from labclaw.plugins.base import AnalysisPlugin, DevicePlugin, DomainPlugin, PluginMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register plugin events at import time
# ---------------------------------------------------------------------------

_PLUGIN_EVENTS = [
    "infra.plugin.loaded",
    "infra.plugin.registered",
    "infra.plugin.error",
]

for _evt in _PLUGIN_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


AnyPlugin = DevicePlugin | DomainPlugin | AnalysisPlugin


class PluginRegistry:
    """Central registry for all plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, AnyPlugin] = {}
        self._by_type: dict[str, list[str]] = {"device": [], "domain": [], "analysis": []}

    def register(self, plugin: AnyPlugin) -> None:
        """Register a plugin. Raises ValueError if name already registered."""
        name = plugin.metadata.name
        if name in self._plugins:
            raise ValueError(f"Plugin {name!r} already registered")

        plugin_type = plugin.metadata.plugin_type
        self._plugins[name] = plugin
        self._by_type.setdefault(plugin_type, []).append(name)

        logger.info("Registered plugin %s (type=%s)", name, plugin_type)
        event_registry.emit("infra.plugin.registered", {"name": name, "type": plugin_type})

    def get(self, name: str) -> AnyPlugin:
        """Get plugin by name. Raises KeyError if not found."""
        if name not in self._plugins:
            raise KeyError(f"Plugin {name!r} not found")
        return self._plugins[name]

    def get_by_type(self, plugin_type: str) -> list[AnyPlugin]:
        """Get all plugins of a given type."""
        names = self._by_type.get(plugin_type, [])
        return [self._plugins[n] for n in names if n in self._plugins]

    def list_plugins(self) -> list[PluginMetadata]:
        """List all registered plugin metadata."""
        return [p.metadata for p in self._plugins.values()]


# Global singleton
plugin_registry = PluginRegistry()
