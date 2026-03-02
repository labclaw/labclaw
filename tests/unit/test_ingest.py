"""Tests for labclaw.ingest — multi-format data loaders."""

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

from labclaw.ingest import (
    _extract_nwb_spatial_series,
    _load_csv,
    _load_dlc_h5,
    _load_h5,
    _load_nwb,
    _load_sam_h5,
    load_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_real_import = builtins.__import__


def _block_import(*names: str) -> Any:
    """Return a side_effect for patching __import__ that blocks specific modules."""

    def _mock(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in names:
            raise ImportError(f"mocked: no {name}")
        return _real_import(name, *args, **kwargs)

    return _mock


# ---------------------------------------------------------------------------
# load_file dispatch
# ---------------------------------------------------------------------------


def test_load_file_csv(tmp_path: Path) -> None:
    p = tmp_path / "data.csv"
    p.write_text("a,b\n1,2\n3,4\n")
    rows = load_file(p)
    assert len(rows) == 2
    assert rows[0] == {"a": 1.0, "b": 2.0}


def test_load_file_tsv(tmp_path: Path) -> None:
    p = tmp_path / "data.tsv"
    p.write_text("a\tb\n1\t2\n")
    rows = load_file(p)
    assert len(rows) == 1
    assert rows[0] == {"a": 1.0, "b": 2.0}


def test_load_file_txt(tmp_path: Path) -> None:
    p = tmp_path / "data.txt"
    p.write_text("x,y\n5,6\n")
    rows = load_file(p)
    assert len(rows) == 1


def test_load_file_nonexistent(tmp_path: Path) -> None:
    assert load_file(tmp_path / "nope.csv") == []


def test_load_file_unsupported_extension(tmp_path: Path) -> None:
    p = tmp_path / "data.xyz"
    p.write_text("whatever")
    assert load_file(p) == []


def test_load_file_h5_dispatches(tmp_path: Path) -> None:
    h5py = pytest.importorskip("h5py")
    p = tmp_path / "sam.h5"
    positions = np.random.rand(5, 2, 2).astype(np.float32)
    with h5py.File(p, "w") as f:
        f.create_dataset("positions", data=positions)
    rows = load_file(p)
    assert len(rows) == 10  # 5 frames * 2 animals
    assert "x" in rows[0] and "y" in rows[0]


def test_load_file_nwb_extension(tmp_path: Path) -> None:
    p = tmp_path / "test.nwb"
    p.write_text("fake")
    with patch("labclaw.ingest._load_nwb", return_value=[{"a": 1}]) as mock:
        rows = load_file(p)
    mock.assert_called_once_with(p)
    assert rows == [{"a": 1}]


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------


def test_load_csv_basic(tmp_path: Path) -> None:
    p = tmp_path / "basic.csv"
    p.write_text("col_a,col_b,label\n1.5,2.5,mouse\n3,4,rat\n")
    rows = _load_csv(p)
    assert len(rows) == 2
    assert rows[0] == {"col_a": 1.5, "col_b": 2.5, "label": "mouse"}
    assert rows[1] == {"col_a": 3.0, "col_b": 4.0, "label": "rat"}


def test_load_csv_tsv_delimiter(tmp_path: Path) -> None:
    p = tmp_path / "tab.tsv"
    p.write_text("x\ty\n10\t20\n")
    rows = _load_csv(p)
    assert rows == [{"x": 10.0, "y": 20.0}]


def test_load_csv_header_only(tmp_path: Path) -> None:
    p = tmp_path / "empty.csv"
    p.write_text("a,b\n")
    assert _load_csv(p) == []


def test_load_csv_none_key_skipped(tmp_path: Path) -> None:
    """DictReader can produce None keys for extra fields."""
    p = tmp_path / "extra.csv"
    p.write_text("a,b\n1,2,3\n")
    rows = _load_csv(p)
    assert len(rows) == 1
    assert None not in rows[0]


# ---------------------------------------------------------------------------
# SAM-Behavior H5 loader
# ---------------------------------------------------------------------------


class TestSamH5:
    def test_basic_load(self, tmp_path: Path) -> None:
        h5py = pytest.importorskip("h5py")
        p = tmp_path / "sam.h5"
        n_frames, n_animals = 3, 2
        positions = np.arange(n_frames * n_animals * 2, dtype=np.float32).reshape(
            n_frames, n_animals, 2
        )
        timestamps = np.array([0.0, 0.033, 0.066])

        with h5py.File(p, "w") as f:
            f.create_dataset("positions", data=positions)
            f.create_dataset("timestamps", data=timestamps)

        with h5py.File(p, "r") as f:
            rows = _load_sam_h5(p, f)

        assert len(rows) == 6
        assert rows[0]["frame"] == 0
        assert rows[0]["animal_id"] == "animal_0"
        assert rows[0]["time_sec"] == 0.0
        assert rows[0]["x"] == float(positions[0, 0, 0])
        assert rows[0]["y"] == float(positions[0, 0, 1])

    def test_no_timestamps_uses_30fps(self, tmp_path: Path) -> None:
        h5py = pytest.importorskip("h5py")
        p = tmp_path / "sam_no_ts.h5"
        positions = np.zeros((2, 1, 2), dtype=np.float32)

        with h5py.File(p, "w") as f:
            f.create_dataset("positions", data=positions)

        with h5py.File(p, "r") as f:
            rows = _load_sam_h5(p, f)

        assert len(rows) == 2
        assert rows[0]["time_sec"] == pytest.approx(0.0)
        assert rows[1]["time_sec"] == pytest.approx(1 / 30.0)

    def test_bad_shape_returns_empty(self, tmp_path: Path) -> None:
        h5py = pytest.importorskip("h5py")
        p = tmp_path / "bad.h5"
        with h5py.File(p, "w") as f:
            f.create_dataset("positions", data=np.zeros((5, 2)))

        with h5py.File(p, "r") as f:
            rows = _load_sam_h5(p, f)
        assert rows == []

    def test_wrong_last_dim_returns_empty(self, tmp_path: Path) -> None:
        h5py = pytest.importorskip("h5py")
        p = tmp_path / "bad3d.h5"
        with h5py.File(p, "w") as f:
            f.create_dataset("positions", data=np.zeros((5, 2, 3)))

        with h5py.File(p, "r") as f:
            rows = _load_sam_h5(p, f)
        assert rows == []


# ---------------------------------------------------------------------------
# DeepLabCut H5 loader
# ---------------------------------------------------------------------------


class TestDlcH5:
    def test_single_animal(self, tmp_path: Path) -> None:
        pd = pytest.importorskip("pandas")
        pytest.importorskip("tables")
        p = tmp_path / "dlc_single.h5"

        cols = pd.MultiIndex.from_tuples(
            [
                ("scorer", "nose", "x"),
                ("scorer", "nose", "y"),
                ("scorer", "nose", "likelihood"),
                ("scorer", "tail", "x"),
                ("scorer", "tail", "y"),
                ("scorer", "tail", "likelihood"),
            ]
        )
        data = np.random.rand(3, 6)
        df = pd.DataFrame(data, columns=cols)
        df.to_hdf(p, key="df_with_missing", mode="w")

        rows = _load_dlc_h5(p)
        assert len(rows) == 3
        assert rows[0]["animal_id"] == "single"
        assert "nose_x" in rows[0]
        assert "tail_likelihood" in rows[0]

    def test_multi_animal(self, tmp_path: Path) -> None:
        pd = pytest.importorskip("pandas")
        pytest.importorskip("tables")
        p = tmp_path / "dlc_multi.h5"

        cols = pd.MultiIndex.from_tuples(
            [
                ("scorer", "mouse1", "nose", "x"),
                ("scorer", "mouse1", "nose", "y"),
                ("scorer", "mouse1", "nose", "likelihood"),
                ("scorer", "mouse2", "nose", "x"),
                ("scorer", "mouse2", "nose", "y"),
                ("scorer", "mouse2", "nose", "likelihood"),
            ]
        )
        data = np.random.rand(2, 6)
        df = pd.DataFrame(data, columns=cols)
        df.to_hdf(p, key="df_with_missing", mode="w")

        rows = _load_dlc_h5(p)
        assert len(rows) == 4  # 2 frames * 2 animals
        animal_ids = {r["animal_id"] for r in rows}
        assert animal_ids == {"mouse1", "mouse2"}

    def test_missing_pandas_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "dlc.h5"
        p.write_bytes(b"fake")
        with patch("builtins.__import__", side_effect=_block_import("pandas")):
            result = _load_dlc_h5(p)
        assert result == []

    def test_non_multiindex_returns_empty(self, tmp_path: Path) -> None:
        pd = pytest.importorskip("pandas")
        pytest.importorskip("tables")
        p = tmp_path / "flat.h5"
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        df.to_hdf(p, key="df", mode="w")
        assert _load_dlc_h5(p) == []

    def test_corrupt_h5_returns_empty(self, tmp_path: Path) -> None:
        pytest.importorskip("pandas")
        p = tmp_path / "corrupt.h5"
        p.write_bytes(b"not a real h5 file")
        assert _load_dlc_h5(p) == []

    def test_single_animal_missing_coord(self, tmp_path: Path) -> None:
        """KeyError fallback when a coord is missing from the MultiIndex."""
        pd = pytest.importorskip("pandas")
        pytest.importorskip("tables")
        p = tmp_path / "dlc_partial.h5"

        # Only x and y, no likelihood
        cols = pd.MultiIndex.from_tuples([("scorer", "nose", "x"), ("scorer", "nose", "y")])
        df = pd.DataFrame(np.array([[1.0, 2.0]]), columns=cols)
        df.to_hdf(p, key="df_with_missing", mode="w")

        rows = _load_dlc_h5(p)
        assert len(rows) == 1
        assert rows[0]["nose_x"] == 1.0
        assert "nose_likelihood" not in rows[0]

    def test_multi_animal_missing_coord(self, tmp_path: Path) -> None:
        """KeyError fallback for multi-animal DLC with missing coords."""
        pd = pytest.importorskip("pandas")
        pytest.importorskip("tables")
        p = tmp_path / "dlc_multi_partial.h5"

        # Only x, no y or likelihood
        cols = pd.MultiIndex.from_tuples(
            [("scorer", "mouse1", "nose", "x"), ("scorer", "mouse2", "nose", "x")]
        )
        df = pd.DataFrame(np.array([[1.0, 2.0]]), columns=cols)
        df.to_hdf(p, key="df_with_missing", mode="w")

        rows = _load_dlc_h5(p)
        assert len(rows) == 2
        assert rows[0]["nose_x"] == 1.0
        assert "nose_y" not in rows[0]

    def test_two_level_multiindex_returns_empty(self, tmp_path: Path) -> None:
        pd = pytest.importorskip("pandas")
        pytest.importorskip("tables")
        p = tmp_path / "twolevel.h5"
        cols = pd.MultiIndex.from_tuples([("a", "x"), ("a", "y")])
        df = pd.DataFrame(np.zeros((2, 2)), columns=cols)
        df.to_hdf(p, key="df", mode="w")
        assert _load_dlc_h5(p) == []


# ---------------------------------------------------------------------------
# H5 dispatcher
# ---------------------------------------------------------------------------


class TestH5Dispatch:
    def test_sam_detected_by_positions_key(self, tmp_path: Path) -> None:
        h5py = pytest.importorskip("h5py")
        p = tmp_path / "dispatch.h5"
        with h5py.File(p, "w") as f:
            f.create_dataset("positions", data=np.zeros((2, 1, 2)))
        rows = _load_h5(p)
        assert len(rows) == 2
        assert rows[0]["animal_id"] == "animal_0"

    def test_falls_through_to_dlc(self, tmp_path: Path) -> None:
        pytest.importorskip("h5py")
        pd = pytest.importorskip("pandas")
        pytest.importorskip("tables")
        p = tmp_path / "dlc_dispatch.h5"

        cols = pd.MultiIndex.from_tuples(
            [("sc", "bp", "x"), ("sc", "bp", "y"), ("sc", "bp", "likelihood")]
        )
        df = pd.DataFrame(np.ones((1, 3)), columns=cols)
        df.to_hdf(p, key="df_with_missing", mode="w")

        rows = _load_h5(p)
        assert len(rows) == 1
        assert "bp_x" in rows[0]

    def test_missing_h5py_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "no_h5py.h5"
        p.write_bytes(b"fake")
        with patch("builtins.__import__", side_effect=_block_import("h5py")):
            result = _load_h5(p)
        assert result == []


# ---------------------------------------------------------------------------
# NWB loader
# ---------------------------------------------------------------------------


class TestNwb:
    def test_missing_pynwb_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "test.nwb"
        p.write_bytes(b"fake")
        with patch("builtins.__import__", side_effect=_block_import("pynwb")):
            result = _load_nwb(p)
        assert result == []

    def test_corrupt_nwb_returns_empty(self, tmp_path: Path) -> None:
        pytest.importorskip("pynwb")
        p = tmp_path / "bad.nwb"
        p.write_bytes(b"not nwb data")
        assert _load_nwb(p) == []

    def test_nwb_with_behavior_position(self, tmp_path: Path) -> None:
        pynwb = pytest.importorskip("pynwb")
        p = tmp_path / "behavior.nwb"

        nwb = pynwb.NWBFile(
            session_description="test",
            identifier="test-001",
            session_start_time=datetime(2024, 1, 1, tzinfo=UTC),
        )

        spatial = pynwb.behavior.SpatialSeries(
            name="position",
            data=np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]),
            timestamps=np.array([0.0, 0.1, 0.2]),
            reference_frame="arena center",
        )
        pos = pynwb.behavior.Position(spatial_series=spatial)
        behavior = nwb.create_processing_module(name="behavior", description="tracking")
        behavior.add(pos)

        with pynwb.NWBHDF5IO(str(p), "w") as io:
            io.write(nwb)

        rows = _load_nwb(p)
        assert len(rows) == 3
        assert rows[0]["x"] == 1.0
        assert rows[0]["y"] == 2.0
        assert rows[0]["time_sec"] == 0.0

    def test_nwb_acquisition_fallback(self, tmp_path: Path) -> None:
        pynwb = pytest.importorskip("pynwb")
        p = tmp_path / "acquisition.nwb"

        nwb = pynwb.NWBFile(
            session_description="test",
            identifier="test-002",
            session_start_time=datetime(2024, 1, 1, tzinfo=UTC),
        )

        ts = pynwb.TimeSeries(
            name="velocity",
            data=np.array([10.0, 20.0, 30.0]),
            timestamps=np.array([0.0, 1.0, 2.0]),
            unit="cm/s",
        )
        nwb.add_acquisition(ts)

        with pynwb.NWBHDF5IO(str(p), "w") as io:
            io.write(nwb)

        rows = _load_nwb(p)
        assert len(rows) == 3
        assert rows[0]["value"] == 10.0
        assert rows[0]["time_sec"] == 0.0

    def test_nwb_empty_file(self, tmp_path: Path) -> None:
        pynwb = pytest.importorskip("pynwb")
        p = tmp_path / "empty.nwb"

        nwb = pynwb.NWBFile(
            session_description="empty",
            identifier="test-003",
            session_start_time=datetime(2024, 1, 1, tzinfo=UTC),
        )
        with pynwb.NWBHDF5IO(str(p), "w") as io:
            io.write(nwb)

        rows = _load_nwb(p)
        assert rows == []


