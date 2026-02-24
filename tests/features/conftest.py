"""Shared BDD fixtures for all feature tests.

Provides common test infrastructure: temp directories, event capture,
and reusable fixtures that all layer tests depend on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from labclaw.core.events import EventRegistry, event_registry
from labclaw.core.schemas import LabEvent


@pytest.fixture()
def tmp_lab(tmp_path: Path) -> Path:
    """Create a temporary lab directory structure."""
    lab = tmp_path / "lab"
    lab.mkdir()
    (lab / "protocols").mkdir()
    (lab / "decisions").mkdir()
    (lab / "failures").mkdir()
    (lab / "stream").mkdir()
    return lab


@pytest.fixture()
def tmp_members(tmp_path: Path) -> Path:
    """Create a temporary members directory."""
    members = tmp_path / "members"
    members.mkdir()
    return members


@pytest.fixture()
def tmp_devices(tmp_path: Path) -> Path:
    """Create a temporary devices directory."""
    devices = tmp_path / "devices"
    devices.mkdir()
    return devices


@pytest.fixture()
def fresh_registry() -> EventRegistry:
    """Provide a clean event registry (does not affect global singleton)."""
    reg = EventRegistry()
    return reg


@pytest.fixture()
def _clean_global_registry() -> None:
    """Reset the global event registry before/after test."""
    event_registry.clear()
    yield  # type: ignore[misc]
    event_registry.clear()


class EventCapture:
    """Captures emitted events for assertion in tests."""

    def __init__(self) -> None:
        self.events: list[LabEvent] = []

    def __call__(self, event: LabEvent) -> None:
        self.events.append(event)

    @property
    def last(self) -> LabEvent:
        assert self.events, "No events captured"
        return self.events[-1]

    @property
    def names(self) -> list[str]:
        return [e.event_name.full for e in self.events]

    def count(self, name: str) -> int:
        return sum(1 for e in self.events if e.event_name.full == name)


@pytest.fixture()
def event_capture() -> EventCapture:
    """Provide an EventCapture instance for subscribing to events."""
    return EventCapture()
