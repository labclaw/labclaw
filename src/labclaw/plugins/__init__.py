"""Plugin system — loader, registry, and three plugin protocol types."""

from __future__ import annotations

from labclaw.plugins.base import AnalysisPlugin, DevicePlugin, DomainPlugin, PluginMetadata
from labclaw.plugins.loader import PluginLoader
from labclaw.plugins.registry import PluginRegistry, plugin_registry

__all__ = [
    "AnalysisPlugin",
    "DevicePlugin",
    "DomainPlugin",
    "PluginLoader",
    "PluginMetadata",
    "PluginRegistry",
    "plugin_registry",
]
