"""HealthCollector — tracks component liveness and daemon runtime statistics."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Literal

ComponentStatus = Literal["up", "down", "unknown"]


class HealthCollector:
    """Thread-safe collector for daemon component status and cycle statistics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._components: dict[str, ComponentStatus] = {
            "api": "up",
            "watcher": "unknown",
            "discovery": "unknown",
            "evolution": "unknown",
            "memory": "unknown",
        }
        self._start_time: float = time.monotonic()
        self._last_cycle_at: datetime | None = None
        self._cycle_count: int = 0

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def set_component_status(self, name: str, status: ComponentStatus) -> None:
        """Update the status of a named component."""
        with self._lock:
            self._components[name] = status

    def record_cycle(self) -> None:
        """Increment cycle counter and record the current timestamp."""
        with self._lock:
            self._cycle_count += 1
            self._last_cycle_at = datetime.now(UTC)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_components(self) -> dict[str, ComponentStatus]:
        """Return a snapshot of all component statuses."""
        with self._lock:
            return dict(self._components)

    def uptime_seconds(self) -> float:
        """Seconds elapsed since this collector was created."""
        return time.monotonic() - self._start_time

    def last_cycle_at(self) -> datetime | None:
        """ISO timestamp of the most recent completed cycle, or None."""
        with self._lock:
            return self._last_cycle_at

    def cycle_count(self) -> int:
        """Total number of cycles completed."""
        with self._lock:
            return self._cycle_count

    def snapshot(self) -> dict:
        """Return a full health snapshot suitable for the /health endpoint."""
        import os

        try:
            import resource

            mem_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # Linux reports kilobytes; macOS reports bytes
            if os.uname().sysname == "Linux":
                memory_mb = mem_bytes / 1024.0
            else:
                memory_mb = mem_bytes / (1024.0 * 1024.0)
        except Exception:
            memory_mb = 0.0

        with self._lock:
            last_at = (
                self._last_cycle_at.isoformat() if self._last_cycle_at is not None else None
            )
            return {
                "components": dict(self._components),
                "uptime_seconds": round(time.monotonic() - self._start_time, 2),
                "last_cycle_at": last_at,
                "cycle_count": self._cycle_count,
                "memory_usage_mb": round(memory_mb, 2),
            }


# Module-level singleton shared by the API and daemon.
_collector: HealthCollector | None = None
_collector_lock = threading.Lock()


def get_health_collector() -> HealthCollector:
    """Return (or create) the process-level HealthCollector singleton."""
    global _collector  # noqa: PLW0603
    with _collector_lock:
        if _collector is None:
            _collector = HealthCollector()
        return _collector


def reset_health_collector() -> None:
    """Reset the singleton (for tests only)."""
    global _collector  # noqa: PLW0603
    with _collector_lock:
        _collector = None
