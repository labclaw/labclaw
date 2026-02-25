"""Parametrized edge-case tests for LabClaw modules."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from labclaw.core.governance import GovernanceEngine
from labclaw.core.schemas import EvolutionTarget
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.schemas import (
    EvolutionCandidate,
    EvolutionConfig,
    FitnessScore,
)

# ---------------------------------------------------------------------------
# 1. Config: various YAML edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "yaml_content,expect_success",
    [
        # Empty YAML
        ("", True),
        # YAML with extra fields (should be ignored by Pydantic)
        ("system:\n  name: test\n  unknown_field: 42\n", True),
        # YAML with missing fields (defaults apply)
        ("system:\n  name: mylab\n", True),
        # Valid complete YAML
        (
            "system:\n  name: lab\n  version: '1.0'\n  log_level: DEBUG\n"
            "graph:\n  backend: sqlite\n  path: /tmp/test.db\n",
            True,
        ),
        # YAML with wrong type for port (string instead of int)
        ("api:\n  port: not_a_number\n", False),
        # YAML with nested wrong types
        ("edge:\n  poll_interval_seconds: fast\n", False),
    ],
    ids=[
        "empty",
        "extra_fields",
        "missing_fields",
        "valid_complete",
        "wrong_type_port",
        "wrong_type_interval",
    ],
)
def test_config_yaml_edge_cases(yaml_content: str, expect_success: bool) -> None:
    from labclaw.config import LabClawConfig

    tmpdir = Path(tempfile.mkdtemp())
    config_path = tmpdir / "test.yaml"
    config_path.write_text(yaml_content)

    data = yaml.safe_load(config_path.read_text()) or {}
    if expect_success:
        config = LabClawConfig.model_validate(data)
        assert config.system.name  # has a name
    else:
        with pytest.raises(Exception):
            LabClawConfig.model_validate(data)


# ---------------------------------------------------------------------------
# 2. Evolution engine: rollback threshold boundary values
# ---------------------------------------------------------------------------


def _make_fitness(metrics: dict[str, float]) -> FitnessScore:
    return FitnessScore(
        target=EvolutionTarget.ANALYSIS_PARAMS,
        metrics=metrics,
        data_points=100,
    )


def _make_candidate() -> EvolutionCandidate:
    return EvolutionCandidate(
        target=EvolutionTarget.ANALYSIS_PARAMS,
        description="test candidate",
        config_diff={"threshold": 0.5},
    )


@pytest.mark.parametrize(
    "baseline_val,current_val,threshold,should_rollback",
    [
        # Exactly at threshold: drop = 0.1/1.0 = 10%, threshold = 10% → NOT rolled back (not >)
        (1.0, 0.9, 0.1, False),
        # Just above threshold: drop = 0.11/1.0 = 11% > 10% → rolled back
        (1.0, 0.89, 0.1, True),
        # Just below threshold: drop = 0.09/1.0 = 9% < 10% → NOT rolled back
        (1.0, 0.91, 0.1, False),
        # No drop: same value → NOT rolled back
        (1.0, 1.0, 0.1, False),
        # Improvement: current > baseline → NOT rolled back
        (1.0, 1.5, 0.1, False),
        # Zero baseline: skip check → NOT rolled back
        (0.0, 0.5, 0.1, False),
        # Large drop with strict threshold
        (100.0, 50.0, 0.01, True),
        # Tiny threshold: any drop triggers rollback
        (1.0, 0.99, 0.005, True),
    ],
    ids=[
        "exactly_at_threshold",
        "just_above_threshold",
        "just_below_threshold",
        "no_drop",
        "improvement",
        "zero_baseline",
        "large_drop_strict",
        "tiny_threshold",
    ],
)
def test_evolution_rollback_boundaries(
    baseline_val: float,
    current_val: float,
    threshold: float,
    should_rollback: bool,
) -> None:
    config = EvolutionConfig(rollback_threshold=threshold, min_soak_sessions=0)
    engine = EvolutionEngine(config=config)

    baseline = _make_fitness({"accuracy": baseline_val})
    candidate = _make_candidate()
    cycle = engine.start_cycle(candidate, baseline)

    new_fitness = _make_fitness({"accuracy": current_val})

    import time

    time.sleep(0.01)  # Ensure soak time passes

    result = engine.advance_stage(cycle.cycle_id, new_fitness)

    from labclaw.core.schemas import EvolutionStage

    if should_rollback:
        assert result.stage == EvolutionStage.ROLLED_BACK
        assert result.rollback_reason is not None
    else:
        assert result.stage == EvolutionStage.SHADOW  # Advanced from BACKTEST
        assert result.rollback_reason is None


# ---------------------------------------------------------------------------
# 3. Governance: 8 roles × 5 actions matrix
# ---------------------------------------------------------------------------

ALL_ROLES = [
    "pi",
    "postdoc",
    "graduate",
    "undergraduate",
    "technician",
    "digital_intern",
    "digital_analyst",
    "digital_specialist",
]

ALL_ACTIONS = ["read", "write", "execute", "approve", "calibrate"]

# Expected permissions based on GovernanceEngine._role_permissions
_EXPECTED: dict[str, set[str]] = {
    "pi": {"read", "write", "execute", "approve", "calibrate"},  # wildcard
    "postdoc": {"read", "write", "execute", "approve"},
    "graduate": {"read", "write", "execute"},
    "undergraduate": {"read", "write"},
    "technician": {"read", "write", "calibrate"},
    "digital_intern": {"read"},
    "digital_analyst": {"read", "analyze"},
    "digital_specialist": {"read", "analyze", "propose"},
}


@pytest.mark.parametrize("role", ALL_ROLES)
@pytest.mark.parametrize("action", ALL_ACTIONS)
def test_governance_role_action_matrix(role: str, action: str) -> None:
    engine = GovernanceEngine()
    decision = engine.check(
        action=action,
        actor=f"test-{role}",
        role=role,
    )
    expected_allowed = action in _EXPECTED.get(role, set())
    assert decision.allowed == expected_allowed, (
        f"role={role}, action={action}: expected allowed={expected_allowed}, got {decision.allowed}"
    )


# ---------------------------------------------------------------------------
# 4. DataAccumulator: file extension filtering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "suffix,should_ingest",
    [
        (".csv", True),
        (".tsv", True),
        (".txt", True),
        (".json", False),
        (".xlsx", False),
        (".CSV", True),  # Case-insensitive
        (".parquet", False),
        (".py", False),
    ],
    ids=["csv", "tsv", "txt", "json", "xlsx", "CSV_upper", "parquet", "py"],
)
def test_data_accumulator_file_extensions(suffix: str, should_ingest: bool) -> None:
    from labclaw.daemon import DataAccumulator

    acc = DataAccumulator()
    tmpdir = Path(tempfile.mkdtemp())
    p = tmpdir / f"test{suffix}"

    # Write valid CSV content regardless of extension
    p.write_text("x,y\n1,2\n3,4\n")

    result = acc.ingest_file(p)
    if should_ingest:
        assert result > 0, f"Expected ingestion for {suffix}"
    else:
        assert result == 0, f"Expected rejection for {suffix}"


# ---------------------------------------------------------------------------
# 5. Orchestrator steps: various row counts
# ---------------------------------------------------------------------------


def _make_data_rows(n: int) -> list[dict[str, Any]]:
    return [{"x": float(i), "y": float(i * 2), "label": f"row_{i}"} for i in range(n)]


@pytest.mark.parametrize(
    "step_class_name,row_count,expect_skipped",
    [
        ("ObserveStep", 0, True),
        ("ObserveStep", 1, False),
        ("ObserveStep", 5, False),
        ("ObserveStep", 100, False),
        ("AskStep", 0, True),
        ("AskStep", 1, True),  # < 10 rows triggers skip
        ("AskStep", 5, True),
        ("AskStep", 10, False),  # >= 10 rows runs mining
        ("AskStep", 100, False),
    ],
    ids=[
        "observe_0",
        "observe_1",
        "observe_5",
        "observe_100",
        "ask_0",
        "ask_1",
        "ask_5",
        "ask_10",
        "ask_100",
    ],
)
@pytest.mark.asyncio
async def test_orchestrator_steps_row_counts(
    step_class_name: str, row_count: int, expect_skipped: bool
) -> None:
    from labclaw.orchestrator import steps

    step_cls = getattr(steps, step_class_name)
    step = step_cls()

    from labclaw.orchestrator.steps import StepContext

    ctx = StepContext(data_rows=_make_data_rows(row_count))
    result = await step.run(ctx)

    assert result.success
    assert result.skipped == expect_skipped


# ---------------------------------------------------------------------------
# 6. EvolutionConfig boundary values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("min_soak_sessions", 0),
        ("min_soak_sessions", 1),
        ("rollback_threshold", 0.0),
        ("rollback_threshold", 1.0),
        ("max_candidates", 1),
        ("max_candidates", 100),
        ("max_cycles", 1),
    ],
    ids=[
        "min_soak_0",
        "min_soak_1",
        "threshold_0",
        "threshold_1",
        "max_cand_1",
        "max_cand_100",
        "max_cycles_1",
    ],
)
def test_evolution_config_boundaries(field: str, value: int | float) -> None:
    config = EvolutionConfig(**{field: value})
    assert getattr(config, field) == value
    # Should produce a valid engine
    engine = EvolutionEngine(config=config)
    assert engine.config is config
