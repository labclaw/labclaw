"""Unit tests for labclaw.recovery — crash state save/load/clear."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from labclaw.recovery import StateRecovery

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_recovery(tmp_path: Path, state_file: Path | None = None) -> StateRecovery:
    return StateRecovery(memory_root=tmp_path, state_file=state_file)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStateRecoveryInit:
    def test_default_state_file_path(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        assert sr.state_file == tmp_path / ".labclaw_state.json"

    def test_custom_state_file_path(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_state.json"
        sr = make_recovery(tmp_path, state_file=custom)
        assert sr.state_file == custom


class TestSaveState:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.save_state({"cycle_count": 5})
        assert sr.state_file.exists()

    def test_save_content_is_valid_json(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.save_state({"cycle_count": 3, "version": "0.0.9"})
        data = json.loads(sr.state_file.read_text())
        assert data["cycle_count"] == 3
        assert data["version"] == "0.0.9"

    def test_save_is_atomic_no_tmp_leftover(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.save_state({"x": 1})
        tmp_file = sr.state_file.with_suffix(".tmp")
        assert not tmp_file.exists()

    def test_save_overwrites_previous_state(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.save_state({"cycle_count": 1})
        sr.save_state({"cycle_count": 9})
        data = json.loads(sr.state_file.read_text())
        assert data["cycle_count"] == 9

    def test_save_with_non_serialisable_value_uses_str_default(self, tmp_path: Path) -> None:
        from datetime import datetime

        sr = make_recovery(tmp_path)
        now = datetime(2026, 2, 25, 12, 0, 0)
        sr.save_state({"ts": now})
        data = json.loads(sr.state_file.read_text())
        assert "2026-02-25" in data["ts"]

    def test_save_creates_parent_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "state.json"
        sr = make_recovery(tmp_path, state_file=nested)
        sr.save_state({"ok": True})
        assert nested.exists()


class TestLoadState:
    def test_load_returns_none_when_no_file(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        assert sr.load_state() is None

    def test_load_returns_saved_state(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.save_state({"cycle_count": 5})
        result = sr.load_state()
        assert result is not None
        assert result["cycle_count"] == 5

    def test_load_corrupt_json_returns_none(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.state_file.write_text("NOT VALID JSON {{{{")
        assert sr.load_state() is None

    def test_load_empty_file_returns_none(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.state_file.write_text("")
        assert sr.load_state() is None

    def test_load_after_multiple_saves_returns_latest(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        for i in range(5):
            sr.save_state({"cycle_count": i})
        result = sr.load_state()
        assert result is not None
        assert result["cycle_count"] == 4


class TestClearState:
    def test_clear_removes_file(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.save_state({"x": 1})
        sr.clear_state()
        assert not sr.state_file.exists()

    def test_clear_is_idempotent_when_no_file(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        # Should not raise even when file does not exist.
        sr.clear_state()
        sr.clear_state()

    def test_load_after_clear_returns_none(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        sr.save_state({"data": "important"})
        sr.clear_state()
        assert sr.load_state() is None


class TestRoundTrip:
    def test_full_round_trip(self, tmp_path: Path) -> None:
        sr = make_recovery(tmp_path)
        original = {"cycle_count": 42, "discovery_count": 7, "version": "0.0.9"}
        sr.save_state(original)
        recovered = sr.load_state()
        assert recovered == original

    def test_oserror_on_read_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sr = make_recovery(tmp_path)
        sr.save_state({"ok": 1})

        original_read_text = Path.read_text

        def _raise(self, *args, **kwargs):  # noqa: ANN001
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "read_text", _raise)
        assert sr.load_state() is None
        monkeypatch.setattr(Path, "read_text", original_read_text)
