"""Step definitions for API security BDD tests.

Covers: authentication, CORS, rate limiting, exception sanitization,
and governance integration via the enforce_request_security dependency.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, then, when

from labclaw.api.app import app
from labclaw.api.deps import reset_all


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sec_client() -> TestClient:
    """Fresh TestClient with reset singletons and security env cleared."""
    reset_all()
    yield TestClient(app, raise_server_exceptions=False)
    reset_all()


@pytest.fixture()
def sec_context() -> dict:
    """Shared mutable state across steps within one scenario."""
    return {}


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("the security test client is initialized", target_fixture="sec_client")
def _given_sec_client(sec_context: dict) -> TestClient:
    sec_context.clear()
    reset_all()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Given: environment configuration
# ---------------------------------------------------------------------------


@given("authentication is required", target_fixture="sec_client")
def _given_auth_required(monkeypatch: pytest.MonkeyPatch, sec_context: dict) -> TestClient:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "1")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "0")
    reset_all()
    return TestClient(app, raise_server_exceptions=False)


@given(
    parsers.parse('authentication is required with token "{token}"'),
    target_fixture="sec_client",
)
def _given_auth_with_token(
    token: str,
    monkeypatch: pytest.MonkeyPatch,
    sec_context: dict,
) -> TestClient:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "1")
    monkeypatch.setenv("LABCLAW_API_TOKEN", token)
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "0")
    reset_all()
    return TestClient(app, raise_server_exceptions=False)


@given(
    "authentication is required and no tokens are configured",
    target_fixture="sec_client",
)
def _given_auth_no_tokens(
    monkeypatch: pytest.MonkeyPatch,
    sec_context: dict,
) -> TestClient:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "1")
    monkeypatch.delenv("LABCLAW_API_TOKEN", raising=False)
    monkeypatch.delenv("LABCLAW_API_TOKENS", raising=False)
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "0")
    reset_all()
    return TestClient(app, raise_server_exceptions=False)


@given(
    parsers.parse('CORS is configured with origin "{origin}"'),
    target_fixture="sec_client",
)
def _given_cors_origin(
    origin: str,
    monkeypatch: pytest.MonkeyPatch,
    sec_context: dict,
) -> TestClient:
    monkeypatch.setenv("LABCLAW_CORS_ALLOWED_ORIGINS", origin)
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "0")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "0")
    reset_all()
    # Rebuild a fresh FastAPI app that reads the updated env var at creation time.
    import importlib
    import sys

    app_module = sys.modules["labclaw.api.app"]
    importlib.reload(app_module)
    sec_context["reloaded_app"] = app_module.app
    return TestClient(app_module.app, raise_server_exceptions=False)


@given("no CORS origins are configured", target_fixture="sec_client")
def _given_no_cors(
    monkeypatch: pytest.MonkeyPatch,
    sec_context: dict,
) -> TestClient:
    monkeypatch.setenv("LABCLAW_CORS_ALLOWED_ORIGINS", "")
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "0")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "0")
    reset_all()
    return TestClient(app, raise_server_exceptions=False)


@given(
    parsers.parse("rate limiting is enabled with a limit of {limit:d} per minute"),
    target_fixture="sec_client",
)
def _given_rate_limit(
    limit: int,
    monkeypatch: pytest.MonkeyPatch,
    sec_context: dict,
) -> TestClient:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "0")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_PER_MINUTE", str(limit))
    reset_all()
    return TestClient(app, raise_server_exceptions=False)


@given("the orchestrator is configured to raise an unexpected error", target_fixture="sec_client")
def _given_orchestrator_error(
    monkeypatch: pytest.MonkeyPatch,
    sec_context: dict,
) -> TestClient:
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "0")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "0")
    reset_all()
    sec_context["patch_orchestrator"] = True
    return TestClient(app, raise_server_exceptions=False)


@given("governance enforcement is enabled")
def _given_governance_on(monkeypatch: pytest.MonkeyPatch, sec_client: TestClient) -> None:
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "1")
    reset_all()


@given(parsers.parse('the default role is "{role}"'))
def _given_default_role(
    role: str,
    monkeypatch: pytest.MonkeyPatch,
    sec_client: TestClient,
) -> None:
    monkeypatch.setenv("LABCLAW_API_DEFAULT_ROLE", role)
    reset_all()


# ---------------------------------------------------------------------------
# When: HTTP calls
# ---------------------------------------------------------------------------


@when("I GET the health endpoint without credentials", target_fixture="response")
def _when_get_health(sec_client: TestClient, sec_context: dict):
    resp = sec_client.get("/api/health")
    sec_context["response"] = resp
    return resp


@when("I GET the metrics endpoint without credentials", target_fixture="response")
def _when_get_metrics(sec_client: TestClient, sec_context: dict):
    resp = sec_client.get("/api/metrics")
    sec_context["response"] = resp
    return resp


@when(
    parsers.parse('I GET "{url}" with Bearer token "{token}"'),
    target_fixture="response",
)
def _when_get_bearer(
    sec_client: TestClient,
    url: str,
    token: str,
    sec_context: dict,
):
    resp = sec_client.get(url, headers={"Authorization": f"Bearer {token}"})
    sec_context["response"] = resp
    return resp


@when(
    parsers.parse('I GET "{url}" with X-API-Key header "{key}"'),
    target_fixture="response",
)
def _when_get_api_key(
    sec_client: TestClient,
    url: str,
    key: str,
    sec_context: dict,
):
    resp = sec_client.get(url, headers={"X-API-Key": key})
    sec_context["response"] = resp
    return resp


@when(parsers.parse('I GET "{url}" without any credentials'), target_fixture="response")
def _when_get_no_creds(sec_client: TestClient, url: str, sec_context: dict):
    resp = sec_client.get(url)
    sec_context["response"] = resp
    return resp


@when(
    parsers.parse('I send an OPTIONS preflight request to "{url}" from "{origin}"'),
    target_fixture="response",
)
def _when_options_preflight(
    sec_client: TestClient,
    url: str,
    origin: str,
    sec_context: dict,
):
    resp = sec_client.options(
        url,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    sec_context["response"] = resp
    return resp


@when(
    parsers.parse('I GET "{url}" from origin "{origin}"'),
    target_fixture="response",
)
def _when_get_with_origin(
    sec_client: TestClient,
    url: str,
    origin: str,
    sec_context: dict,
):
    resp = sec_client.get(url, headers={"Origin": origin})
    sec_context["response"] = resp
    return resp


@when(
    parsers.parse('I make {n:d} requests to "{url}"'),
    target_fixture="response",
)
def _when_make_n_requests(
    sec_client: TestClient,
    n: int,
    url: str,
    sec_context: dict,
):
    responses = [sec_client.get(url) for _ in range(n)]
    sec_context["all_responses"] = responses
    sec_context["response"] = responses[-1]
    return responses[-1]


@when("I POST \"/api/orchestrator/cycle\" with empty data rows", target_fixture="response")
def _when_post_orchestrator_error(
    sec_client: TestClient,
    sec_context: dict,
):
    with patch(
        "labclaw.orchestrator.loop.ScientificLoop.run_cycle",
        new=AsyncMock(side_effect=RuntimeError("internal loop crashed")),
    ):
        resp = sec_client.post("/api/orchestrator/cycle", json={"data_rows": []})
    sec_context["response"] = resp
    return resp


@when(
    parsers.parse(
        'I POST "/api/sessions/" with operator "{operator}" and Bearer token "{token}"'
    ),
    target_fixture="response",
)
def _when_post_session_bearer(
    sec_client: TestClient,
    operator: str,
    token: str,
    sec_context: dict,
):
    reset_all()
    resp = sec_client.post(
        "/api/sessions/",
        json={"operator": operator},
        headers={"Authorization": f"Bearer {token}"},
    )
    sec_context["response"] = resp
    return resp


@when(
    parsers.parse(
        'I POST "/api/sessions/" with operator "{operator}" as role "{role}" with Bearer token "{token}"'
    ),
    target_fixture="response",
)
def _when_post_session_with_role(
    sec_client: TestClient,
    operator: str,
    role: str,
    token: str,
    sec_context: dict,
):
    reset_all()
    resp = sec_client.post(
        "/api/sessions/",
        json={"operator": operator},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Labclaw-Role": role,
            "X-Labclaw-Actor": operator,
        },
    )
    sec_context["response"] = resp
    return resp


# ---------------------------------------------------------------------------
# Then: assertions
# ---------------------------------------------------------------------------


@then(parsers.parse("the response status is {code:d}"))
def _then_sec_status(response, code: int, sec_context: dict) -> None:
    resp = sec_context.get("response", response)
    assert resp.status_code == code, (
        f"Expected {code}, got {resp.status_code}: {resp.text}"
    )


@then("the response includes an Access-Control-Allow-Origin header")
def _then_has_cors_header(response, sec_context: dict) -> None:
    resp = sec_context.get("response", response)
    assert "access-control-allow-origin" in resp.headers, (
        f"Expected CORS header in: {dict(resp.headers)}"
    )


@then("the response has no Access-Control-Allow-Origin header")
def _then_no_cors_header(response, sec_context: dict) -> None:
    resp = sec_context.get("response", response)
    assert "access-control-allow-origin" not in resp.headers, (
        f"Unexpected CORS header in: {dict(resp.headers)}"
    )


@then("all requests succeed with status 200")
def _then_all_200(sec_context: dict) -> None:
    responses = sec_context.get("all_responses", [])
    for i, resp in enumerate(responses):
        assert resp.status_code == 200, (
            f"Request {i + 1} expected 200, got {resp.status_code}: {resp.text}"
        )


@then(parsers.parse("the third request returns status {code:d}"))
def _then_third_request_status(code: int, sec_context: dict) -> None:
    responses = sec_context.get("all_responses", [])
    assert len(responses) >= 3, f"Expected at least 3 responses, got {len(responses)}"
    resp = responses[2]
    assert resp.status_code == code, (
        f"Expected {code} on third request, got {resp.status_code}: {resp.text}"
    )


@then(parsers.parse('the response detail is "{detail}"'))
def _then_detail(response, detail: str, sec_context: dict) -> None:
    resp = sec_context.get("response", response)
    body = resp.json()
    assert body.get("detail") == detail, (
        f"Expected detail={detail!r}, got: {body}"
    )


@then("the response detail does not contain internal error information")
def _then_no_internal_info(response, sec_context: dict) -> None:
    resp = sec_context.get("response", response)
    text = resp.text
    for leak in ("Traceback", "loop crashed", "RuntimeError", "Exception"):
        assert leak not in text, f"Found internal info {leak!r} in response: {text[:300]}"
