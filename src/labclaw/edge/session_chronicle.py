"""Session chronicle — assembles detected files into session records.

Spec: docs/specs/L3-engine.md (Session Chronicle section)
Design doc: section 5.1 (Session Chronicle)

The OBSERVE step of the scientific method: raw data flows in,
sessions are assembled, and records are written to memory.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from labclaw.core.events import event_registry
from labclaw.core.graph import RecordingNode, SessionNode
from labclaw.core.schemas import FileReference
from labclaw.memory.markdown import TierABackend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events at module import time
# ---------------------------------------------------------------------------

_EVENTS = [
    "session.chronicle.started",
    "session.recording.added",
    "session.chronicle.ended",
]

for _evt in _EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Session chronicle
# ---------------------------------------------------------------------------


class SessionChronicle:
    """Assembles detected files into session records and writes to memory."""

    def __init__(
        self,
        memory: TierABackend | None = None,
        max_sessions: int = 10_000,
    ) -> None:
        self._memory = memory
        self._max_sessions = max_sessions
        self._sessions: dict[str, SessionNode] = {}
        self._recordings: dict[str, list[RecordingNode]] = {}

    def start_session(
        self,
        operator_id: str | None = None,
        experiment_id: str | None = None,
    ) -> SessionNode:
        """Start a new recording session.

        Args:
            operator_id: Who is running the session.
            experiment_id: Which experiment this belongs to.

        Returns:
            The created SessionNode.
        """
        if len(self._sessions) >= self._max_sessions:
            # Evict oldest completed session, or oldest overall
            evict_id = None
            for sid, snode in list(self._sessions.items()):
                if snode.duration_seconds is not None:
                    evict_id = sid
                    break
            if evict_id is None:
                evict_id = min(self._sessions,
                               key=lambda s: self._sessions[s].session_date)
            del self._sessions[evict_id]
            self._recordings.pop(evict_id, None)

        session = SessionNode(
            session_date=datetime.now(UTC),
            operator_id=operator_id,
            experiment_id=experiment_id,
        )

        self._sessions[session.node_id] = session
        self._recordings[session.node_id] = []

        event_registry.emit(
            "session.chronicle.started",
            payload={
                "session_id": session.node_id,
                "operator_id": operator_id,
                "experiment_id": experiment_id,
                "started_at": session.session_date.isoformat(),
            },
        )

        logger.info(
            "Session started: %s (operator=%s, experiment=%s)",
            session.node_id,
            operator_id,
            experiment_id,
        )
        return session

    def add_recording(
        self,
        session_id: str,
        file_ref: FileReference,
        modality: str,
        device_id: str | None = None,
    ) -> RecordingNode:
        """Add a recording (data file) to an existing session.

        Args:
            session_id: The session to add to.
            file_ref: Reference to the data file.
            modality: Type of recording (video, ephys, calcium_imaging, etc.).
            device_id: Which device produced the recording.

        Returns:
            The created RecordingNode.
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id!r} not found")

        recording = RecordingNode(
            session_id=session_id,
            file=file_ref,
            modality=modality,
            device_id=device_id,
        )

        self._recordings[session_id].append(recording)

        event_registry.emit(
            "session.recording.added",
            payload={
                "session_id": session_id,
                "recording_id": recording.node_id,
                "modality": modality,
                "path": str(file_ref.path),
                "device_id": device_id,
            },
        )

        logger.info(
            "Recording added to session %s: %s (%s)",
            session_id,
            file_ref.path,
            modality,
        )
        return recording

    def end_session(self, session_id: str) -> SessionNode:
        """End a session and compute its duration.

        Args:
            session_id: The session to end.

        Returns:
            The updated SessionNode with duration filled in.
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id!r} not found")

        session = self._sessions[session_id]

        # Idempotency: if already ended, return as-is
        if session.duration_seconds is not None:
            return session

        now = datetime.now(UTC)
        duration = (now - session.session_date).total_seconds()
        session.duration_seconds = duration
        session.updated_at = now

        event_registry.emit(
            "session.chronicle.ended",
            payload={
                "session_id": session_id,
                "duration_seconds": duration,
                "recording_count": len(self._recordings[session_id]),
                "ended_at": now.isoformat(),
            },
        )

        logger.info(
            "Session ended: %s (duration=%.1fs, recordings=%d)",
            session_id,
            duration,
            len(self._recordings[session_id]),
        )
        return session

    def get_session(self, session_id: str) -> SessionNode:
        """Retrieve a session by ID.

        Raises KeyError if not found.
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id!r} not found")
        return self._sessions[session_id]

    def get_recordings(self, session_id: str) -> list[RecordingNode]:
        """Retrieve all recordings for a session."""
        if session_id not in self._recordings:
            raise KeyError(f"Session {session_id!r} not found")
        return list(self._recordings[session_id])

    def list_sessions(self) -> list[SessionNode]:
        """Return all sessions (active and ended)."""
        return list(self._sessions.values())
