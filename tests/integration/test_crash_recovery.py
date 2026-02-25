"""Integration tests — simulate crash → restart → verify state is recovered."""

from __future__ import annotations

from pathlib import Path

import pytest

from labclaw.recovery import StateRecovery


@pytest.fixture()
def memory_root(tmp_path: Path) -> Path:
    root = tmp_path / "memory"
    root.mkdir()
    return root


class TestCrashRecoveryIntegration:
    def test_state_saved_and_recovered_after_restart(self, memory_root: Path) -> None:
        """Simulate daemon saving state before crash, then recovering on restart."""
        # --- "First process": daemon runs 5 cycles then crashes ---
        recovery_process_1 = StateRecovery(memory_root)
        daemon_state = {
            "cycle_count": 5,
            "discovery_count": 3,
            "version": "0.0.9",
        }
        recovery_process_1.save_state(daemon_state)

        # --- "Second process": daemon restarts and loads state ---
        recovery_process_2 = StateRecovery(memory_root)
        recovered = recovery_process_2.load_state()

        assert recovered is not None
        assert recovered["cycle_count"] == 5
        assert recovered["discovery_count"] == 3

    def test_corrupt_state_file_handled_gracefully(self, memory_root: Path) -> None:
        """Corrupt state file must NOT prevent daemon from starting."""
        state_file = memory_root / ".labclaw_state.json"
        state_file.write_text("{corrupted: json [[[")

        recovery = StateRecovery(memory_root)
        result = recovery.load_state()

        # Fresh state — no crash, no exception
        assert result is None

    def test_missing_state_file_starts_fresh(self, memory_root: Path) -> None:
        """No state file → daemon starts with clean slate."""
        recovery = StateRecovery(memory_root)
        assert recovery.load_state() is None

    def test_state_cleared_after_clean_shutdown(self, memory_root: Path) -> None:
        """Clean shutdown clears state; next restart sees no leftover state."""
        recovery = StateRecovery(memory_root)
        recovery.save_state({"cycle_count": 10})
        # Clean shutdown clears state file
        recovery.clear_state()

        recovery_restart = StateRecovery(memory_root)
        assert recovery_restart.load_state() is None

    def test_incremental_state_updates(self, memory_root: Path) -> None:
        """State file always reflects the most recent save."""
        recovery = StateRecovery(memory_root)
        for i in range(1, 6):
            recovery.save_state({"cycle_count": i})

        # Latest save wins
        recovered = recovery.load_state()
        assert recovered is not None
        assert recovered["cycle_count"] == 5

    def test_atomic_write_no_partial_state(self, memory_root: Path) -> None:
        """Verify no .tmp leftover after a successful save."""
        recovery = StateRecovery(memory_root)
        recovery.save_state({"cycle_count": 1})

        tmp_file = recovery.state_file.with_suffix(".tmp")
        assert not tmp_file.exists()
        assert recovery.state_file.exists()

    def test_large_state_round_trip(self, memory_root: Path) -> None:
        """Large state dicts are serialised and recovered correctly."""
        recovery = StateRecovery(memory_root)
        large_state = {
            "cycle_count": 100,
            "files_processed": 9999,
            "patterns": [{"id": str(i), "score": i * 0.01} for i in range(500)],
        }
        recovery.save_state(large_state)
        recovered = recovery.load_state()
        assert recovered is not None
        assert recovered["cycle_count"] == 100
        assert len(recovered["patterns"]) == 500

    def test_state_file_path_is_deterministic(self, memory_root: Path) -> None:
        """Two independent StateRecovery objects with same root share the same file."""
        r1 = StateRecovery(memory_root)
        r2 = StateRecovery(memory_root)
        assert r1.state_file == r2.state_file
