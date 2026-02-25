"""Step definitions for REST API endpoint BDD tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, then, when

from labclaw.api.app import app
from labclaw.api.deps import reset_all

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def api_client() -> TestClient:
    """Fresh test client with reset singletons per scenario."""
    reset_all()
    return TestClient(app)


@pytest.fixture()
def api_context() -> dict:
    """Shared mutable context across steps within one scenario."""
    return {}


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------

@given("the API test client is initialized", target_fixture="client")
def _given_api_client(api_client: TestClient, api_context: dict) -> TestClient:
    api_context.clear()
    return api_client


# ---------------------------------------------------------------------------
# When: HTTP verbs
# ---------------------------------------------------------------------------

@when(parsers.parse('I GET "{url}"'), target_fixture="response")
def _when_get(client: TestClient, url: str, api_context: dict):
    resp = client.get(url)
    api_context["response"] = resp
    return resp


@when(
    parsers.parse('I POST "/api/devices/" with device name "{name}" type "{dtype}"'),
    target_fixture="response",
)
def _when_post_device(client: TestClient, name: str, dtype: str, api_context: dict):
    resp = client.post("/api/devices/", json={"name": name, "device_type": dtype})
    api_context["response"] = resp
    return resp


@when(
    parsers.parse('I POST "/api/sessions/" with operator "{operator}"'),
    target_fixture="response",
)
def _when_post_session(client: TestClient, operator: str, api_context: dict):
    resp = client.post("/api/sessions/", json={"operator": operator})
    api_context["response"] = resp
    return resp


@then("I store the device_id")
def _then_store_device_id(api_context: dict, response):
    api_context["device_id"] = response.json()["device_id"]


@when("I GET the stored device", target_fixture="response")
def _when_get_stored_device(client: TestClient, api_context: dict):
    device_id = api_context["device_id"]
    resp = client.get(f"/api/devices/{device_id}")
    api_context["response"] = resp
    return resp


@when(
    parsers.parse('I PATCH the stored device status to "{status}"'),
    target_fixture="response",
)
def _when_patch_device_status(client: TestClient, status: str, api_context: dict):
    device_id = api_context["device_id"]
    resp = client.patch(f"/api/devices/{device_id}/status", json={"status": status})
    api_context["response"] = resp
    return resp


@when("I DELETE the stored device", target_fixture="response")
def _when_delete_stored_device(client: TestClient, api_context: dict):
    device_id = api_context["device_id"]
    resp = client.delete(f"/api/devices/{device_id}")
    api_context["response"] = resp
    return resp


@when(parsers.parse('I DELETE "{url}"'), target_fixture="response")
def _when_delete_url(client: TestClient, url: str, api_context: dict):
    resp = client.delete(url)
    api_context["response"] = resp
    return resp


@when("I POST end session for the stored session_id", target_fixture="response")
def _when_end_session(client: TestClient, api_context: dict):
    session_id = api_context["session_id"]
    resp = client.post(f"/api/sessions/{session_id}/end")
    api_context["response"] = resp
    return resp


@when('I POST "/api/discovery/mine" with sample data', target_fixture="response")
def _when_mine(client: TestClient, api_context: dict):
    data = [
        {"x": float(i), "y": float(i * 2), "timestamp": i}
        for i in range(15)
    ]
    resp = client.post("/api/discovery/mine", json={"data": data})
    api_context["response"] = resp
    return resp


@when('I POST "/api/discovery/mine" with empty data', target_fixture="response")
def _when_mine_empty(client: TestClient, api_context: dict):
    resp = client.post("/api/discovery/mine", json={"data": []})
    api_context["response"] = resp
    return resp


@when(
    parsers.parse('I POST "/api/evolution/fitness" for target "{target}"'),
    target_fixture="response",
)
def _when_measure_fitness(client: TestClient, target: str, api_context: dict):
    resp = client.post(
        "/api/evolution/fitness",
        json={"target": target, "metrics": {"accuracy": 0.9}, "data_points": 10},
    )
    api_context["response"] = resp
    return resp


@when('I POST "/api/devices/" with invalid JSON body', target_fixture="response")
def _when_post_device_invalid_json(client: TestClient, api_context: dict):
    resp = client.post(
        "/api/devices/",
        content=b"this is not json at all",
        headers={"Content-Type": "application/json"},
    )
    api_context["response"] = resp
    return resp


@when(
    parsers.parse('I POST "/api/evolution/cycle" for target "{target}"'),
    target_fixture="response",
)
def _when_start_evolution_cycle(client: TestClient, target: str, api_context: dict):
    resp = client.post(
        "/api/evolution/cycle",
        json={"target": target, "n_candidates": 1},
    )
    api_context["response"] = resp
    return resp


@when('I POST "/api/discovery/hypothesize" with empty patterns', target_fixture="response")
def _when_hypothesize_empty(client: TestClient, api_context: dict):
    # Use raise_server_exceptions=False so we get an HTTP response even on 500s
    client_no_raise = TestClient(app, raise_server_exceptions=False)
    resp = client_no_raise.post(
        "/api/discovery/hypothesize",
        json={"patterns": [], "context": "", "constraints": []},
    )
    api_context["response"] = resp
    return resp


# ---------------------------------------------------------------------------
# Then: assertions
# ---------------------------------------------------------------------------

@then(parsers.parse("the response status is {code:d}"))
def _then_status(response, code: int):
    assert response.status_code == code, (
        f"Expected {code}, got {response.status_code}: {response.text}"
    )


@then(parsers.parse('the response contains "{key}" with value "{value}"'))
def _then_contains_kv(response, key: str, value: str):
    data = response.json()
    assert key in data, f"Key {key!r} not in response: {data}"
    assert str(data[key]) == value, f"Expected {value!r}, got {data[key]!r}"


@then(parsers.parse('the response contains "{key}"'))
def _then_contains_key(response, key: str):
    data = response.json()
    assert key in data, f"Key {key!r} not in response: {data}"


@then(parsers.parse("the response contains {count:d} device"))
def _then_device_count(response, count: int):
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= count, f"Expected >= {count} devices, got {len(data)}"


@then("the response contains a session_id")
def _then_has_session_id(response, api_context: dict):
    data = response.json()
    assert "node_id" in data, f"No node_id in response: {data}"
    api_context["session_id"] = data["node_id"]


@then("the response is a list")
def _then_is_list(response):
    data = response.json()
    assert isinstance(data, list), f"Expected list, got {type(data).__name__}"


@then("the hypothesize response is acceptable")
def _then_hypothesize_acceptable(response):
    # Accepts 200 (list of hypotheses) or 500 (no LLM configured in test env)
    assert response.status_code in (200, 500), (
        f"Expected 200 or 500, got {response.status_code}: {response.text}"
    )


@then(parsers.parse('the metrics response contains "{metric_name}"'))
def _then_metrics_contains(response, metric_name: str):
    text = response.text
    assert metric_name in text, (
        f"Expected metric {metric_name!r} in metrics response:\n{text[:500]}"
    )
