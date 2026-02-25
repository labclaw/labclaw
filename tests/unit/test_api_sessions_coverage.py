"""Coverage tests for src/labclaw/api/routers/sessions.py.

List, get, recording, and end-session paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all, set_data_dir, set_memory_root


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Return a TestClient with isolated data and memory dirs."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    memory_root = tmp_path / "memory"
    memory_root.mkdir()

    reset_all()
    set_memory_root(memory_root)
    set_data_dir(data_dir)

    yield TestClient(app), data_dir

    reset_all()


# ---------------------------------------------------------------------------
# list_sessions — Line 41: GET /api/sessions/
# ---------------------------------------------------------------------------


class TestListSessions:
    def test_list_sessions_empty(self, client: tuple[TestClient, Path]) -> None:
        tc, _ = client
        resp = tc.get("/api/sessions/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions_after_create(self, client: tuple[TestClient, Path]) -> None:
        tc, _ = client
        tc.post("/api/sessions/", json={"operator": "eve"})
        resp = tc.get("/api/sessions/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# get_session — Lines 49-52: GET /api/sessions/{session_id}
# ---------------------------------------------------------------------------


class TestGetSession:
    def test_get_existing_session(self, client: tuple[TestClient, Path]) -> None:
        tc, _ = client
        created = tc.post("/api/sessions/", json={"operator": "frank"})
        session_id = created.json()["node_id"]
        resp = tc.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["node_id"] == session_id

    def test_get_unknown_session_returns_404(self, client: tuple[TestClient, Path]) -> None:
        tc, _ = client
        resp = tc.get("/api/sessions/no-such-id")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# add_recording — Line 75: valid path, file exists → 201
# ---------------------------------------------------------------------------


class TestAddRecordingValid:
    def test_valid_file_added(self, client: tuple[TestClient, Path]) -> None:
        tc, data_dir = client

        # Create a real file inside data_dir
        rec_file = data_dir / "session.csv"
        rec_file.write_text("col1,col2\n1,2\n")

        # Start a session
        resp = tc.post("/api/sessions/", json={"operator": "alice"})
        assert resp.status_code == 201
        session_id = resp.json()["node_id"]

        # Add the recording — file exists and is inside data_dir
        resp = tc.post(
            f"/api/sessions/{session_id}/recordings",
            json={
                "file_path": str(rec_file),
                "modality": "behavioral_csv",
                "device_id": "rig-01",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["modality"] == "behavioral_csv"


# ---------------------------------------------------------------------------
# add_recording — Lines 78-87: path outside data_dir → 400
# ---------------------------------------------------------------------------


class TestAddRecordingPathOutsideDataDir:
    def test_rejects_path_outside_data_dir(
        self, client: tuple[TestClient, Path], tmp_path: Path
    ) -> None:
        tc, data_dir = client

        # File exists but is outside data_dir
        outside_file = tmp_path / "secret.csv"
        outside_file.write_text("data")

        resp = tc.post("/api/sessions/", json={"operator": "bob"})
        session_id = resp.json()["node_id"]

        resp = tc.post(
            f"/api/sessions/{session_id}/recordings",
            json={
                "file_path": str(outside_file),
                "modality": "video",
            },
        )
        assert resp.status_code == 400
        assert "outside data directory" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# add_recording — file does not exist → 400
# ---------------------------------------------------------------------------


class TestAddRecordingFileMissing:
    def test_rejects_nonexistent_file(self, client: tuple[TestClient, Path]) -> None:
        tc, data_dir = client

        missing = data_dir / "ghost.mp4"

        resp = tc.post("/api/sessions/", json={"operator": "carol"})
        session_id = resp.json()["node_id"]

        resp = tc.post(
            f"/api/sessions/{session_id}/recordings",
            json={
                "file_path": str(missing),
                "modality": "video",
            },
        )
        assert resp.status_code == 400
        assert "does not exist" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# add_recording — unknown session → 404 (Line 87)
# ---------------------------------------------------------------------------


class TestAddRecordingUnknownSession:
    def test_unknown_session_returns_404(self, client: tuple[TestClient, Path]) -> None:
        tc, data_dir = client

        real_file = data_dir / "data.csv"
        real_file.write_text("a,b\n1,2")

        resp = tc.post(
            "/api/sessions/no-such-session/recordings",
            json={
                "file_path": str(real_file),
                "modality": "behavioral_csv",
            },
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# end_session — Lines 97-98: unknown session → 404
# ---------------------------------------------------------------------------


class TestEndSessionUnknown:
    def test_end_unknown_session_returns_404(self, client: tuple[TestClient, Path]) -> None:
        tc, _ = client
        resp = tc.post("/api/sessions/unknown-xyz/end")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_end_known_session_returns_200(self, client: tuple[TestClient, Path]) -> None:
        tc, _ = client

        # Create and end a session
        resp = tc.post("/api/sessions/", json={"operator": "dave"})
        assert resp.status_code == 201
        session_id = resp.json()["node_id"]

        resp = tc.post(f"/api/sessions/{session_id}/end")
        assert resp.status_code == 200
        body = resp.json()
        assert body["node_id"] == session_id
