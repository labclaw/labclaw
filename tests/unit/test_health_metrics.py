"""Tests for health, metrics, and request logging middleware."""

from __future__ import annotations

import logging
import re
import time

from fastapi.testclient import TestClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all, set_data_dir, set_memory_root


def _client(tmp_path):
    """Return a TestClient with memory_root and data_dir pointed at tmp_path."""
    reset_all()
    memory_root = tmp_path / "memory"
    data_dir = tmp_path / "data"
    memory_root.mkdir()
    data_dir.mkdir()
    set_memory_root(memory_root)
    set_data_dir(data_dir)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_returns_200_with_correct_structure(tmp_path):
    client = _client(tmp_path)
    try:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("healthy", "degraded", "unhealthy")
        assert "components" in body
        for key in ("memory", "data", "event_bus", "evolution"):
            assert key in body["components"]
            assert "status" in body["components"][key]
        assert "version" in body
        assert isinstance(body["uptime_seconds"], (int, float))
        assert body["uptime_seconds"] >= 0
    finally:
        reset_all()


def test_health_degraded_when_memory_root_missing(tmp_path):
    reset_all()
    # Point memory_root at a path that does not exist
    missing = tmp_path / "does_not_exist"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    set_memory_root(missing)
    set_data_dir(data_dir)
    client = TestClient(app)
    try:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["components"]["memory"]["status"] == "degraded"
    finally:
        reset_all()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_metrics_returns_valid_prometheus_format(tmp_path):
    client = _client(tmp_path)
    try:
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        text = resp.text

        # Every metric line should be a HELP, TYPE, or value line
        for line in text.strip().splitlines():
            assert (
                line.startswith("# HELP")
                or line.startswith("# TYPE")
                or re.match(r"^labclaw_\w+", line)
            ), f"Unexpected line: {line!r}"
    finally:
        reset_all()


def test_metrics_values_are_non_negative(tmp_path):
    client = _client(tmp_path)
    try:
        resp = client.get("/api/metrics")
        text = resp.text
        for line in text.strip().splitlines():
            if line.startswith("#"):
                continue
            # Extract numeric value (last token, may have labels before it)
            parts = line.split()
            value = float(parts[-1])
            assert value >= 0, f"Negative metric value in: {line!r}"
    finally:
        reset_all()


def test_uptime_increases_over_time(tmp_path):
    client = _client(tmp_path)
    try:
        resp1 = client.get("/api/health")
        t1 = resp1.json()["uptime_seconds"]
        time.sleep(0.05)
        resp2 = client.get("/api/health")
        t2 = resp2.json()["uptime_seconds"]
        assert t2 > t1
    finally:
        reset_all()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


def test_request_logging_middleware_logs(tmp_path, caplog):
    client = _client(tmp_path)
    try:
        with caplog.at_level(logging.INFO, logger="labclaw.api"):
            client.get("/api/health")
        assert any(
            "GET" in rec.message and "/api/health" in rec.message and "200" in rec.message
            for rec in caplog.records
        ), f"Expected log line with GET /api/health 200, got: {[r.message for r in caplog.records]}"
    finally:
        reset_all()
