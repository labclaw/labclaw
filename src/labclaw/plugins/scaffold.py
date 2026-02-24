"""Plugin scaffolding — create new plugin projects from template.

Used by ``labclaw plugin create <name>``.
"""

from __future__ import annotations

from pathlib import Path


def scaffold_plugin(name: str, plugin_type: str, output_dir: Path) -> Path:
    """Create a new plugin project from template.

    Creates: pyproject.toml, src/<name>/__init__.py, tests/, README.md

    Args:
        name: Plugin package name (e.g. ``labclaw_neuro``).
        plugin_type: One of ``device``, ``domain``, ``analysis``.
        output_dir: Directory in which to create the project folder.

    Returns:
        Path to the created project directory.
    """
    if plugin_type not in ("device", "domain", "analysis"):
        raise ValueError(f"plugin_type must be device/domain/analysis, got {plugin_type!r}")

    project_dir = output_dir / name
    src_dir = project_dir / "src" / name
    tests_dir = project_dir / "tests"

    for d in (src_dir, tests_dir):
        d.mkdir(parents=True, exist_ok=True)

    _write_pyproject(project_dir, name, plugin_type)
    _write_init(src_dir, name, plugin_type)
    _write_readme(project_dir, name, plugin_type)
    (tests_dir / "__init__.py").write_text("")

    return project_dir


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------


def _write_pyproject(project_dir: Path, name: str, plugin_type: str) -> None:
    content = f"""\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "0.1.0"
description = "LabClaw {plugin_type} plugin"
requires-python = ">=3.11"
dependencies = ["labclaw>=0.0.1"]

[project.entry-points."labclaw.plugins"]
{name} = "{name}:create_plugin"

[tool.hatch.build.targets.wheel]
packages = ["src/{name}"]
"""
    (project_dir / "pyproject.toml").write_text(content)


def _write_init(src_dir: Path, name: str, plugin_type: str) -> None:
    class_name = "".join(part.capitalize() for part in name.replace("-", "_").split("_"))
    method_stubs = _method_stubs(plugin_type)
    content = f"""\
\"\"\"LabClaw {plugin_type} plugin: {name}.\"\"\"

from __future__ import annotations

from typing import Any

from labclaw.plugins.base import PluginMetadata


class {class_name}:
    metadata = PluginMetadata(
        name="{name}",
        version="0.1.0",
        description="LabClaw {plugin_type} plugin",
        plugin_type="{plugin_type}",
    )

{method_stubs}


def create_plugin() -> {class_name}:
    return {class_name}()
"""
    (src_dir / "__init__.py").write_text(content)


def _write_readme(project_dir: Path, name: str, plugin_type: str) -> None:
    content = f"""\
# {name}

A LabClaw **{plugin_type}** plugin.

## Install

```bash
pip install -e .
```

After installation LabClaw discovers this plugin automatically via the
`labclaw.plugins` entry point group.
"""
    (project_dir / "README.md").write_text(content)


def _method_stubs(plugin_type: str) -> str:
    if plugin_type == "device":
        return """\
    def register_devices(self) -> list[dict[str, Any]]:
        return []

    def get_driver(self, device_type: str) -> Any:
        raise NotImplementedError(device_type)"""

    if plugin_type == "domain":
        return """\
    def get_sample_node_types(self) -> dict[str, type]:
        return {}

    def get_sentinel_rules(self) -> list[dict[str, Any]]:
        return []

    def get_hypothesis_templates(self) -> list[dict[str, Any]]:
        return []"""

    # analysis
    return """\
    def get_mining_algorithms(self) -> list[dict[str, Any]]:
        return []

    def get_validators(self) -> list[dict[str, Any]]:
        return []"""
