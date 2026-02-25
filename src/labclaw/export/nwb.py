"""NWB exporter — writes findings + provenance to NWB or JSON fallback.

pynwb is an optional dependency. When not installed, a structured JSON
file is produced instead (same schema, different container).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class NWBExporter:
    """Export findings and provenance to NWB format (or JSON fallback)."""

    def export_session(self, session_data: dict[str, Any], output_path: Path) -> Path:
        """Export session data and findings to NWB or JSON file.

        Tries to use pynwb when available. Falls back to a structured JSON
        stub so callers never need to check whether pynwb is installed.

        Args:
            session_data: Dict with keys: session_id, findings, provenance_steps,
                          data_rows (optional), metadata (optional).
            output_path: Destination file path (.nwb or .json).

        Returns:
            Resolved path to the written file.
        """
        try:
            import pynwb  # noqa: F401

            return self._export_nwb(session_data, output_path)
        except ImportError:
            logger.debug("pynwb not installed; using JSON fallback")
            return self._export_json_stub(session_data, output_path)

    def _export_nwb(self, session_data: dict[str, Any], output_path: Path) -> Path:
        """Write a real NWB file using pynwb.

        Args:
            session_data: Session payload (see export_session).
            output_path: Destination file (.nwb).

        Returns:
            Resolved path to the written file.
        """
        import pynwb
        from dateutil.parser import parse as parse_dt

        session_id = session_data.get("session_id", str(uuid.uuid4()))
        session_start_raw = session_data.get("session_start_time", _now_iso())
        try:
            session_start = parse_dt(session_start_raw)
        except Exception:
            session_start = datetime.now(UTC)

        nwb_file = pynwb.NWBFile(
            session_description=session_data.get(
                "description", "LabClaw automated discovery session"
            ),
            identifier=session_id,
            session_start_time=session_start,
        )

        # Attach provenance as a lab_meta_data JSON blob
        provenance_json = json.dumps(
            {
                "findings": session_data.get("findings", []),
                "provenance_steps": session_data.get("provenance_steps", []),
                "finding_chains": session_data.get("finding_chains", []),
                "exported_at": _now_iso(),
            },
            default=str,
        )
        nwb_file.add_lab_meta_data(
            pynwb.file.LabMetaData(
                name="labclaw_provenance",
                # Store the raw JSON string as a TimeSeries notes field
            )
        )
        # Attach as a scratch entry (portable across NWB versions)
        scratch = pynwb.core.ScratchData(
            name="labclaw_provenance",
            data=provenance_json,
            description="LabClaw provenance chain for this session",
        )
        nwb_file.add_scratch(scratch)

        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with pynwb.NWBHDF5IO(str(output_path), "w") as io:
            io.write(nwb_file)

        logger.info("Exported NWB file: %s", output_path)
        return output_path

    def _export_json_stub(self, session_data: dict[str, Any], output_path: Path) -> Path:
        """Write a structured JSON file when pynwb is not available.

        The JSON mirrors the data that would be placed in the NWB scratch.

        Args:
            session_data: Session payload (see export_session).
            output_path: Destination file (.json or any extension).

        Returns:
            Resolved path to the written file.
        """
        session_id = session_data.get("session_id", str(uuid.uuid4()))
        payload: dict[str, Any] = {
            "format": "labclaw-json-stub",
            "version": "1.0",
            "session_id": session_id,
            "session_start_time": session_data.get("session_start_time", _now_iso()),
            "description": session_data.get(
                "description", "LabClaw automated discovery session"
            ),
            "findings": session_data.get("findings", []),
            "provenance_steps": session_data.get("provenance_steps", []),
            "finding_chains": session_data.get("finding_chains", []),
            "metadata": session_data.get("metadata", {}),
            "exported_at": _now_iso(),
        }
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, default=str))
        logger.info("Exported JSON stub: %s", output_path)
        return output_path
