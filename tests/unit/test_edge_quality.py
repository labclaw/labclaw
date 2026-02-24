"""Tests for QualityChecker from labclaw.edge.quality."""

from __future__ import annotations

from pathlib import Path

import pytest

from labclaw.core.schemas import FileReference, QualityLevel
from labclaw.edge.quality import QualityChecker

# ---------------------------------------------------------------------------
# check_file
# ---------------------------------------------------------------------------


def test_check_file_good(tmp_path: Path) -> None:
    """Existing non-empty file returns level=GOOD with value=file_size in bytes."""
    checker = QualityChecker()
    p = tmp_path / "data.bin"
    content = b"hello world"
    p.write_bytes(content)
    ref = FileReference(path=p)

    metric = checker.check_file(ref)

    assert metric.level == QualityLevel.GOOD
    assert metric.value == pytest.approx(len(content))


def test_check_file_not_exists(tmp_path: Path) -> None:
    """Non-existent file returns level=CRITICAL, name='file_exists'."""
    checker = QualityChecker()
    ref = FileReference(path=tmp_path / "missing.csv")

    metric = checker.check_file(ref)

    assert metric.level == QualityLevel.CRITICAL
    assert metric.name == "file_exists"


def test_check_file_empty(tmp_path: Path) -> None:
    """Empty file returns level=WARNING, name='file_non_empty'."""
    checker = QualityChecker()
    p = tmp_path / "empty.txt"
    p.write_bytes(b"")
    ref = FileReference(path=p)

    metric = checker.check_file(ref)

    assert metric.level == QualityLevel.WARNING
    assert metric.name == "file_non_empty"


# ---------------------------------------------------------------------------
# check_video
# ---------------------------------------------------------------------------


def test_check_video_good_extension(tmp_path: Path) -> None:
    """Valid .mp4 file with content: 2 metrics, second has name='video_extension', level=GOOD."""
    checker = QualityChecker()
    p = tmp_path / "recording.mp4"
    p.write_bytes(b"\x00" * 512)
    ref = FileReference(path=p)

    metrics = checker.check_video(ref)

    assert len(metrics) == 2
    ext_metric = metrics[1]
    assert ext_metric.name == "video_extension"
    assert ext_metric.level == QualityLevel.GOOD


def test_check_video_bad_extension(tmp_path: Path) -> None:
    """Unrecognised extension .xyz: video_extension metric has level=WARNING."""
    checker = QualityChecker()
    p = tmp_path / "clip.xyz"
    p.write_bytes(b"\x00" * 256)
    ref = FileReference(path=p)

    metrics = checker.check_video(ref)

    assert len(metrics) == 2
    ext_metric = metrics[1]
    assert ext_metric.name == "video_extension"
    assert ext_metric.level == QualityLevel.WARNING


# ---------------------------------------------------------------------------
# check_generic
# ---------------------------------------------------------------------------


def test_check_generic_existing_file(tmp_path: Path) -> None:
    """Existing readable file: 3 metrics (file_exists, file_size, file_readable), all GOOD."""
    checker = QualityChecker()
    p = tmp_path / "sample.dat"
    p.write_bytes(b"data" * 100)
    ref = FileReference(path=p)

    metrics = checker.check_generic(ref)

    assert len(metrics) == 3
    names = [m.name for m in metrics]
    assert "file_exists" in names
    assert "file_size" in names
    assert "file_readable" in names
    assert all(m.level == QualityLevel.GOOD for m in metrics)


def test_check_generic_nonexistent(tmp_path: Path) -> None:
    """Non-existent file: 1 metric (file_exists=CRITICAL), returns early."""
    checker = QualityChecker()
    ref = FileReference(path=tmp_path / "ghost.dat")

    metrics = checker.check_generic(ref)

    assert len(metrics) == 1
    assert metrics[0].name == "file_exists"
    assert metrics[0].level == QualityLevel.CRITICAL


def test_check_generic_empty_file(tmp_path: Path) -> None:
    """Empty file: file_exists=GOOD, file_size=WARNING."""
    checker = QualityChecker()
    p = tmp_path / "empty.dat"
    p.write_bytes(b"")
    ref = FileReference(path=p)

    metrics = checker.check_generic(ref)

    exists_metric = next(m for m in metrics if m.name == "file_exists")
    size_metric = next(m for m in metrics if m.name == "file_size")
    assert exists_metric.level == QualityLevel.GOOD
    assert size_metric.level == QualityLevel.WARNING
