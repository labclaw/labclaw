"""BDD step definitions for L2 Configuration.

Spec: src/labclaw/config.py
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pytest_bdd import given, parsers, then, when

from labclaw.config import LabClawConfig, load_config

# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse("a custom config file with api port {port:d}"),
    target_fixture="custom_config_path",
)
def custom_config_file(tmp_path: Path, port: int) -> Path:
    config_data = {"api": {"host": "0.0.0.0", "port": port}}
    config_file = tmp_path / "custom.yaml"
    config_file.write_text(yaml.dump(config_data))
    return config_file


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I load the default configuration", target_fixture="loaded_config")
def load_default_config() -> LabClawConfig:
    return load_config()


@when("I load the custom configuration", target_fixture="loaded_config")
def load_custom_config(custom_config_path: Path) -> LabClawConfig:
    return load_config(custom_config_path)


@when("I load config from a nonexistent path", target_fixture="loaded_config")
def load_nonexistent_config(tmp_path: Path) -> LabClawConfig:
    nonexistent = tmp_path / "does_not_exist.yaml"
    return load_config(nonexistent)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("the config has a system section")
def check_system_section(loaded_config: LabClawConfig) -> None:
    assert loaded_config.system is not None
    assert loaded_config.system.name


@then("the config has an api section")
def check_api_section(loaded_config: LabClawConfig) -> None:
    assert loaded_config.api is not None
    assert loaded_config.api.port > 0


@then("the config has an events section")
def check_events_section(loaded_config: LabClawConfig) -> None:
    assert loaded_config.events is not None
    assert loaded_config.events.backend


@then("the config has a graph section")
def check_graph_section(loaded_config: LabClawConfig) -> None:
    assert loaded_config.graph is not None
    assert loaded_config.graph.backend


@then("the config has an edge section")
def check_edge_section(loaded_config: LabClawConfig) -> None:
    assert loaded_config.edge is not None


@then("the config has an llm section")
def check_llm_section(loaded_config: LabClawConfig) -> None:
    assert loaded_config.llm is not None


@then(parsers.parse("the api port is {port:d}"))
def check_api_port(loaded_config: LabClawConfig, port: int) -> None:
    assert loaded_config.api.port == port, f"Expected api.port={port}, got {loaded_config.api.port}"


@then(parsers.parse('the graph backend is "{backend}"'))
def check_graph_backend(loaded_config: LabClawConfig, backend: str) -> None:
    assert loaded_config.graph.backend == backend, (
        f"Expected graph.backend={backend!r}, got {loaded_config.graph.backend!r}"
    )


@then(parsers.parse('the events backend is "{backend}"'))
def check_events_backend(loaded_config: LabClawConfig, backend: str) -> None:
    assert loaded_config.events.backend == backend, (
        f"Expected events.backend={backend!r}, got {loaded_config.events.backend!r}"
    )


@then(parsers.parse('the system name is "{name}"'))
def check_system_name(loaded_config: LabClawConfig, name: str) -> None:
    assert loaded_config.system.name == name, (
        f"Expected system.name={name!r}, got {loaded_config.system.name!r}"
    )


@then(parsers.parse('the llm provider is "{provider}"'))
def check_llm_provider(loaded_config: LabClawConfig, provider: str) -> None:
    # llm may be a Pydantic model or a raw dict depending on import order
    llm = loaded_config.llm
    actual = llm.get("provider") if isinstance(llm, dict) else getattr(llm, "provider", None)
    assert actual == provider, f"Expected llm.provider={provider!r}, got {actual!r}"


@then("the edge watch_paths is a list")
def check_edge_watch_paths(loaded_config: LabClawConfig) -> None:
    assert isinstance(loaded_config.edge.watch_paths, list)
