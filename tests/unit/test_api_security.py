"""Security behavior tests for API auth, governance, and rate limiting."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all, set_data_dir, set_memory_root


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    memory_root = tmp_path / "lab"
    data_dir = tmp_path / "data"
    memory_root.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    set_memory_root(memory_root)
    set_data_dir(data_dir)
    reset_all()
    try:
        return TestClient(app)
    finally:
        reset_all()


def test_health_endpoint_is_auth_exempt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "1")
    reset_all()
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_protected_endpoint_requires_token_config(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "1")
    monkeypatch.delenv("LABCLAW_API_TOKEN", raising=False)
    monkeypatch.delenv("LABCLAW_API_TOKENS", raising=False)
    reset_all()
    resp = client.get("/api/events/")
    assert resp.status_code == 503


def test_protected_endpoint_rejects_invalid_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "1")
    monkeypatch.setenv("LABCLAW_API_TOKEN", "secret-token")
    reset_all()
    resp = client.get(
        "/api/events/",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_governance_denies_write_without_role_override(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "1")
    monkeypatch.setenv("LABCLAW_API_TOKEN", "secret-token")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "1")
    monkeypatch.delenv("LABCLAW_API_DEFAULT_ROLE", raising=False)
    reset_all()
    resp = client.post(
        "/api/sessions/",
        json={"operator": "robot"},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert resp.status_code == 403


def test_governance_allows_write_for_postdoc(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "1")
    monkeypatch.setenv("LABCLAW_API_TOKEN", "secret-token")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "1")
    reset_all()
    resp = client.post(
        "/api/sessions/",
        json={"operator": "robot"},
        headers={
            "Authorization": "Bearer secret-token",
            "X-Labclaw-Actor": "alice",
            "X-Labclaw-Role": "postdoc",
        },
    )
    assert resp.status_code == 201


def test_rate_limit_enforced(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "0")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_PER_MINUTE", "2")
    reset_all()

    assert client.get("/api/events/").status_code == 200
    assert client.get("/api/events/").status_code == 200
    assert client.get("/api/events/").status_code == 429


def test_rate_limit_window_eviction(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify _rate_limit_window evicts oldest key when exceeding max size."""
    import labclaw.api.deps as deps_mod

    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "0")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_PER_MINUTE", "9999")
    monkeypatch.setattr(deps_mod, "_MAX_RATE_LIMIT_KEYS", 2)
    reset_all()

    # Fill 2 distinct keys
    client.get("/api/events/")
    client.get("/api/devices/")
    # Third distinct key triggers eviction
    client.get("/api/plugins/")

    with deps_mod._rate_limit_lock:
        assert len(deps_mod._rate_limit_window) <= 2
