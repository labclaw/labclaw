"""Plate reader CSV driver — parses 96-well plate CSV exports.

Handles common plate reader CSV formats: header metadata rows followed
by an 8×12 grid (rows A–H, columns 1–12).

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from labclaw.hardware.interfaces.file_based import FileBasedDriver

logger = logging.getLogger(__name__)

# 96-well row letters (A–H) and column numbers (1–12)
_ROW_LETTERS = list("ABCDEFGH")
_COL_NUMBERS = list(range(1, 13))


class PlateReaderCSVDriver(FileBasedDriver):
    """Driver for plate reader CSV exports (96-well format).

    Expects CSV files where:
      - Leading rows without a recognised row letter are treated as metadata.
      - Grid rows start with a row letter (A–H) followed by 12 numeric values.
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
            file_patterns or ["*.csv"],
        )

    def parse_file(self, path: Path) -> dict[str, Any]:
        """Parse a 96-well plate CSV.

        Returns::

            {
                "wells": {"A1": 0.123, "A2": 0.456, ..., "H12": 1.234},
                "metadata": {"Instrument": "...", ...},
                "file": "/path/to/file.csv",
            }
        """
        metadata: dict[str, str] = {}
        wells: dict[str, float | str] = {}

        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            for raw_row in reader:
                if not raw_row:
                    continue

                first = raw_row[0].strip()

                # Detect grid row: first cell is a single letter A–H
                if first.upper() in _ROW_LETTERS:
                    row_letter = first.upper()
                    values = raw_row[1:]
                    for col_idx, val in enumerate(values):
                        if col_idx >= len(_COL_NUMBERS):
                            break
                        col_num = _COL_NUMBERS[col_idx]
                        well_key = f"{row_letter}{col_num}"
                        stripped = val.strip()
                        try:
                            wells[well_key] = float(stripped)
                        except ValueError:
                            wells[well_key] = stripped
                else:
                    # Treat as metadata: "Key,Value" or "Key,Value,..."
                    if len(raw_row) >= 2:
                        key = first
                        value = raw_row[1].strip()
                        if key:
                            metadata[key] = value

        logger.debug(
            "PlateReaderCSVDriver parsed %d wells, %d metadata fields from %s",
            len(wells),
            len(metadata),
            path,
        )
        return {"wells": wells, "metadata": metadata, "file": str(path)}
