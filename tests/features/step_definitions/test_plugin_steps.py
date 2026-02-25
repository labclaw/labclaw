"""BDD step definitions for L2 Plugin System.

Spec: docs/specs/cross-foundations.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.plugins.base import PluginMetadata
from labclaw.plugins.registry import PluginRegistry
from labclaw.plugins.scaffold import scaffold_plugin

# ---------------------------------------------------------------------------
# Concrete plugin implementations for testing
# ---------------------------------------------------------------------------


class NeuroscienceDomainPlugin:
    """Concrete domain plugin for test scenarios."""

    metadata = PluginMetadata(
        name="neuro-domain",
        version="0.1.0",
        description="Neuroscience domain plugin",
        author="Test",
        plugin_type="domain",
    )

    def get_sample_node_types(self) -> dict[str, type]:
        return {"neuron": dict, "synapse": dict}

    def get_sentinel_rules(self) -> list[dict[str, Any]]:
        return [{"name": "spike_threshold", "check": "warn_if"}]

    def get_hypothesis_templates(self) -> list[dict[str, Any]]:
        return [{"template": "Neural activity in {region} correlates with {behavior}"}]


class CameraDevicePlugin:
    """Concrete device plugin for test scenarios."""

    metadata = PluginMetadata(
        name="camera-device",
        version="0.2.0",
        description="Camera hardware plugin",
        author="Test",
        plugin_type="device",
    )

    def register_devices(self) -> list[dict[str, Any]]:
        return [{"type": "usb_camera", "driver": "v4l2"}]

    def get_driver(self, device_type: str) -> Any:
        return None


class StatsAnalysisPlugin:
    """Concrete analysis plugin for test scenarios."""

    metadata = PluginMetadata(
        name="stats-analysis",
        version="0.1.0",
        description="Statistical analysis plugin",
        author="Test",
        plugin_type="analysis",
    )

    def get_mining_algorithms(self) -> list[dict[str, Any]]:
        return [{"name": "pearson_correlation"}]

    def get_validators(self) -> list[dict[str, Any]]:
        return [{"name": "anova"}]


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    "a domain plugin with neuroscience metadata",
    target_fixture="domain_plugin",
)
def domain_plugin_with_neuro_metadata() -> NeuroscienceDomainPlugin:
    return NeuroscienceDomainPlugin()


@given(
    "a device plugin with camera metadata",
    target_fixture="device_plugin",
)
def device_plugin_with_camera_metadata() -> CameraDevicePlugin:
    return CameraDevicePlugin()


@given(
    "an analysis plugin with stats metadata",
    target_fixture="analysis_plugin",
)
def analysis_plugin_with_stats_metadata() -> StatsAnalysisPlugin:
    return StatsAnalysisPlugin()


@given(
    "a target directory for the new plugin",
    target_fixture="scaffold_dir",
)
def target_directory(tmp_path: Path) -> Path:
    return tmp_path


@given(
    "an empty plugin registry",
    target_fixture="plugin_registry",
)
def empty_plugin_registry() -> PluginRegistry:
    return PluginRegistry()


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    "the plugin is registered in the registry",
    target_fixture="plugin_registry",
)
def register_plugin(domain_plugin: NeuroscienceDomainPlugin) -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(domain_plugin)
    return registry


@when(
    "the device plugin is registered in the registry",
    target_fixture="plugin_registry",
)
def register_device_plugin(device_plugin: CameraDevicePlugin) -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(device_plugin)
    return registry


@when(
    "the analysis plugin is registered in the registry",
    target_fixture="plugin_registry",
)
def register_analysis_plugin(analysis_plugin: StatsAnalysisPlugin) -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(analysis_plugin)
    return registry


@when(
    "both plugins are registered in the same registry",
    target_fixture="plugin_registry",
)
def register_both_plugins(
    domain_plugin: NeuroscienceDomainPlugin,
    device_plugin: CameraDevicePlugin,
) -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(domain_plugin)
    registry.register(device_plugin)
    return registry


@when(
    parsers.parse('I scaffold a plugin named "{name}" of type "{plugin_type}"'),
    target_fixture="scaffolded_path",
)
def scaffold_new_plugin(scaffold_dir: Path, name: str, plugin_type: str) -> Path:
    return scaffold_plugin(name, plugin_type, scaffold_dir)


@when(
    parsers.parse('I try to get plugin "{name}"'),
    target_fixture="plugin_get_error",
)
def try_get_plugin(plugin_registry: PluginRegistry, name: str) -> Exception | None:
    try:
        plugin_registry.get(name)
        return None
    except KeyError as exc:
        return exc


@when(
    "I try to register the same plugin again",
    target_fixture="plugin_dup_error",
)
def try_register_duplicate(
    plugin_registry: PluginRegistry,
    domain_plugin: NeuroscienceDomainPlugin,
) -> Exception | None:
    try:
        plugin_registry.register(domain_plugin)
        return None
    except ValueError as exc:
        return exc


@when(
    parsers.parse('I try to scaffold a plugin named "{name}" of type "{plugin_type}"'),
    target_fixture="scaffold_error",
)
def try_scaffold_invalid_type(scaffold_dir: Path, name: str, plugin_type: str) -> Exception | None:
    try:
        scaffold_plugin(name, plugin_type, scaffold_dir)
        return None
    except ValueError as exc:
        return exc


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("it should appear in the plugin list")
def check_plugin_in_list(plugin_registry: PluginRegistry) -> None:
    plugins = plugin_registry.list_plugins()
    names = [p.name for p in plugins]
    assert len(names) > 0, "Plugin list is empty"


@then(parsers.parse('it should be retrievable by type "{plugin_type}"'))
def check_retrievable_by_type(
    plugin_registry: PluginRegistry, plugin_type: str,
) -> None:
    plugins = plugin_registry.get_by_type(plugin_type)
    assert len(plugins) >= 1, f"Expected >= 1 {plugin_type} plugin, got {len(plugins)}"


@then(parsers.parse('I can retrieve it by name "{name}"'))
def check_retrieve_by_name(plugin_registry: PluginRegistry, name: str) -> None:
    plugin = plugin_registry.get(name)
    assert plugin.metadata.name == name


@then("a plugin KeyError is raised")
def check_plugin_key_error(plugin_get_error: Exception | None) -> None:
    assert plugin_get_error is not None, "Expected KeyError but no exception raised"
    assert isinstance(plugin_get_error, KeyError), (
        f"Expected KeyError, got {type(plugin_get_error).__name__}"
    )


@then("a plugin ValueError is raised")
def check_plugin_value_error(plugin_dup_error: Exception | None) -> None:
    assert plugin_dup_error is not None, "Expected ValueError but no exception raised"
    assert isinstance(plugin_dup_error, ValueError), (
        f"Expected ValueError, got {type(plugin_dup_error).__name__}"
    )


@then(parsers.parse("listing by type \"{plugin_type}\" returns {count:d} plugin"))
def check_list_by_type_singular(
    plugin_registry: PluginRegistry, plugin_type: str, count: int
) -> None:
    plugins = plugin_registry.get_by_type(plugin_type)
    assert len(plugins) == count, f"Expected {count} {plugin_type} plugins, got {len(plugins)}"


@then(parsers.parse("listing by type \"{plugin_type}\" returns {count:d} plugins"))
def check_list_by_type(
    plugin_registry: PluginRegistry, plugin_type: str, count: int
) -> None:
    plugins = plugin_registry.get_by_type(plugin_type)
    assert len(plugins) == count, f"Expected {count} {plugin_type} plugins, got {len(plugins)}"


@then(parsers.parse('the plugin metadata has name "{name}"'))
def check_metadata_name(domain_plugin: NeuroscienceDomainPlugin, name: str) -> None:
    assert domain_plugin.metadata.name == name


@then(parsers.parse('the plugin metadata has version "{version}"'))
def check_metadata_version(domain_plugin: NeuroscienceDomainPlugin, version: str) -> None:
    assert domain_plugin.metadata.version == version


@then("the plugin metadata has a description")
def check_metadata_description(domain_plugin: NeuroscienceDomainPlugin) -> None:
    assert domain_plugin.metadata.description
    assert len(domain_plugin.metadata.description) > 0


@then(parsers.parse('the plugin metadata has plugin_type "{plugin_type}"'))
def check_metadata_plugin_type(domain_plugin: NeuroscienceDomainPlugin, plugin_type: str) -> None:
    assert domain_plugin.metadata.plugin_type == plugin_type


@then("the directory structure should include pyproject.toml and __init__.py")
def check_directory_structure(scaffolded_path: Path) -> None:
    assert (scaffolded_path / "pyproject.toml").exists(), "Missing pyproject.toml"
    # __init__.py is under src/<name>/
    init_files = list(scaffolded_path.rglob("__init__.py"))
    assert len(init_files) >= 1, "Missing __init__.py"


@then("the __init__.py should contain a create_plugin factory")
def check_create_plugin_factory(scaffolded_path: Path) -> None:
    init_files = list(scaffolded_path.rglob("__init__.py"))
    # Find the one under src/ (not tests/)
    src_init = [f for f in init_files if "src" in str(f)]
    assert src_init, f"No __init__.py found under src/: {init_files}"
    content = src_init[0].read_text()
    assert "def create_plugin" in content, (
        f"Expected 'def create_plugin' in __init__.py, got:\n{content[:200]}"
    )


@then(parsers.parse('the scaffolded plugin type is "{plugin_type}"'))
def check_scaffolded_plugin_type(scaffolded_path: Path, plugin_type: str) -> None:
    pyproject = (scaffolded_path / "pyproject.toml").read_text()
    assert plugin_type in pyproject, (
        f"Expected plugin type {plugin_type!r} in pyproject.toml"
    )


@then("a scaffold ValueError is raised")
def check_scaffold_value_error(scaffold_error: Exception | None) -> None:
    assert scaffold_error is not None, "Expected ValueError but no exception raised"
    assert isinstance(scaffold_error, ValueError), (
        f"Expected ValueError, got {type(scaffold_error).__name__}"
    )


@then("the plugin list is empty")
def check_plugin_list_empty(plugin_registry: PluginRegistry) -> None:
    plugins = plugin_registry.list_plugins()
    assert len(plugins) == 0, f"Expected empty list, got {[p.name for p in plugins]}"
