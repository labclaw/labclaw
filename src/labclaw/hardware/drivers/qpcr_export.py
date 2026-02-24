"""qPCR export driver — parses StepOnePlus qPCR export files.

StepOnePlus exports are tab-separated with metadata header blocks
followed by a results table containing Ct values, sample names, and well positions.

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from labclaw.hardware.interfaces.file_based import FileBasedDriver

logger = logging.getLogger(__name__)

# Column names used by StepOnePlus exports (case-insensitive matching)
_WELL_COLS = {"well", "well position"}
_SAMPLE_COLS = {"sample name", "sample"}
_CT_COLS = {"ct", "cт", "cycle threshold"}
_DETECTOR_COLS = {"detector name", "target name", "detector"}


def _find_col(header: list[str], candidates: set[str]) -> int | None:
    """Return index of first header field matching any candidate (case-insensitive)."""
    for idx, field in enumerate(header):
        if field.strip().lower() in candidates:
            return idx
    return None


class QPCRExportDriver(FileBasedDriver):
    """Driver for StepOnePlus qPCR export files (tab-separated).

    Parses the results block starting after the header row that contains
    a 'Well' column.  All other rows before that are treated as metadata.
    """

    def __init__(
        self,
        device_id: str,
        device_type: str,
        watch_path: Path,
        file_patterns: list[str] | None = None,
    ) -> None:
        super().__init__(
            device_id,
            device_type,
            watch_path,
            file_patterns or ["*.txt", "*.tsv", "*.csv"],
        )

    def parse_file(self, path: Path) -> dict[str, Any]:
        """Parse a StepOnePlus export file.

        Returns::

            {
                "samples": [
                    {"well": "A1", "name": "Sample1", "detector": "GAPDH", "ct": 22.4},
                    ...
                ],
                "metadata": {"Experiment Name": "...", ...},
                "file": "/path/to/file.txt",
            }
        """
        # Detect delimiter from extension
        suffix = path.suffix.lower()
        delimiter = "\t" if suffix in {".txt", ".tsv"} else ","

        metadata: dict[str, str] = {}
        samples_list: list[dict[str, Any]] = []
        in_results = False
        col_well: int | None = None
        col_sample: int | None = None
        col_ct: int | None = None
        col_detector: int | None = None

        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh, delimiter=delimiter)
            for raw_row in reader:
                if not raw_row or all(c.strip() == "" for c in raw_row):
                    if in_results:
                        # Blank line signals end of results block
                        break
                    continue

                if not in_results:
                    # Look for the results header row (contains a Well column)
                    stripped = [c.strip() for c in raw_row]
                    well_idx = _find_col(stripped, _WELL_COLS)
                    if well_idx is not None:
                        in_results = True
                        col_well = well_idx
                        col_sample = _find_col(stripped, _SAMPLE_COLS)
                        col_ct = _find_col(stripped, _CT_COLS)
                        col_detector = _find_col(stripped, _DETECTOR_COLS)
                    else:
                        # Metadata line: "Key\tValue" or "Key,Value"
                        if len(raw_row) >= 2:
                            key = raw_row[0].strip()
                            value = raw_row[1].strip()
                            if key:
                                metadata[key] = value
                    continue

                # Results data row
                fields = [c.strip() for c in raw_row]

                def _get(idx: int | None) -> str:
                    if idx is None or idx >= len(fields):
                        return ""
                    return fields[idx]

                well = _get(col_well)
                if not well:
                    continue

                ct_raw = _get(col_ct)
                ct_value: float | str
                try:
                    undetermined = {"UNDETERMINED", "N/A", ""}
                    ct_value = (
                        float(ct_raw)
                        if ct_raw and ct_raw.upper() not in undetermined
                        else ct_raw
                    )
                except ValueError:
                    ct_value = ct_raw

                samples_list.append({
                    "well": well,
                    "name": _get(col_sample),
                    "detector": _get(col_detector),
                    "ct": ct_value,
                })

        logger.debug(
            "QPCRExportDriver parsed %d samples, %d metadata fields from %s",
            len(samples_list),
            len(metadata),
            path,
        )
        return {"samples": samples_list, "metadata": metadata, "file": str(path)}
