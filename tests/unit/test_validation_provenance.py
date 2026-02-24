from __future__ import annotations

import pytest

from labclaw.validation.provenance import ProvenanceTracker, from_dict, to_dict
from labclaw.validation.statistics import ProvenanceChain, ProvenanceStep

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_steps(count: int = 2) -> list[ProvenanceStep]:
    return [
        ProvenanceStep(
            node_id=f"node-{i}",
            node_type="DataNode",
            description=f"Step {i}",
        )
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# ProvenanceTracker.build_chain
# ---------------------------------------------------------------------------


def test_build_chain_returns_chain_with_correct_finding_id() -> None:
    tracker = ProvenanceTracker()
    steps = _make_steps(3)
    chain = tracker.build_chain("find-001", steps)

    assert chain.finding_id == "find-001"
    assert len(chain.steps) == 3
    assert chain.chain_id != ""


def test_build_chain_empty_steps_raises() -> None:
    tracker = ProvenanceTracker()
    with pytest.raises(ValueError, match="at least one step"):
        tracker.build_chain("find-001", [])


# ---------------------------------------------------------------------------
# ProvenanceTracker.verify_chain
# ---------------------------------------------------------------------------


def test_verify_chain_valid_returns_true() -> None:
    tracker = ProvenanceTracker()
    chain = tracker.build_chain("find-001", _make_steps(2))

    assert tracker.verify_chain(chain) is True


def test_verify_chain_empty_finding_id_returns_false() -> None:
    tracker = ProvenanceTracker()
    chain = ProvenanceChain(finding_id="", steps=_make_steps(1))

    assert tracker.verify_chain(chain) is False


def test_verify_chain_no_steps_returns_false() -> None:
    tracker = ProvenanceTracker()
    chain = ProvenanceChain(finding_id="find-001", steps=[])

    assert tracker.verify_chain(chain) is False


def test_verify_chain_step_empty_node_id_returns_false() -> None:
    tracker = ProvenanceTracker()
    bad_step = ProvenanceStep(node_id="", node_type="DataNode", description="x")
    chain = ProvenanceChain(finding_id="find-001", steps=[bad_step])

    assert tracker.verify_chain(chain) is False


def test_verify_chain_step_empty_node_type_returns_false() -> None:
    tracker = ProvenanceTracker()
    bad_step = ProvenanceStep(node_id="node-1", node_type="", description="x")
    chain = ProvenanceChain(finding_id="find-001", steps=[bad_step])

    assert tracker.verify_chain(chain) is False


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


def test_to_dict_from_dict_round_trip() -> None:
    import json

    tracker = ProvenanceTracker()
    steps = _make_steps(3)
    original = tracker.build_chain("find-rt-01", steps)

    serialized = to_dict(original)

    # Verify JSON-safe (no datetime, UUID objects)
    json.dumps(serialized)

    restored = from_dict(serialized)

    assert restored.finding_id == original.finding_id
    assert restored.chain_id == original.chain_id
    assert len(restored.steps) == len(original.steps)
    for orig_step, rest_step in zip(original.steps, restored.steps):
        assert rest_step.node_id == orig_step.node_id
        assert rest_step.node_type == orig_step.node_type
        assert rest_step.description == orig_step.description
