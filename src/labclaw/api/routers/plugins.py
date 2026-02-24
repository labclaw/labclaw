"""Plugin registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from labclaw.plugins.base import PluginMetadata

router = APIRouter()


@router.get("/")
def list_plugins() -> list[PluginMetadata]:
    """List all registered plugins."""
    from labclaw.plugins.registry import plugin_registry
    return plugin_registry.list_plugins()


@router.get("/by-type/{plugin_type}")
def list_plugins_by_type(plugin_type: str) -> list[PluginMetadata]:
    """List plugins filtered by type (device, domain, analysis)."""
    from labclaw.plugins.registry import plugin_registry
    plugins = plugin_registry.get_by_type(plugin_type)
    return [p.metadata for p in plugins]
