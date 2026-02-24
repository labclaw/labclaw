from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from labclaw.api.app import app
from labclaw.api.deps import (
    get_session_chronicle,
    get_tier_a_backend,
    reset_all,
    set_memory_root,
)
from labclaw.core.events import event_registry


def _ensure_memory_events() -> None:
    for name in ("memory.tier_a.created", "memory.tier_a.updated", "memory.search.executed"):
        if not event_registry.is_registered(name):
            event_registry.register(name)


def test_memory_api_rejects_invalid_entity_id_on_append(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.post("/api/memory/bad*id/memory", json={"category": "x", "detail": "y"})
        assert resp.status_code == 400
        assert "entity_id" in resp.json()["detail"]
    finally:
        reset_all()


def test_memory_api_rejects_invalid_entity_id_on_read(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.get("/api/memory/bad*id/soul")
        assert resp.status_code == 400
        assert "entity_id" in resp.json()["detail"]
    finally:
        reset_all()


def test_memory_api_rejects_invalid_entity_id_on_memory_read(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.get("/api/memory/bad*id/memory")
        assert resp.status_code == 400
        assert "entity_id" in resp.json()["detail"]
    finally:
        reset_all()


def test_memory_api_append_valid_entity_id_still_works(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.post("/api/memory/lab_001/memory", json={"category": "x", "detail": "y"})
        assert resp.status_code == 201
        assert resp.json()["entity_id"] == "lab_001"
    finally:
        reset_all()


def test_set_memory_root_clears_chronicle_and_backend_cache(tmp_path: Path) -> None:
    reset_all()
    try:
        first_root = tmp_path / "memory-a"
        second_root = tmp_path / "memory-b"

        set_memory_root(first_root)
        first_backend = get_tier_a_backend()
        first_chronicle = get_session_chronicle()

        set_memory_root(second_root)
        second_backend = get_tier_a_backend()
        second_chronicle = get_session_chronicle()

        assert first_backend is not second_backend
        assert first_chronicle is not second_chronicle
        assert second_backend.root == second_root
        assert second_chronicle._memory is second_backend
    finally:
        reset_all()


def test_memory_api_rejects_invalid_search_limit(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.get("/api/memory/search/query?q=test&limit=0")
        assert resp.status_code == 422
        assert "greater than or equal to 1" in resp.text
    finally:
        reset_all()
