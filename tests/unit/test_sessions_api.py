from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all, set_memory_root


def test_add_recording_rejects_missing_file(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    memory_root = tmp_path / "memory"
    monkeypatch.setenv("LABCLAW_DATA_DIR", str(data_dir))

    reset_all()
    try:
        set_memory_root(memory_root)
        client = TestClient(app)

        session_resp = client.post("/api/sessions/", json={"operator": "robot"})
        session_id = session_resp.json()["node_id"]

        missing_path = data_dir / "missing.csv"
        resp = client.post(
            f"/api/sessions/{session_id}/recordings",
            json={
                "file_path": str(missing_path),
                "modality": "behavioral_csv",
                "device_id": "rig-01",
            },
        )
        assert resp.status_code == 400
        assert "does not exist" in resp.json()["detail"]
    finally:
        reset_all()
