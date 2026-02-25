"""Tests for the plugin system: base, registry, loader, scaffold."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from labclaw.core.events import event_registry
from labclaw.plugins.base import AnalysisPlugin, DevicePlugin, DomainPlugin, PluginMetadata
from labclaw.plugins.loader import PluginLoader
from labclaw.plugins.registry import PluginRegistry
from labclaw.plugins.scaffold import scaffold_plugin

# ---------------------------------------------------------------------------
# Helpers — concrete plugin stubs
# ---------------------------------------------------------------------------


class StubDevicePlugin:
    metadata = PluginMetadata(
        name="test-device",
        version="0.1.0",
        description="A stub device plugin",
        plugin_type="device",
    )

    def register_devices(self) -> list[dict[str, Any]]:
        return [{"type": "camera"}]

    def get_driver(self, device_type: str) -> Any:
        return None


class StubDomainPlugin:
    metadata = PluginMetadata(
        name="test-domain",
        version="0.1.0",
        description="A stub domain plugin",
        plugin_type="domain",
    )

    def get_sample_node_types(self) -> dict[str, type]:
        return {}

    def get_sentinel_rules(self) -> list[dict[str, Any]]:
        return []

    def get_hypothesis_templates(self) -> list[dict[str, Any]]:
        return []


class StubAnalysisPlugin:
    metadata = PluginMetadata(
        name="test-analysis",
        version="0.1.0",
        description="A stub analysis plugin",
        plugin_type="analysis",
    )

    def get_mining_algorithms(self) -> list[dict[str, Any]]:
        return []

    def get_validators(self) -> list[dict[str, Any]]:
        return []


# ---------------------------------------------------------------------------
# PluginMetadata
# ---------------------------------------------------------------------------


class TestPluginMetadata:
    def test_create_basic(self) -> None:
        meta = PluginMetadata(name="foo", version="1.0", description="bar", plugin_type="device")
        assert meta.name == "foo"
        assert meta.version == "1.0"
        assert meta.author == ""

    def test_create_with_author(self) -> None:
        meta = PluginMetadata(
            name="foo",
            version="1.0",
            description="bar",
            plugin_type="domain",
            author="Alice",
        )
        assert meta.author == "Alice"

    def test_validation_missing_required(self) -> None:
        with pytest.raises(Exception):
            PluginMetadata(name="foo")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# PluginRegistry
# ---------------------------------------------------------------------------


class TestPluginRegistry:
    def test_register_device(self) -> None:
        reg = PluginRegistry()
        plugin = StubDevicePlugin()
        reg.register(plugin)
        assert reg.get("test-device") is plugin

    def test_register_domain(self) -> None:
        reg = PluginRegistry()
        plugin = StubDomainPlugin()
        reg.register(plugin)
        assert reg.get("test-domain") is plugin

    def test_register_analysis(self) -> None:
        reg = PluginRegistry()
        plugin = StubAnalysisPlugin()
        reg.register(plugin)
        assert reg.get("test-analysis") is plugin

    def test_duplicate_raises(self) -> None:
        reg = PluginRegistry()
        reg.register(StubDevicePlugin())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(StubDevicePlugin())

    def test_get_missing_raises(self) -> None:
        reg = PluginRegistry()
        with pytest.raises(KeyError, match="not found"):
            reg.get("nope")

    def test_list_plugins(self) -> None:
        reg = PluginRegistry()
        reg.register(StubDevicePlugin())
        reg.register(StubDomainPlugin())
        metas = reg.list_plugins()
        names = {m.name for m in metas}
        assert names == {"test-device", "test-domain"}

    def test_get_by_type(self) -> None:
        reg = PluginRegistry()
        dev = StubDevicePlugin()
        ana = StubAnalysisPlugin()
        reg.register(dev)
        reg.register(ana)
        assert reg.get_by_type("device") == [dev]
        assert reg.get_by_type("analysis") == [ana]
        assert reg.get_by_type("domain") == []

    def test_register_emits_event(self) -> None:
        reg = PluginRegistry()
        events: list = []
        event_registry.subscribe("infra.plugin.registered", events.append)
        reg.register(StubDevicePlugin())
        assert len(events) >= 1
        assert events[-1].payload["name"] == "test-device"


# ---------------------------------------------------------------------------
# PluginLoader
# ---------------------------------------------------------------------------


class TestPluginLoader:
    def test_discover_entry_points(self) -> None:
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)

        mock_ep = MagicMock()
        mock_ep.name = "mock-ep-plugin"
        mock_ep.load.return_value = StubDevicePlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            found = loader.discover_entry_points()

        assert found == ["mock-ep-plugin"]
        assert reg.get("test-device") is not None

    def test_discover_entry_points_error(self) -> None:
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)

        mock_ep = MagicMock()
        mock_ep.name = "bad-plugin"
        mock_ep.load.side_effect = ImportError("nope")

        events: list = []
        event_registry.subscribe("infra.plugin.error", events.append)

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            found = loader.discover_entry_points()

        assert found == []
        assert any(e.payload["name"] == "bad-plugin" for e in events)

    def test_discover_entry_points_disabled_when_flag_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        monkeypatch.setenv("LABCLAW_ENABLE_ENTRYPOINT_PLUGINS", "0")

        mock_ep = MagicMock()
        mock_ep.name = "disabled-plugin"
        mock_ep.load.return_value = StubDevicePlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            found = loader.discover_entry_points()

        assert found == []
        mock_ep.load.assert_not_called()

    def test_discover_local(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        init_file = plugin_dir / "__init__.py"
        init_file.write_text(
            "from labclaw.plugins.base import PluginMetadata\n"
            "class MyPlugin:\n"
            "    metadata = PluginMetadata(name='my-local', version='1.0', "
            "description='test', plugin_type='device')\n"
            "    def register_devices(self): return []\n"
            "    def get_driver(self, dt): return None\n"
            "def create_plugin(): return MyPlugin()\n"
        )

        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        found = loader.discover_local(tmp_path)
        assert "my_plugin" in found
        assert reg.get("my-local") is not None

    def test_discover_local_no_create_plugin(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "bad_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("x = 1\n")

        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        found = loader.discover_local(tmp_path)
        assert found == []

    def test_discover_local_disabled_when_flag_off(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("def create_plugin(): return None\n")
        monkeypatch.setenv("LABCLAW_ENABLE_LOCAL_PLUGINS", "0")

        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        found = loader.discover_local(tmp_path)
        assert found == []

    def test_discover_local_failing_plugin(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "fail_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("def create_plugin(): raise RuntimeError('boom')\n")

        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        events: list = []
        event_registry.subscribe("infra.plugin.error", events.append)
        found = loader.discover_local(tmp_path)
        assert found == []
        assert any(e.payload["name"] == "fail_plugin" for e in events)

    def test_discover_local_skips_files(self, tmp_path: Path) -> None:
        (tmp_path / "not_a_dir.txt").write_text("hi")
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        found = loader.discover_local(tmp_path)
        assert found == []

    def test_discover_local_skips_dir_without_init(self, tmp_path: Path) -> None:
        (tmp_path / "empty_dir").mkdir()
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        found = loader.discover_local(tmp_path)
        assert found == []

    def test_load_all(self, tmp_path: Path) -> None:
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)

        with patch("importlib.metadata.entry_points", return_value=[]):
            found = loader.load_all(local_dir=tmp_path)

        assert found == []

    def test_load_all_no_local_dir(self) -> None:
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)

        with patch("importlib.metadata.entry_points", return_value=[]):
            found = loader.load_all(local_dir=None)

        assert found == []

    def test_loaded_event_emitted(self) -> None:
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        events: list = []
        event_registry.subscribe("infra.plugin.loaded", events.append)

        mock_ep = MagicMock()
        mock_ep.name = "ev-plugin"
        mock_ep.load.return_value = StubAnalysisPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            loader.discover_entry_points()

        assert any(e.payload["name"] == "ev-plugin" for e in events)

    def test_discover_entry_points_skips_not_allowlisted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        monkeypatch.setenv("LABCLAW_PLUGIN_ALLOWLIST", "only-this")

        mock_ep = MagicMock()
        mock_ep.name = "ev-plugin"
        mock_ep.load.return_value = StubAnalysisPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            found = loader.discover_entry_points()

        assert found == []

    def test_plugin_allowlist_defaults_to_deny_outside_pytest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("LABCLAW_PLUGIN_ALLOWLIST", raising=False)
        monkeypatch.setenv("LABCLAW_PLUGIN_ALLOW_ALL", "0")
        assert PluginLoader._plugin_allowed("test-plugin") is False

        monkeypatch.setenv("LABCLAW_PLUGIN_ALLOW_ALL", "1")
        assert PluginLoader._plugin_allowed("test-plugin") is True

    def test_discover_local_missing_path_returns_empty(self, tmp_path: Path) -> None:
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        found = loader.discover_local(tmp_path / "does-not-exist")
        assert found == []

    def test_discover_local_skips_allowlist_miss(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text(
            "from labclaw.plugins.base import PluginMetadata\n"
            "class MyPlugin:\n"
            "    metadata = PluginMetadata(name='my-local', version='1.0', "
            "description='test', plugin_type='device')\n"
            "    def register_devices(self): return []\n"
            "    def get_driver(self, dt): return None\n"
            "def create_plugin(): return MyPlugin()\n"
        )
        monkeypatch.setenv("LABCLAW_PLUGIN_ALLOWLIST", "different_plugin")
        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        found = loader.discover_local(tmp_path)
        assert found == []

    def test_discover_local_insecure_dir_world_writable(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        os.chmod(plugin_dir, 0o777)
        (plugin_dir / "__init__.py").write_text("def create_plugin(): return None\n")

        reg = PluginRegistry()
        loader = PluginLoader(registry=reg)
        found = loader.discover_local(tmp_path)
        assert found == []

    def test_is_secure_plugin_dir_handles_uid_error(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        with patch("labclaw.plugins.loader.os.getuid", side_effect=OSError("uid error")):
            assert PluginLoader._is_secure_plugin_dir(plugin_dir) is False

    def test_is_secure_plugin_dir_handles_stat_error(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        with patch.object(Path, "stat", side_effect=OSError("stat error")):
            assert PluginLoader._is_secure_plugin_dir(plugin_dir) is False

    def test_is_secure_plugin_dir_rejects_symlink(self, tmp_path: Path) -> None:
        real_dir = tmp_path / "real_plugin"
        real_dir.mkdir()
        symlink_dir = tmp_path / "symlink_plugin"
        symlink_dir.symlink_to(real_dir, target_is_directory=True)
        assert PluginLoader._is_secure_plugin_dir(symlink_dir) is False


# ---------------------------------------------------------------------------
# scaffold_plugin
# ---------------------------------------------------------------------------


class TestScaffoldPlugin:
    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        project_dir = scaffold_plugin("labclaw_neuro", "device", tmp_path)
        assert project_dir.exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "src" / "labclaw_neuro" / "__init__.py").exists()
        assert (project_dir / "tests" / "__init__.py").exists()
        assert (project_dir / "README.md").exists()

    def test_pyproject_contains_entry_point(self, tmp_path: Path) -> None:
        project_dir = scaffold_plugin("labclaw_neuro", "device", tmp_path)
        content = (project_dir / "pyproject.toml").read_text()
        assert "labclaw.plugins" in content
        assert "labclaw_neuro" in content

    def test_init_has_create_plugin(self, tmp_path: Path) -> None:
        project_dir = scaffold_plugin("labclaw_neuro", "domain", tmp_path)
        content = (project_dir / "src" / "labclaw_neuro" / "__init__.py").read_text()
        assert "def create_plugin" in content

    def test_analysis_scaffold(self, tmp_path: Path) -> None:
        project_dir = scaffold_plugin("labclaw_stats", "analysis", tmp_path)
        content = (project_dir / "src" / "labclaw_stats" / "__init__.py").read_text()
        assert "get_mining_algorithms" in content
        assert "get_validators" in content

    def test_invalid_type_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="plugin_type must be"):
            scaffold_plugin("foo", "invalid", tmp_path)

    def test_device_scaffold_methods(self, tmp_path: Path) -> None:
        project_dir = scaffold_plugin("labclaw_hw", "device", tmp_path)
        content = (project_dir / "src" / "labclaw_hw" / "__init__.py").read_text()
        assert "register_devices" in content
        assert "get_driver" in content

    def test_domain_scaffold_methods(self, tmp_path: Path) -> None:
        project_dir = scaffold_plugin("labclaw_bio", "domain", tmp_path)
        content = (project_dir / "src" / "labclaw_bio" / "__init__.py").read_text()
        assert "get_sample_node_types" in content
        assert "get_sentinel_rules" in content
        assert "get_hypothesis_templates" in content


# ---------------------------------------------------------------------------
# Protocol checks
# ---------------------------------------------------------------------------


class TestProtocols:
    def test_device_plugin_protocol(self) -> None:
        assert isinstance(StubDevicePlugin(), DevicePlugin)

    def test_domain_plugin_protocol(self) -> None:
        assert isinstance(StubDomainPlugin(), DomainPlugin)

    def test_analysis_plugin_protocol(self) -> None:
        assert isinstance(StubAnalysisPlugin(), AnalysisPlugin)
