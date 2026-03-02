"""Data ingestion loaders — unified file→rows for all supported formats.

Supported formats:
  - CSV / TSV / TXT  (flat tabular)
  - SAM-Behavior H5  (/positions dataset, shape [n_frames, n_animals, 2])
  - DeepLabCut H5    (pandas MultiIndex: scorer/individuals/bodyparts/coords)
  - NWB              (pynwb Position / BehavioralTimeSeries)

All loaders produce list[dict[str, Any]], one dict per observation.
Optional deps (h5py, pandas, pynwb) are imported lazily; missing → warning + [].
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_FPS = 30.0

# CSV/TSV/TXT files grow by appending rows; H5/NWB always return the complete dataset.
_APPEND_ONLY_EXTENSIONS = frozenset((".csv", ".tsv", ".txt"))


def is_append_only(path: Path) -> bool:
    """Return True if the file format supports incremental (append-only) ingestion."""
    return path.suffix.lower() in _APPEND_ONLY_EXTENSIONS


def load_file(path: Path) -> list[dict[str, Any]]:
    """Load any supported file into flat rows. Auto-detects by extension + content."""
    if not path.is_file():
        logger.debug("File not found: %s", path)
        return []

    ext = path.suffix.lower()
    if ext in (".csv", ".tsv", ".txt"):
        return _load_csv(path)
    if ext == ".h5":
        return _load_h5(path)
    if ext == ".nwb":
        return _load_nwb(path)

    logger.debug("Unsupported format: %s", path)
    return []


# ---------------------------------------------------------------------------
# CSV / TSV loader (extracted from daemon.py)
# ---------------------------------------------------------------------------


def _load_csv(path: Path) -> list[dict[str, Any]]:
    """Parse CSV/TSV into flat rows with numeric auto-conversion."""
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    rows: list[dict[str, Any]] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            parsed: dict[str, Any] = {}
            for k, v in row.items():
                if k is None:
                    continue
                try:
                    parsed[k] = float(v)
                except (ValueError, TypeError):
                    parsed[k] = v
            if parsed:
                rows.append(parsed)
    return rows


# ---------------------------------------------------------------------------
# HDF5 loader — sniffs SAM-Behavior vs DeepLabCut
# ---------------------------------------------------------------------------


def _load_h5(path: Path) -> list[dict[str, Any]]:
    """Dispatch H5 files: /positions → SAM, else try DLC MultiIndex."""
    try:
        import h5py
    except ImportError:
        logger.warning("h5py not installed; cannot read %s", path)
        return []

    with h5py.File(path, "r") as f:
        if "positions" in f:
            return _load_sam_h5(path, f)

    # Not SAM — try DLC format via pandas
    return _load_dlc_h5(path)


def _load_sam_h5(path: Path, f: Any) -> list[dict[str, Any]]:
    """SAM-Behavior H5: /positions [n_frames, n_animals, 2], optional /timestamps."""
    import numpy as np

    positions = np.asarray(f["positions"])
    if positions.ndim != 3 or positions.shape[2] != 2:
        logger.warning("Unexpected /positions shape %s in %s", positions.shape, path)
        return []

    n_frames, n_animals = positions.shape[0], positions.shape[1]
    timestamps = np.asarray(f["timestamps"]) if "timestamps" in f else None

    rows: list[dict[str, Any]] = []
    for frame_idx in range(n_frames):
        time_sec = (
            float(timestamps[frame_idx]) if timestamps is not None else frame_idx / _DEFAULT_FPS
        )
        for animal_idx in range(n_animals):
            rows.append(
                {
                    "frame": frame_idx,
                    "time_sec": time_sec,
                    "animal_id": f"animal_{animal_idx}",
                    "x": float(positions[frame_idx, animal_idx, 0]),
                    "y": float(positions[frame_idx, animal_idx, 1]),
                }
            )
    return rows


def _load_dlc_h5(path: Path) -> list[dict[str, Any]]:
    """DeepLabCut H5: pandas MultiIndex (scorer/individuals/bodyparts/coords)."""
    try:
        import pandas as pd
    except ImportError:
        logger.warning("pandas not installed; cannot read DLC file %s", path)
        return []

    try:
        df = pd.read_hdf(path)
    except Exception:
        logger.warning("Could not read HDF5 as DLC format: %s", path, exc_info=True)
        return []

    if not isinstance(df.columns, pd.MultiIndex):
        logger.warning("H5 file lacks MultiIndex columns (not DLC format): %s", path)
        return []

    # DLC MultiIndex levels: scorer / individuals (or bodyparts) / coords
    # Handle both single-animal (scorer/bodyparts/coords) and
    # multi-animal (scorer/individuals/bodyparts/coords) layouts
    n_levels = df.columns.nlevels
    rows: list[dict[str, Any]] = []

    if n_levels >= 4:
        # Multi-animal: (scorer, individual, bodypart, coord)
        individuals = df.columns.get_level_values(1).unique()
        scorer = df.columns.get_level_values(0)[0]
        bodyparts = df.columns.get_level_values(2).unique()
        for frame_idx in range(len(df)):
            sub = df.iloc[frame_idx]
            for individual in individuals:
                row: dict[str, Any] = {
                    "frame": frame_idx,
                    "animal_id": str(individual),
                }
                for bp in bodyparts:
                    for coord in ("x", "y", "likelihood"):
                        try:
                            val = sub[(scorer, individual, bp, coord)]
                            row[f"{bp}_{coord}"] = float(val)
                        except KeyError:
                            pass
                rows.append(row)
    elif n_levels == 3:
        # Single-animal: (scorer, bodypart, coord)
        scorer = df.columns.get_level_values(0)[0]
        bodyparts = df.columns.get_level_values(1).unique()
        for frame_idx in range(len(df)):
            row = {"frame": frame_idx, "animal_id": "single"}
            sub = df.iloc[frame_idx]
            for bp in bodyparts:
                for coord in ("x", "y", "likelihood"):
                    try:
                        val = sub[(scorer, bp, coord)]
                        row[f"{bp}_{coord}"] = float(val)
                    except KeyError:
                        pass
            rows.append(row)
    else:
        logger.warning("Unexpected MultiIndex levels (%d) in %s", n_levels, path)

    return rows


# ---------------------------------------------------------------------------
# NWB loader — pynwb Position / BehavioralTimeSeries
# ---------------------------------------------------------------------------


def _load_nwb(path: Path) -> list[dict[str, Any]]:
    """Load behavioral tracking data from an NWB file."""
    try:
        import pynwb
    except ImportError:
        logger.warning("pynwb not installed; cannot read %s", path)
        return []

    try:
        io = pynwb.NWBHDF5IO(str(path), "r")
    except Exception:
        logger.warning("Could not open NWB file: %s", path, exc_info=True)
        return []

    rows: list[dict[str, Any]] = []
    try:
        nwb = io.read()

        if "behavior" in nwb.processing:
            behavior = nwb.processing["behavior"]
            for container_name in behavior.data_interfaces:
                container = behavior.data_interfaces[container_name]
                rows.extend(_extract_nwb_spatial_series(container))

        if not rows:
            # Try acquisition as fallback
            for acq_name in nwb.acquisition:
                acq = nwb.acquisition[acq_name]
                rows.extend(_extract_nwb_spatial_series(acq))
    except Exception:
        logger.warning("Could not read NWB file: %s", path, exc_info=True)
    finally:
        io.close()

    return rows


def _extract_nwb_spatial_series(container: Any) -> list[dict[str, Any]]:
    """Extract rows from a Position or SpatialSeries NWB container."""
    import numpy as np

    rows: list[dict[str, Any]] = []

    try:
        from pynwb.behavior import Position
    except ImportError:  # pragma: no cover
        return []

    if isinstance(container, Position):
        for ss_name in container.spatial_series:
            ss = container.spatial_series[ss_name]
            data = np.asarray(ss.data)
            timestamps = np.asarray(ss.timestamps) if ss.timestamps is not None else None

            for i in range(len(data)):
                row: dict[str, Any] = {
                    "frame": i,
                    "time_sec": float(timestamps[i])
                    if timestamps is not None
                    else i / ss.rate
                    if hasattr(ss, "rate") and ss.rate
                    else float(i),
                    "animal_id": str(ss_name),
                }
                if data.ndim == 1:
                    row["x"] = float(data[i])
                elif data.ndim == 2 and data.shape[1] >= 2:
                    row["x"] = float(data[i, 0])
                    row["y"] = float(data[i, 1])
                    if data.shape[1] >= 3:
                        row["z"] = float(data[i, 2])
                rows.append(row)
    else:
        # Generic SpatialSeries or TimeSeries
        if hasattr(container, "data") and hasattr(container, "timestamps"):
            data = np.asarray(container.data)
            timestamps = (
                np.asarray(container.timestamps) if container.timestamps is not None else None
            )
            for i in range(len(data)):
                row = {
                    "time_sec": float(timestamps[i]) if timestamps is not None else float(i),
                }
                if data.ndim == 1:
                    row["value"] = float(data[i])
                elif data.ndim == 2:
                    for col_idx in range(data.shape[1]):
                        row[f"col_{col_idx}"] = float(data[i, col_idx])
                rows.append(row)

    return rows
