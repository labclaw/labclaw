"""Unit tests — NWB/JSON export.

Tests both the JSON fallback path (always available) and the pynwb path
(mocked so the test suite never requires pynwb to be installed).
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from labclaw.export.nwb import NWBExporter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_data(session_id: str = "sess-001") -> dict:
    return {
        "session_id": session_id,
        "description": "Test session",
        "findings": ["Finding A", "Finding B"],
        "provenance_steps": [
            {
                "step": "observe",
                "node_id": "n-1",
                "node_type": "observation",
                "inputs": [],
                "outputs": ["20 rows"],
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        ],
        "finding_chains": [],
        "metadata": {"foo": "bar"},
    }


# ---------------------------------------------------------------------------
# JSON stub export (pynwb not installed)
# ---------------------------------------------------------------------------


def test_export_json_stub_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "export.json"
    exporter = NWBExporter()
    result = exporter._export_json_stub(_session_data(), out)
    assert result.exists()
    assert result == out


def test_export_json_stub_content(tmp_path: Path) -> None:
    out = tmp_path / "export.json"
    exporter = NWBExporter()
    exporter._export_json_stub(_session_data("sess-42"), out)
    payload = json.loads(out.read_text())
    assert payload["session_id"] == "sess-42"
    assert payload["format"] == "labclaw-json-stub"
    assert payload["version"] == "1.0"
    assert "findings" in payload
    assert "provenance_steps" in payload
    assert "finding_chains" in payload
    assert "exported_at" in payload


def test_export_json_stub_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "dir" / "export.json"
    exporter = NWBExporter()
    result = exporter._export_json_stub(_session_data(), out)
    assert result.exists()


def test_export_session_uses_json_fallback_when_no_pynwb(tmp_path: Path) -> None:
    """export_session falls back to JSON when pynwb import fails."""
    out = tmp_path / "export.json"
    exporter = NWBExporter()
    with patch.dict(sys.modules, {"pynwb": None}):
        result = exporter.export_session(_session_data(), out)
    assert result.exists()
    payload = json.loads(result.read_text())
    assert payload["format"] == "labclaw-json-stub"


def test_export_json_stub_empty_session_data(tmp_path: Path) -> None:
    out = tmp_path / "empty.json"
    exporter = NWBExporter()
    result = exporter._export_json_stub({}, out)
    payload = json.loads(result.read_text())
    assert payload["findings"] == []
    assert payload["provenance_steps"] == []


# ---------------------------------------------------------------------------
# pynwb path (mocked)
# ---------------------------------------------------------------------------


def _build_pynwb_mock() -> types.ModuleType:
    """Build a minimal pynwb mock sufficient for _export_nwb."""
    pynwb_mod = types.ModuleType("pynwb")

    # NWBFile mock
    nwb_file_instance = MagicMock()
    nwb_file_cls = MagicMock(return_value=nwb_file_instance)
    pynwb_mod.NWBFile = nwb_file_cls  # type: ignore[attr-defined]

    # NWBHDF5IO context manager mock
    io_instance = MagicMock()
    io_cm = MagicMock(
        __enter__=MagicMock(return_value=io_instance),
        __exit__=MagicMock(return_value=False),
    )
    pynwb_mod.NWBHDF5IO = MagicMock(return_value=io_cm)  # type: ignore[attr-defined]

    # ScratchData mock
    scratch_cls = MagicMock(return_value=MagicMock())
    pynwb_mod.core = types.ModuleType("pynwb.core")
    pynwb_mod.core.ScratchData = scratch_cls  # type: ignore[attr-defined]

    # LabMetaData mock
    pynwb_mod.file = types.ModuleType("pynwb.file")
    pynwb_mod.file.LabMetaData = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]

    return pynwb_mod


def test_export_nwb_calls_pynwb(tmp_path: Path) -> None:
    """When pynwb is available, _export_nwb is called."""
    out = tmp_path / "out.nwb"
    pynwb_mock = _build_pynwb_mock()

    modules = {
        "pynwb": pynwb_mock,
        "pynwb.core": pynwb_mock.core,
        "pynwb.file": pynwb_mock.file,
    }
    from datetime import UTC, datetime

    dateutil_mod = types.ModuleType("dateutil")
    dateutil_parser = types.ModuleType("dateutil.parser")
    dateutil_parser.parse = MagicMock(return_value=datetime.now(UTC))  # type: ignore[attr-defined]
    dt_mods = {"dateutil": dateutil_mod, "dateutil.parser": dateutil_parser}
    with patch.dict(sys.modules, modules):
        with patch.dict(sys.modules, dt_mods):
            exporter = NWBExporter()
            result = exporter._export_nwb(_session_data(), out)

    assert result == out.resolve()
    assert pynwb_mock.NWBFile.called


def test_export_session_uses_nwb_when_pynwb_available(tmp_path: Path) -> None:
    """export_session dispatches to _export_nwb when pynwb can be imported."""
    out = tmp_path / "out.nwb"
    pynwb_mock = _build_pynwb_mock()

    modules = {
        "pynwb": pynwb_mock,
        "pynwb.core": pynwb_mock.core,
        "pynwb.file": pynwb_mock.file,
    }
    from datetime import UTC, datetime

    dateutil_mod = types.ModuleType("dateutil")
    dateutil_parser = types.ModuleType("dateutil.parser")
    dateutil_parser.parse = MagicMock(return_value=datetime.now(UTC))  # type: ignore[attr-defined]
    dt_mods = {"dateutil": dateutil_mod, "dateutil.parser": dateutil_parser}
    with patch.dict(sys.modules, modules):
        with patch.dict(sys.modules, dt_mods):
            exporter = NWBExporter()
            result = exporter.export_session(_session_data(), out)

    assert result == out.resolve()


def test_export_nwb_bad_session_start_time(tmp_path: Path) -> None:
    """If session_start_time cannot be parsed, fallback to now()."""
    out = tmp_path / "out.nwb"
    pynwb_mock = _build_pynwb_mock()

    data = _session_data()
    data["session_start_time"] = "not-a-valid-date"

    modules = {
        "pynwb": pynwb_mock,
        "pynwb.core": pynwb_mock.core,
        "pynwb.file": pynwb_mock.file,
    }
    dateutil_mod = types.ModuleType("dateutil")
    dateutil_parser = types.ModuleType("dateutil.parser")
    dateutil_parser.parse = MagicMock(side_effect=ValueError("bad date"))  # type: ignore[attr-defined]
    dt_mods = {"dateutil": dateutil_mod, "dateutil.parser": dateutil_parser}
    with patch.dict(sys.modules, modules):
        with patch.dict(sys.modules, dt_mods):
            exporter = NWBExporter()
            result = exporter._export_nwb(data, out)

    assert result == out.resolve()
