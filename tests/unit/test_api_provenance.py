"""Unit tests — provenance REST API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from labclaw.api.app import app
from labclaw.api.routers import provenance as provenance_module


@pytest.fixture(autouse=True)
def _clear_chains():
    """Reset in-process chain store before each test."""
    provenance_module._chains.clear()
    yield
    provenance_module._chains.clear()


client = TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/v0/provenance/
# ---------------------------------------------------------------------------


def test_create_chain_returns_201() -> None:
    resp = client.post(
        "/api/v0/provenance/",
        json={
            "finding_id": "find-001",
            "steps": [
                {"node_id": "n1", "node_type": "observation", "description": "raw data"},
                {"node_id": "n2", "node_type": "conclusion", "description": "finding"},
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["finding_id"] == "find-001"
    assert len(body["steps"]) == 2
    assert body["chain_id"] != ""


def test_create_chain_empty_steps_returns_400() -> None:
    resp = client.post(
        "/api/v0/provenance/",
        json={"finding_id": "find-002", "steps": []},
    )
    assert resp.status_code == 400
    assert "at least one step" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/v0/provenance/{finding_id}
# ---------------------------------------------------------------------------


def test_get_chain_returns_200() -> None:
    # Create first
    client.post(
        "/api/v0/provenance/",
        json={
            "finding_id": "find-get",
            "steps": [{"node_id": "n1", "node_type": "obs", "description": "d"}],
        },
    )
    resp = client.get("/api/v0/provenance/find-get")
    assert resp.status_code == 200
    assert resp.json()["finding_id"] == "find-get"


def test_get_chain_not_found_returns_404() -> None:
    resp = client.get("/api/v0/provenance/no-such-finding")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Legacy prefix /api/provenance/
# ---------------------------------------------------------------------------


def test_legacy_prefix_create_returns_201() -> None:
    resp = client.post(
        "/api/provenance/",
        json={
            "finding_id": "legacy-001",
            "steps": [{"node_id": "n1", "node_type": "obs", "description": "d"}],
        },
    )
    assert resp.status_code == 201


def test_legacy_prefix_get_returns_200() -> None:
    provenance_module._chains.clear()
    client.post(
        "/api/provenance/",
        json={
            "finding_id": "legacy-002",
            "steps": [{"node_id": "n1", "node_type": "obs", "description": "d"}],
        },
    )
    resp = client.get("/api/provenance/legacy-002")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Multiple steps are preserved
# ---------------------------------------------------------------------------


def test_chain_preserves_all_steps() -> None:
    steps = [
        {"node_id": f"n{i}", "node_type": "stage", "description": f"step {i}"}
        for i in range(5)
    ]
    resp = client.post(
        "/api/v0/provenance/",
        json={"finding_id": "find-multi", "steps": steps},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["steps"]) == 5