# ---------------------------------------------------------------------------
# _extract_nwb_spatial_series
# ---------------------------------------------------------------------------


class TestExtractNwbSpatialSeries:
    def test_position_with_1d_data(self) -> None:
        pynwb = pytest.importorskip("pynwb")
        ss = pynwb.behavior.SpatialSeries(
            name="pos1d",
            data=np.array([1.0, 2.0]),
            timestamps=np.array([0.0, 0.1]),
            reference_frame="origin",
        )
        pos = pynwb.behavior.Position(spatial_series=ss)
        rows = _extract_nwb_spatial_series(pos)
        assert len(rows) == 2
        assert rows[0]["x"] == 1.0
        assert "y" not in rows[0]

    def test_position_with_3d_data(self) -> None:
        pynwb = pytest.importorskip("pynwb")
        ss = pynwb.behavior.SpatialSeries(
            name="pos3d",
            data=np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
            timestamps=np.array([0.0, 0.1]),
            reference_frame="origin",
        )
        pos = pynwb.behavior.Position(spatial_series=ss)
        rows = _extract_nwb_spatial_series(pos)
        assert len(rows) == 2
        assert rows[0]["z"] == 3.0

    def test_position_no_timestamps_uses_rate(self) -> None:
        pynwb = pytest.importorskip("pynwb")
        ss = pynwb.behavior.SpatialSeries(
            name="pos_rate",
            data=np.array([[1.0, 2.0], [3.0, 4.0]]),
            rate=30.0,
            reference_frame="origin",
        )
        pos = pynwb.behavior.Position(spatial_series=ss)
        rows = _extract_nwb_spatial_series(pos)
        assert len(rows) == 2
        assert rows[0]["time_sec"] == pytest.approx(0.0)
        assert rows[1]["time_sec"] == pytest.approx(30.0)

    def test_generic_timeseries_2d(self) -> None:
        pynwb = pytest.importorskip("pynwb")
        ts = pynwb.TimeSeries(
            name="multi_col",
            data=np.array([[1.0, 2.0], [3.0, 4.0]]),
            timestamps=np.array([0.0, 1.0]),
            unit="au",
        )
        rows = _extract_nwb_spatial_series(ts)
        assert len(rows) == 2
        assert rows[0]["col_0"] == 1.0
        assert rows[0]["col_1"] == 2.0

    def test_generic_timeseries_no_timestamps(self) -> None:
        pynwb = pytest.importorskip("pynwb")
        ts = pynwb.TimeSeries(
            name="no_ts",
            data=np.array([10.0, 20.0]),
            rate=1.0,
            unit="au",
        )
        rows = _extract_nwb_spatial_series(ts)
        assert len(rows) == 2
        assert rows[0]["time_sec"] == 0.0
        assert rows[1]["time_sec"] == 1.0

    def test_non_data_container_returns_empty(self) -> None:
        """Object without data/timestamps attributes."""
        rows = _extract_nwb_spatial_series(object())
        assert rows == []
