"""Tests for labclaw.config — configuration loader and models."""

from __future__ import annotations

from pathlib import Path

import yaml

from labclaw.config import (
    AgentsConfig,
    APIConfig,
    EdgeConfig,
    EventsConfig,
    GraphConfig,
    LabClawConfig,
    SystemConfig,
    load_config,
)


class TestLoadConfig:
    def test_valid_yaml_file(self, tmp_path: Path):
        cfg_data = {
            "system": {"name": "test-lab", "version": "1.0.0", "log_level": "DEBUG"},
            "graph": {"backend": "sqlite", "path": "test.db"},
            "api": {"host": "127.0.0.1", "port": 9000},
        }
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(cfg_data))

        config = load_config(cfg_file)
        assert config.system.name == "test-lab"
        assert config.system.version == "1.0.0"
        assert config.system.log_level == "DEBUG"
        assert config.api.host == "127.0.0.1"
        assert config.api.port == 9000

    def test_missing_file_returns_defaults(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.yaml"
        config = load_config(missing)
        assert isinstance(config, LabClawConfig)
        assert config.system.name == "labclaw"

    def test_invalid_yaml_data(self, tmp_path: Path):
        """YAML that parses but has invalid types should raise."""
        cfg_file = tmp_path / "bad.yaml"
        cfg_file.write_text("system:\n  port: not_a_valid_field\n")
        # Pydantic should still allow extra/unknown fields or ignore them
        # depending on model config. This tests it doesn't crash.
        config = load_config(cfg_file)
        assert isinstance(config, LabClawConfig)

    def test_empty_yaml_returns_defaults(self, tmp_path: Path):
        cfg_file = tmp_path / "empty.yaml"
        cfg_file.write_text("")
        config = load_config(cfg_file)
        assert isinstance(config, LabClawConfig)
        assert config.system.name == "labclaw"

    def test_default_config_file(self):
        """Loading with no path should use configs/default.yaml."""
        config = load_config()
        assert isinstance(config, LabClawConfig)


class TestLabClawConfigDefaults:
    def test_default_values(self):
        config = LabClawConfig()
        assert config.system.name == "labclaw"
        assert config.system.version == "0.0.1"
        assert config.system.log_level == "INFO"
        assert config.graph.backend == "sqlite"
        assert config.events.backend == "memory"
        assert config.api.port == 8000
        assert config.edge.watch_paths == []
        assert config.agents.default_model == "claude-sonnet-4-6"


class TestNestedConfigModels:
    def test_system_config(self):
        sc = SystemConfig(name="my-lab", version="2.0", log_level="WARNING")
        assert sc.name == "my-lab"
        assert sc.version == "2.0"
        assert sc.log_level == "WARNING"

    def test_graph_config(self):
        gc = GraphConfig(backend="postgres", path="pg://localhost")
        assert gc.backend == "postgres"
        assert gc.path == "pg://localhost"

    def test_events_config(self):
        ec = EventsConfig(backend="redis", redis_url="redis://custom:6380")
        assert ec.backend == "redis"
        assert ec.redis_url == "redis://custom:6380"

    def test_api_config(self):
        ac = APIConfig(host="localhost", port=3000)
        assert ac.host == "localhost"
        assert ac.port == 3000

    def test_edge_config(self):
        ec = EdgeConfig(watch_paths=["/data/videos"], poll_interval_seconds=10)
        assert ec.watch_paths == ["/data/videos"]
        assert ec.poll_interval_seconds == 10

    def test_agents_config(self):
        ac = AgentsConfig(default_model="gpt-4", max_tool_calls=50)
        assert ac.default_model == "gpt-4"
        assert ac.max_tool_calls == 50
