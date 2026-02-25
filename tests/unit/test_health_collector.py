"""Unit tests for labclaw.api.health_collector — HealthCollector class."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from labclaw.api.health_collector import (
    HealthCollector,
    get_health_collector,
    reset_health_collector,
)


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    reset_health_collector()
    yield
    reset_health_collector()


class TestHealthCollectorInit:
    def test_default_api_component_is_up(self) -> None:
        hc = HealthCollector()
        assert hc.get_components()["api"] == "up"

    def test_default_daemon_components_are_unknown(self) -> None:
        hc = HealthCollector()
        comps = hc.get_components()
        for name in ("watcher", "discovery", "evolution", "memory"):
            assert comps[name] == "unknown", f"{name} should be 'unknown'"

    def test_cycle_count_starts_at_zero(self) -> None:
        hc = HealthCollector()
        assert hc.cycle_count() == 0

    def test_last_cycle_at_starts_none(self) -> None:
        hc = HealthCollector()
        assert hc.last_cycle_at() is None

    def test_uptime_is_non_negative(self) -> None:
        hc = HealthCollector()
        assert hc.uptime_seconds() >= 0


class TestSetComponentStatus:
    def test_set_known_component(self) -> None:
        hc = HealthCollector()
        hc.set_component_status("watcher", "up")
        assert hc.get_components()["watcher"] == "up"

    def test_set_unknown_component_name(self) -> None:
        hc = HealthCollector()
        hc.set_component_status("my_plugin", "up")
        assert hc.get_components()["my_plugin"] == "up"

    def test_set_component_down(self) -> None:
        hc = HealthCollector()
        hc.set_component_status("evolution", "down")
        assert hc.get_components()["evolution"] == "down"

    def test_get_components_returns_snapshot_not_reference(self) -> None:
        hc = HealthCollector()
        snap = hc.get_components()
        snap["api"] = "down"
        assert hc.get_components()["api"] == "up"


class TestRecordCycle:
    def test_record_cycle_increments_counter(self) -> None:
        hc = HealthCollector()
        hc.record_cycle()
        assert hc.cycle_count() == 1

    def test_record_cycle_multiple_times(self) -> None:
        hc = HealthCollector()
        for _ in range(5):
            hc.record_cycle()
        assert hc.cycle_count() == 5

    def test_record_cycle_sets_last_cycle_at(self) -> None:
        hc = HealthCollector()
        before = datetime.now(UTC)
        hc.record_cycle()
        after = datetime.now(UTC)
        ts = hc.last_cycle_at()
        assert ts is not None
        assert before <= ts <= after


class TestSnapshot:
    def test_snapshot_contains_required_keys(self) -> None:
        hc = HealthCollector()
        snap = hc.snapshot()
        required = (
            "components",
            "uptime_seconds",
            "last_cycle_at",
            "cycle_count",
            "memory_usage_mb",
        )
        for key in required:
            assert key in snap, f"Key {key!r} missing from snapshot"

    def test_snapshot_last_cycle_at_is_none_initially(self) -> None:
        hc = HealthCollector()
        assert hc.snapshot()["last_cycle_at"] is None

    def test_snapshot_last_cycle_at_is_iso_string_after_cycle(self) -> None:
        hc = HealthCollector()
        hc.record_cycle()
        snap = hc.snapshot()
        assert snap["last_cycle_at"] is not None
        # Should parse as ISO 8601
        datetime.fromisoformat(snap["last_cycle_at"])

    def test_snapshot_cycle_count(self) -> None:
        hc = HealthCollector()
        hc.record_cycle()
        hc.record_cycle()
        assert hc.snapshot()["cycle_count"] == 2

    def test_snapshot_uptime_non_negative(self) -> None:
        hc = HealthCollector()
        assert hc.snapshot()["uptime_seconds"] >= 0

    def test_snapshot_memory_usage_non_negative(self) -> None:
        hc = HealthCollector()
        assert hc.snapshot()["memory_usage_mb"] >= 0

    def test_snapshot_memory_usage_exception_handled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If resource module raises, memory_usage_mb should be 0.0."""
        import resource as resource_module

        def _mock_resource_getrusage(*args, **kwargs):
            raise OSError("resource unavailable")

        monkeypatch.setattr(resource_module, "getrusage", _mock_resource_getrusage)
        hc = HealthCollector()
        snap = hc.snapshot()
        assert snap["memory_usage_mb"] == 0.0

    def test_snapshot_memory_usage_non_linux_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover the macOS branch (bytes / 1024^2) for non-Linux uname."""
        import os

        class _FakeUname:
            sysname = "Darwin"

        monkeypatch.setattr(os, "uname", lambda: _FakeUname())
        hc = HealthCollector()
        snap = hc.snapshot()
        assert snap["memory_usage_mb"] >= 0


class TestSingleton:
    def test_get_health_collector_returns_same_instance(self) -> None:
        a = get_health_collector()
        b = get_health_collector()
        assert a is b

    def test_reset_health_collector_creates_fresh_instance(self) -> None:
        a = get_health_collector()
        a.record_cycle()
        reset_health_collector()
        b = get_health_collector()
        assert b.cycle_count() == 0
        assert a is not b
