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
# Concrete domain plugin for testing
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
    "a target directory for the new plugin",
    target_fixture="scaffold_dir",
)
def target_directory(tmp_path: Path) -> Path:
    return tmp_path


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
    parsers.parse('I scaffold a plugin named "{name}" of type "{plugin_type}"'),
    target_fixture="scaffolded_path",
)
def scaffold_new_plugin(scaffold_dir: Path, name: str, plugin_type: str) -> Path:
    return scaffold_plugin(name, plugin_type, scaffold_dir)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("it should appear in the plugin list")
def check_plugin_in_list(plugin_registry: PluginRegistry) -> None:
    plugins = plugin_registry.list_plugins()
    names = [p.name for p in plugins]
    assert "neuro-domain" in names, f"Expected 'neuro-domain' in {names}"


@then(parsers.parse('it should be retrievable by type "{plugin_type}"'))
def check_retrievable_by_type(
    plugin_registry: PluginRegistry, plugin_type: str,
) -> None:
    plugins = plugin_registry.get_by_type(plugin_type)
    assert len(plugins) >= 1, f"Expected >= 1 {plugin_type} plugin, got {len(plugins)}"


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
