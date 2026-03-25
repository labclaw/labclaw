"""Tests for brain core types."""

from __future__ import annotations

from labclaw.brain.types import BrainResult, HealthStatus, ToolInfo


def test_brain_result_success():
    r = BrainResult(success=True, data={"key": "value"})
    assert r.success
    assert r.data == {"key": "value"}
    assert r.error is None


def test_brain_result_failure():
    r = BrainResult(success=False, error="timeout")
    assert not r.success
    assert r.error == "timeout"
    assert r.data is None


def test_brain_result_model_dump():
    r = BrainResult(success=True, data=[1, 2, 3])
    d = r.model_dump()
    assert d == {"success": True, "data": [1, 2, 3], "error": None}


def test_tool_info_defaults():
    t = ToolInfo(name="search_pubmed", description="Search PubMed", skill="tooluniverse")
    assert t.name == "search_pubmed"
    assert t.category == ""
    assert t.parameters == {}


def test_tool_info_full():
    t = ToolInfo(
        name="get_protein",
        description="Get protein",
        skill="tooluniverse",
        category="genomics",
        parameters={"accession": {"type": "string"}},
    )
    assert t.category == "genomics"
    assert "accession" in t.parameters


def test_health_status():
    h = HealthStatus(status="ok", skills={"tooluniverse": True}, tool_count=2000, version="0.0.1")
    assert h.status == "ok"
    assert h.tool_count == 2000


def test_health_status_degraded():
    h = HealthStatus(
        status="degraded",
        skills={"tooluniverse": True, "lifesci": False},
        tool_count=2000,
        version="0.0.1",
    )
    assert h.status == "degraded"
    assert not h.skills["lifesci"]
