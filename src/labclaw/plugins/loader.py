"""Plugin loader — discovers plugins from entry points and local directories.

Spec: docs/specs/cross-foundations.md
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import logging
import os
import stat
from pathlib import Path

from labclaw.core.events import event_registry
from labclaw.plugins.registry import PluginRegistry, plugin_registry

logger = logging.getLogger(__name__)
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _running_under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


class PluginLoader:
    """Discovers and loads plugins from entry points and local directories."""

    def __init__(self, registry: PluginRegistry | None = None) -> None:
        self._registry = registry or plugin_registry

    @staticmethod
    def _plugin_allowed(name: str) -> bool:
        raw = os.environ.get("LABCLAW_PLUGIN_ALLOWLIST", "")
        allowlist = {item.strip() for item in raw.split(",") if item.strip()}
        if not allowlist:
            return _running_under_pytest() or _env_bool("LABCLAW_PLUGIN_ALLOW_ALL", False)
        return name in allowlist

    @staticmethod
    def _is_secure_plugin_dir(path: Path) -> bool:
        """Basic local plugin dir hardening: reject symlink/world-writable dirs."""
        try:
            if path.is_symlink():
                return False
            st = path.stat()
        except OSError:
            return False
        if st.st_mode & stat.S_IWOTH:
            return False
        try:
            return st.st_uid == os.getuid()
        except OSError:
            return False

    def discover_entry_points(self) -> list[str]:
        """Find plugins via Python entry_points (group='labclaw.plugins')."""
        if not _env_bool("LABCLAW_ENABLE_ENTRYPOINT_PLUGINS", _running_under_pytest()):
            logger.info("Entry-point plugins are disabled")
            return []

        plugins_found = []
        for ep in importlib.metadata.entry_points(group="labclaw.plugins"):
            if not self._plugin_allowed(ep.name):
                logger.info("Skipping entry-point plugin %s (not in allowlist)", ep.name)
                continue
            try:
                plugin_cls = ep.load()
                plugin = plugin_cls()
                self._registry.register(plugin)
                plugins_found.append(ep.name)
                event_registry.emit(
                    "infra.plugin.loaded", {"name": ep.name, "source": "entry_point"}
                )
            except Exception as e:
                logger.warning("Failed to load plugin %s: %s", ep.name, e)
                event_registry.emit("infra.plugin.error", {"name": ep.name, "error": str(e)})
        return plugins_found

    def discover_local(self, path: Path) -> list[str]:
        """Find plugins in local plugins/ directory.

        Each subdirectory must contain an ``__init__.py`` with a
        ``create_plugin()`` factory function.
        """
        plugins_found = []
        if not _env_bool("LABCLAW_ENABLE_LOCAL_PLUGINS", _running_under_pytest()):
            logger.info("Local plugins are disabled")
            return plugins_found
        if not path.exists() or not path.is_dir():
            return plugins_found
        for subdir in path.iterdir():
            if not subdir.is_dir():
                continue
            if not self._is_secure_plugin_dir(subdir):
                logger.warning("Skipping insecure local plugin directory: %s", subdir)
                event_registry.emit(
                    "infra.plugin.error",
                    {"name": subdir.name, "error": "insecure_dir"},
                )
                continue
            if not self._plugin_allowed(subdir.name):
                logger.info("Skipping local plugin %s (not in allowlist)", subdir.name)
                continue
            init_file = subdir / "__init__.py"
            if not init_file.exists():
                continue
            module_name = subdir.name
            try:
                spec = importlib.util.spec_from_file_location(module_name, init_file)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[attr-defined]
                factory = getattr(module, "create_plugin", None)
                if factory is None:
                    logger.debug("Skipping %s: no create_plugin() found", subdir)
                    continue
                plugin = factory()
                self._registry.register(plugin)
                plugins_found.append(module_name)
                event_registry.emit("infra.plugin.loaded", {"name": module_name, "source": "local"})
            except Exception as e:
                logger.warning("Failed to load local plugin %s: %s", subdir.name, e)
                event_registry.emit("infra.plugin.error", {"name": subdir.name, "error": str(e)})
        return plugins_found

    def load_all(self, local_dir: Path | None = None) -> list[str]:
        """Discover and load all plugins."""
        loaded = self.discover_entry_points()
        if local_dir and local_dir.exists():
            loaded.extend(self.discover_local(local_dir))
        return loaded
