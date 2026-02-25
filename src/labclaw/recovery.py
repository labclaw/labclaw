"""Crash recovery — atomically saves and restores daemon state between restarts."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class StateRecovery:
    """Recovers daemon state from persistent storage after crash/restart."""

    def __init__(self, memory_root: Path, state_file: Path | None = None) -> None:
        self._memory_root = memory_root
        self._state_file = state_file or memory_root / ".labclaw_state.json"

    @property
    def state_file(self) -> Path:
        return self._state_file

    def save_state(self, state: dict) -> None:
        """Atomically save daemon state to disk."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state, default=str)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self._state_file.parent,
            prefix=f"{self._state_file.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self._state_file)  # atomic on POSIX
        logger.debug("Daemon state saved to %s", self._state_file)

    def load_state(self) -> dict | None:
        """Load last saved state, or None if no state file exists."""
        if not self._state_file.exists():
            return None
        try:
            return json.loads(self._state_file.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning(
                "State file %s is corrupt or unreadable; starting fresh",
                self._state_file,
            )
            return None

    def clear_state(self) -> None:
        """Remove state file."""
        self._state_file.unlink(missing_ok=True)
        logger.debug("Daemon state file cleared: %s", self._state_file)
