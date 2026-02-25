"""Session chronicle endpoints — start, record, end sessions."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from labclaw.api.deps import get_data_dir, get_session_chronicle
from labclaw.core.graph import RecordingNode, SessionNode
from labclaw.core.schemas import FileReference
from labclaw.edge.session_chronicle import SessionChronicle

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SessionStartRequest(BaseModel):
    operator: str | None = None
    experiment_id: str | None = None


class RecordingAddRequest(BaseModel):
    file_path: str
    modality: str
    device_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
def list_sessions(
    chronicle: SessionChronicle = Depends(get_session_chronicle),
) -> list[SessionNode]:
    return chronicle.list_sessions()


@router.get("/{session_id}")
def get_session(
    session_id: str,
    chronicle: SessionChronicle = Depends(get_session_chronicle),
) -> SessionNode:
    try:
        return chronicle.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")


@router.post("/", status_code=201)
def start_session(
    body: SessionStartRequest,
    chronicle: SessionChronicle = Depends(get_session_chronicle),
) -> SessionNode:
    return chronicle.start_session(
        operator_id=body.operator,
        experiment_id=body.experiment_id,
    )


@router.post("/{session_id}/recordings", status_code=201)
def add_recording(
    session_id: str,
    body: RecordingAddRequest,
    chronicle: SessionChronicle = Depends(get_session_chronicle),
) -> RecordingNode:
    data_dir = get_data_dir()
    resolved = Path(body.file_path).resolve()
    if not resolved.is_relative_to(data_dir.resolve()):
        raise HTTPException(status_code=400, detail="Path outside data directory")
    if not resolved.is_file():
        raise HTTPException(status_code=400, detail="Recording file does not exist")
    file_ref = FileReference(path=resolved)
    try:
        return chronicle.add_recording(
            session_id=session_id,
            file_ref=file_ref,
            modality=body.modality,
            device_id=body.device_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")


@router.post("/{session_id}/end")
def end_session(
    session_id: str,
    chronicle: SessionChronicle = Depends(get_session_chronicle),
) -> SessionNode:
    try:
        return chronicle.end_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
