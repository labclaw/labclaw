"""Tests for DataAccumulator from labclaw.daemon."""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from labclaw.daemon import DataAccumulator


def _write_csv(path: Path, rows: list[dict]) -> None:
    """Write a CSV file with given list-of-dicts rows."""
    if not rows:
        path.write_text("a,b,c\n", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _append_csv_rows(path: Path, rows: list[dict]) -> None:
    """Append data rows to an existing CSV (no header)."""
    fieldnames = list(rows[0].keys())
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Basic ingestion
# ---------------------------------------------------------------------------


def test_ingest_csv_file(tmp_path: Path) -> None:
    """CSV with 3 numeric rows: returns 3, total_rows=3, files_processed=1."""
    acc = DataAccumulator()
    csv_path = tmp_path / "data.csv"
    rows = [{"a": 1, "b": 2, "c": 3}, {"a": 4, "b": 5, "c": 6}, {"a": 7, "b": 8, "c": 9}]
    _write_csv(csv_path, rows)

    result = acc.ingest_file(csv_path)

    assert result == 3
    assert acc.total_rows == 3
    assert acc.files_processed == 1
    all_rows = acc.get_all_rows()
    assert len(all_rows) == 3
    # Numeric values must be parsed as floats
    for row in all_rows:
        for key in ("a", "b", "c"):
            assert isinstance(row[key], float), f"Expected float for {key}, got {type(row[key])}"


def test_ingest_tsv_file(tmp_path: Path) -> None:
    """TSV file is parsed correctly using tab delimiter."""
    acc = DataAccumulator()
    tsv_path = tmp_path / "data.tsv"
    tsv_path.write_text("x\ty\n1.0\t2.5\n3.0\t4.5\n", encoding="utf-8")

    result = acc.ingest_file(tsv_path)

    assert result == 2
    assert acc.total_rows == 2
    assert acc.files_processed == 1
    all_rows = acc.get_all_rows()
    assert all_rows[0]["x"] == pytest.approx(1.0)
    assert all_rows[1]["y"] == pytest.approx(4.5)


def test_ingest_skips_non_tabular(tmp_path: Path) -> None:
    """Non-.csv/.tsv/.txt file returns 0 without error."""
    acc = DataAccumulator()
    json_path = tmp_path / "data.json"
    json_path.write_text('{"key": "value"}', encoding="utf-8")

    result = acc.ingest_file(json_path)

    assert result == 0
    assert acc.total_rows == 0
    assert acc.files_processed == 0


def test_ingest_empty_csv(tmp_path: Path) -> None:
    """CSV with only a header row yields 0 data rows."""
    acc = DataAccumulator()
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("a,b,c\n", encoding="utf-8")

    result = acc.ingest_file(csv_path)

    assert result == 0
    assert acc.total_rows == 0
    # File was opened successfully; offset tracking is not updated for zero-row files
    assert acc.files_processed == 0


# ---------------------------------------------------------------------------
# Idempotency and offset tracking
# ---------------------------------------------------------------------------


def test_ingest_twice_same_file(tmp_path: Path) -> None:
    """Ingesting the same file twice: second call returns 0 (offset already at end)."""
    acc = DataAccumulator()
    csv_path = tmp_path / "once.csv"
    _write_csv(csv_path, [{"a": 1, "b": 2}, {"a": 3, "b": 4}])

    first = acc.ingest_file(csv_path)
    second = acc.ingest_file(csv_path)

    assert first == 2
    assert second == 0
    assert acc.total_rows == 2
    assert acc.files_processed == 1


def test_ingest_file_grows(tmp_path: Path) -> None:
    """First ingest reads 2 rows; after appending 3 more, second ingest reads exactly 3."""
    acc = DataAccumulator()
    csv_path = tmp_path / "growing.csv"
    _write_csv(csv_path, [{"val": 1}, {"val": 2}])

    first = acc.ingest_file(csv_path)
    assert first == 2

    _append_csv_rows(csv_path, [{"val": 3}, {"val": 4}, {"val": 5}])

    second = acc.ingest_file(csv_path)
    assert second == 3
    assert acc.total_rows == 5
    assert acc.files_processed == 1


def test_ingest_file_truncated(tmp_path: Path) -> None:
    """When a file shrinks below the known offset, the cursor resets and all rows are re-read."""
    acc = DataAccumulator()
    csv_path = tmp_path / "truncated.csv"
    _write_csv(csv_path, [{"v": i} for i in range(5)])

    first = acc.ingest_file(csv_path)
    assert first == 5

    # Rewrite the file with fewer rows (simulates instrument restarting)
    _write_csv(csv_path, [{"v": 99}, {"v": 100}])

    second = acc.ingest_file(csv_path)
    assert second == 2
    # total_rows reflects the deque accumulation (5 + 2)
    assert acc.total_rows == 7


def test_ingest_nonexistent_file(tmp_path: Path) -> None:
    """Non-existent file path returns 0 and does not raise."""
    acc = DataAccumulator()
    missing = tmp_path / "does_not_exist.csv"

    result = acc.ingest_file(missing)

    assert result == 0
    assert acc.total_rows == 0
    assert acc.files_processed == 0


# ---------------------------------------------------------------------------
# Mixed types
# ---------------------------------------------------------------------------


def test_mixed_numeric_and_string(tmp_path: Path) -> None:
    """Numeric columns become float; string columns remain strings."""
    acc = DataAccumulator()
    csv_path = tmp_path / "mixed.csv"
    csv_path.write_text("name,score\nalpha,3.14\nbeta,2.71\n", encoding="utf-8")

    result = acc.ingest_file(csv_path)

    assert result == 2
    rows = acc.get_all_rows()
    assert rows[0]["name"] == "alpha"
    assert isinstance(rows[0]["name"], str)
    assert rows[0]["score"] == pytest.approx(3.14)
    assert isinstance(rows[0]["score"], float)
    assert rows[1]["name"] == "beta"
    assert rows[1]["score"] == pytest.approx(2.71)


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_concurrent_ingest_same_file(tmp_path: Path) -> None:
    """Two threads ingesting the same file: the in-progress guard lets only one proceed."""
    acc = DataAccumulator()
    csv_path = tmp_path / "concurrent.csv"
    _write_csv(csv_path, [{"x": i} for i in range(10)])

    results: list[int] = []
    barrier = threading.Barrier(2)

    def ingest_worker() -> None:
        barrier.wait()  # Both threads start at the same time
        results.append(acc.ingest_file(csv_path))

    t1 = threading.Thread(target=ingest_worker)
    t2 = threading.Thread(target=ingest_worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # One thread gets 10, the other gets 0 (blocked by _files_in_progress guard)
    # OR both complete sequentially with the second getting 0 from the offset
    assert sum(results) == 10
    assert acc.total_rows == 10


def test_ingest_file_exception_returns_zero(tmp_path: Path) -> None:
    """When load_file raises, ingest_file returns 0 and releases the lock."""
    acc = DataAccumulator()
    csv_path = tmp_path / "boom.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    with patch("labclaw.daemon.load_file", side_effect=RuntimeError("parse error")):
        result = acc.ingest_file(csv_path)

    assert result == 0
    assert acc.total_rows == 0
    # Lock released — file not stuck in _files_in_progress
    assert str(csv_path) not in acc._files_in_progress


def test_h5_ingest_then_skip_reingest(tmp_path: Path) -> None:
    """H5/NWB files are ingested once; re-ingest is skipped via sentinel."""
    acc = DataAccumulator()
    h5_path = tmp_path / "data.h5"
    h5_path.write_bytes(b"fake")  # content doesn't matter, we mock load_file

    fake_rows = [{"frame": i, "x": float(i)} for i in range(5)]
    with patch("labclaw.daemon.load_file", return_value=fake_rows):
        first = acc.ingest_file(h5_path)
    assert first == 5
    assert acc.files_processed == 1

    # Re-ingest the same H5 file — should be skipped (sentinel dedup)
    with patch("labclaw.daemon.load_file", return_value=fake_rows):
        second = acc.ingest_file(h5_path)
    assert second == 0
    assert acc.total_rows == 5  # no duplicates
