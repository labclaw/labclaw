"""BDD step definitions for L2 Plugin Security.

Covers: plugin allowlist enforcement, disable switches, secure directory
validation, and combined load_all constraints.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, then, when

import labclaw.plugins.loader as _loader_mod
from labclaw.core.events import event_registry
from labclaw.plugins.base import PluginMetadata
from labclaw.plugins.loader import PluginLoader
from labclaw.plugins.registry import PluginRegistry

# ---------------------------------------------------------------------------
# Minimal plugin stub
# ---------------------------------------------------------------------------


class _SecTestPlugin:
    """Stub plugin for security scenario wiring."""

    metadata = PluginMetadata(
        name="trusted-plugin",
        version="0.1.0",
        description="Security test stub",
        plugin_type="device",
    )

    def register_devices(self) -> list[dict[str, Any]]:
        return []

    def get_driver(self, device_type: str) -> Any:
        return None


# ---------------------------------------------------------------------------
# State container
# ---------------------------------------------------------------------------


class _Ctx:
    """Mutable test context passed through scenario fixtures."""

    def __init__(self) -> None:
        self.found: list[str] = []
        self.loaded_events: list[Any] = []
        self.error_events: list[Any] = []
        self.mock_ep: MagicMock | None = None
        self.plugin_dir: Path | None = None
        self.secure_check_result: bool | None = None


# ---------------------------------------------------------------------------
# Given — allowlist / env vars
# ---------------------------------------------------------------------------


@given(
    parsers.parse('the plugin allowlist contains "{allowlist_value}"'),
    target_fixture="sec_ctx",
)
def given_allowlist(monkeypatch: pytest.MonkeyPatch, allowlist_value: str) -> _Ctx:
    monkeypatch.setenv("LABCLAW_PLUGIN_ALLOWLIST", allowlist_value)
    # Ensure entry-point discovery and local discovery are enabled
    monkeypatch.delenv("LABCLAW_ENABLE_ENTRYPOINT_PLUGINS", raising=False)
    monkeypatch.delenv("LABCLAW_ENABLE_LOCAL_PLUGINS", raising=False)
    return _Ctx()


@given(
    "no allowlist is configured",
    target_fixture="sec_ctx",
)
def given_no_allowlist(monkeypatch: pytest.MonkeyPatch) -> _Ctx:
    monkeypatch.delenv("LABCLAW_PLUGIN_ALLOWLIST", raising=False)
    return _Ctx()


@given(parsers.parse('LABCLAW_PLUGIN_ALLOW_ALL is "{value}"'))
def given_allow_all(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("LABCLAW_PLUGIN_ALLOW_ALL", value)


@given("PYTEST_CURRENT_TEST is not set")
def given_not_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


@given(
    parsers.parse('LABCLAW_ENABLE_ENTRYPOINT_PLUGINS is "{value}"'),
    target_fixture="sec_ctx",
)
def given_ep_enabled_flag(monkeypatch: pytest.MonkeyPatch, value: str) -> _Ctx:
    monkeypatch.setenv("LABCLAW_ENABLE_ENTRYPOINT_PLUGINS", value)
    monkeypatch.delenv("LABCLAW_PLUGIN_ALLOWLIST", raising=False)
    return _Ctx()


@given(
    parsers.parse('LABCLAW_ENABLE_LOCAL_PLUGINS is "{value}"'),
    target_fixture="sec_ctx",
)
def given_local_enabled_flag(monkeypatch: pytest.MonkeyPatch, value: str) -> _Ctx:
    monkeypatch.setenv("LABCLAW_ENABLE_LOCAL_PLUGINS", value)
    monkeypatch.delenv("LABCLAW_PLUGIN_ALLOWLIST", raising=False)
    return _Ctx()


@given(
    parsers.parse('a local plugin directory with a plugin named "{plugin_name}"'),
)
def given_named_local_plugin(
    tmp_path: Path,
    plugin_name: str,
    sec_ctx: _Ctx,
) -> None:
    plugin_dir = tmp_path / plugin_name
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text(
        f"from labclaw.plugins.base import PluginMetadata\n"
        f"class P:\n"
        f"    metadata = PluginMetadata(name='{plugin_name}', version='0.1.0',\n"
        f"        description='test', plugin_type='device')\n"
        f"    def register_devices(self): return []\n"
        f"    def get_driver(self, dt): return None\n"
        f"def create_plugin(): return P()\n"
    )
    sec_ctx.plugin_dir = tmp_path


@given("a local plugin directory with a valid plugin")
def given_valid_local_plugin(tmp_path: Path, sec_ctx: _Ctx) -> None:
    plugin_dir = tmp_path / "good_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text(
        "from labclaw.plugins.base import PluginMetadata\n"
        "class P:\n"
        "    metadata = PluginMetadata(name='good-plugin', version='0.1.0',\n"
        "        description='ok', plugin_type='device')\n"
        "    def register_devices(self): return []\n"
        "    def get_driver(self, dt): return None\n"
        "def create_plugin(): return P()\n"
    )
    sec_ctx.plugin_dir = tmp_path


@given("a local plugin directory that is world-writable", target_fixture="sec_ctx")
def given_world_writable_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> _Ctx:
    monkeypatch.delenv("LABCLAW_PLUGIN_ALLOWLIST", raising=False)
    monkeypatch.delenv("LABCLAW_ENABLE_LOCAL_PLUGINS", raising=False)
    monkeypatch.delenv("LABCLAW_ENABLE_ENTRYPOINT_PLUGINS", raising=False)
    ctx = _Ctx()
    plugin_dir = tmp_path / "unsafe_plugin"
    plugin_dir.mkdir()
    os.chmod(plugin_dir, 0o777)
    (plugin_dir / "__init__.py").write_text("def create_plugin(): return None\n")
    ctx.plugin_dir = tmp_path
    return ctx


@given("a local plugin directory that is a symlink", target_fixture="sec_ctx")
def given_symlinked_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> _Ctx:
    monkeypatch.delenv("LABCLAW_PLUGIN_ALLOWLIST", raising=False)
    monkeypatch.delenv("LABCLAW_ENABLE_LOCAL_PLUGINS", raising=False)
    monkeypatch.delenv("LABCLAW_ENABLE_ENTRYPOINT_PLUGINS", raising=False)
    ctx = _Ctx()
    real_dir = tmp_path / "real_plugin"
    real_dir.mkdir()
    (real_dir / "__init__.py").write_text("def create_plugin(): return None\n")
    link_dir = tmp_path / "link_plugin"
    link_dir.symlink_to(real_dir, target_is_directory=True)
    ctx.plugin_dir = tmp_path
    return ctx


@given(
    "a plugin directory where os.getuid raises OSError",
    target_fixture="sec_ctx",
)
def given_uid_error_dir(tmp_path: Path) -> _Ctx:
    ctx = _Ctx()
    plugin_dir = tmp_path / "uid_error_plugin"
    plugin_dir.mkdir()
    with patch.object(_loader_mod.os, "getuid", side_effect=OSError("uid error")):
        ctx.secure_check_result = PluginLoader._is_secure_plugin_dir(plugin_dir)
    return ctx


@given(
    "a plugin directory where path.stat raises OSError",
    target_fixture="sec_ctx",
)
def given_stat_error_dir(tmp_path: Path) -> _Ctx:
    ctx = _Ctx()
    plugin_dir = tmp_path / "stat_error_plugin"
    plugin_dir.mkdir()
    with patch.object(Path, "stat", side_effect=OSError("stat error")):
        ctx.secure_check_result = PluginLoader._is_secure_plugin_dir(plugin_dir)
    return ctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I discover entry-point plugin "{ep_name}"'),
)
def when_discover_ep(sec_ctx: _Ctx, ep_name: str) -> None:
    event_registry.subscribe("infra.plugin.loaded", sec_ctx.loaded_events.append)

    mock_ep = MagicMock()
    mock_ep.name = ep_name
    mock_ep.load.return_value = _SecTestPlugin
    sec_ctx.mock_ep = mock_ep

    reg = PluginRegistry()
    loader = PluginLoader(registry=reg)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        sec_ctx.found = loader.discover_entry_points()


@when("I run entry-point discovery")
def when_run_ep_discovery(sec_ctx: _Ctx) -> None:
    event_registry.subscribe("infra.plugin.loaded", sec_ctx.loaded_events.append)

    mock_ep = MagicMock()
    mock_ep.name = "some-plugin"
    sec_ctx.mock_ep = mock_ep

    reg = PluginRegistry()
    loader = PluginLoader(registry=reg)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        sec_ctx.found = loader.discover_entry_points()


@when("I run local plugin discovery")
def when_run_local_discovery(sec_ctx: _Ctx) -> None:
    event_registry.subscribe("infra.plugin.loaded", sec_ctx.loaded_events.append)
    event_registry.subscribe("infra.plugin.error", sec_ctx.error_events.append)

    reg = PluginRegistry()
    loader = PluginLoader(registry=reg)
    assert sec_ctx.plugin_dir is not None, "plugin_dir not set by Given step"
    sec_ctx.found = loader.discover_local(sec_ctx.plugin_dir)


@when("I call load_all with that directory")
def when_call_load_all_with_dir(sec_ctx: _Ctx) -> None:
    event_registry.subscribe("infra.plugin.loaded", sec_ctx.loaded_events.append)

    reg = PluginRegistry()
    loader = PluginLoader(registry=reg)
    assert sec_ctx.plugin_dir is not None, "plugin_dir not set by Given step"
    with patch("importlib.metadata.entry_points", return_value=[]):
        sec_ctx.found = loader.load_all(local_dir=sec_ctx.plugin_dir)


@when("I call load_all with no local directory")
def when_call_load_all_no_dir(sec_ctx: _Ctx) -> None:
    event_registry.subscribe("infra.plugin.loaded", sec_ctx.loaded_events.append)

    reg = PluginRegistry()
    loader = PluginLoader(registry=reg)
    with patch("importlib.metadata.entry_points", return_value=[]):
        sec_ctx.found = loader.load_all(local_dir=None)


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("{count:d} plugin is loaded"))
def then_n_plugins_singular(sec_ctx: _Ctx, count: int) -> None:
    assert len(sec_ctx.found) == count, (
        f"Expected {count} plugin(s) loaded, got {sec_ctx.found}"
    )


@then(parsers.parse("{count:d} plugins are loaded"))
def then_n_plugins(sec_ctx: _Ctx, count: int) -> None:
    assert len(sec_ctx.found) == count, (
        f"Expected {count} plugin(s) loaded, got {sec_ctx.found}"
    )


@then(parsers.parse('an infra.plugin.loaded event is emitted for "{name}"'))
def then_loaded_event_for(sec_ctx: _Ctx, name: str) -> None:
    names = [e.payload.get("name") for e in sec_ctx.loaded_events]
    assert name in names, (
        f"Expected infra.plugin.loaded for {name!r}, got {names}"
    )


@then("no infra.plugin.loaded event is emitted")
def then_no_loaded_event(sec_ctx: _Ctx) -> None:
    assert sec_ctx.loaded_events == [], (
        f"Expected no infra.plugin.loaded events, got {sec_ctx.loaded_events}"
    )


@then("the entry-point ep.load was never called")
def then_ep_load_not_called(sec_ctx: _Ctx) -> None:
    if sec_ctx.mock_ep is not None:
        sec_ctx.mock_ep.load.assert_not_called()


@then("an infra.plugin.error event is emitted for that directory")
def then_error_event_for_dir(sec_ctx: _Ctx) -> None:
    assert sec_ctx.error_events, (
        "Expected at least one infra.plugin.error event"
    )


@then(parsers.parse('the allowlist check for "{name}" returns denied'))
def then_allowlist_denied(name: str) -> None:
    result = PluginLoader._plugin_allowed(name)
    assert result is False, f"Expected denied, but {name!r} was permitted"


@then(parsers.parse('the allowlist check for "{name}" returns permitted'))
def then_allowlist_permitted(name: str) -> None:
    result = PluginLoader._plugin_allowed(name)
    assert result is True, f"Expected permitted, but {name!r} was denied"


@then("_is_secure_plugin_dir returns False")
def then_insecure_dir(sec_ctx: _Ctx) -> None:
    assert sec_ctx.secure_check_result is False, (
        f"Expected _is_secure_plugin_dir to return False, got {sec_ctx.secure_check_result}"
    )
