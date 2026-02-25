"""Property-based tests using Hypothesis for LabClaw models and data paths."""

from __future__ import annotations

import csv
import tempfile
import threading
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from labclaw.core.governance import GovernanceDecision, GovernanceEngine
from labclaw.core.schemas import (
    EvolutionTarget,
)
from labclaw.evolution.schemas import (
    EvolutionCandidate,
    FitnessScore,
)
from labclaw.orchestrator.steps import StepContext
from labclaw.plugins.base import PluginMetadata

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

safe_text = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S", "Z"), exclude_characters="\x00"),
    min_size=1,
    max_size=50,
)

safe_floats = st.floats(
    min_value=-1e10,
    max_value=1e10,
    allow_nan=False,
    allow_infinity=False,
)

json_primitive = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31),
    safe_floats,
    safe_text,
)

json_value = st.recursive(
    json_primitive,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(safe_text, children, max_size=5),
    ),
    max_leaves=10,
)


# ---------------------------------------------------------------------------
# 1. StepContext: any combination of valid fields produces a valid model
# ---------------------------------------------------------------------------


@given(
    data_rows=st.lists(
        st.dictionaries(safe_text, json_primitive, max_size=5),
        max_size=10,
    ),
    cycle_id=st.text(max_size=50),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_step_context_roundtrip(data_rows: list[dict], cycle_id: str) -> None:
    ctx = StepContext(data_rows=data_rows, cycle_id=cycle_id)
    dumped = ctx.model_dump(mode="json")
    restored = StepContext.model_validate(dumped)
    assert restored.cycle_id == ctx.cycle_id
    assert len(restored.data_rows) == len(ctx.data_rows)


# ---------------------------------------------------------------------------
# 2. FitnessScore: arbitrary float metrics serialize/deserialize
# ---------------------------------------------------------------------------


@given(
    metrics=st.dictionaries(
        safe_text,
        safe_floats,
        min_size=1,
        max_size=10,
    ),
    data_points=st.integers(min_value=0, max_value=100_000),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_fitness_score_roundtrip(metrics: dict[str, float], data_points: int) -> None:
    score = FitnessScore(
        target=EvolutionTarget.ANALYSIS_PARAMS,
        metrics=metrics,
        data_points=data_points,
    )
    json_str = score.model_dump_json()
    restored = FitnessScore.model_validate_json(json_str)
    assert restored.metrics == score.metrics
    assert restored.data_points == score.data_points


# ---------------------------------------------------------------------------
# 3. EvolutionCandidate: arbitrary config_diff dicts are handled
# ---------------------------------------------------------------------------


@given(
    config_diff=st.dictionaries(safe_text, json_value, max_size=10),
    description=safe_text,
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_evolution_candidate_arbitrary_config(
    config_diff: dict[str, Any], description: str
) -> None:
    candidate = EvolutionCandidate(
        target=EvolutionTarget.PROMPTS,
        description=description,
        config_diff=config_diff,
    )
    dumped = candidate.model_dump(mode="json")
    restored = EvolutionCandidate.model_validate(dumped)
    assert restored.description == candidate.description
    assert restored.config_diff == candidate.config_diff


# ---------------------------------------------------------------------------
# 4. DataAccumulator thread safety: concurrent ingest_file calls
# ---------------------------------------------------------------------------


@given(
    num_files=st.integers(min_value=2, max_value=5),
    rows_per_file=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_data_accumulator_thread_safety(num_files: int, rows_per_file: int) -> None:
    from labclaw.daemon import DataAccumulator

    acc = DataAccumulator()
    tmpdir = Path(tempfile.mkdtemp())

    files: list[Path] = []
    for i in range(num_files):
        p = tmpdir / f"data_{i}.csv"
        with p.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["x", "y"])
            writer.writeheader()
            for j in range(rows_per_file):
                writer.writerow({"x": float(i * 100 + j), "y": float(j)})
        files.append(p)

    errors: list[Exception] = []
    results: list[int] = [0] * num_files

    def ingest(idx: int) -> None:
        try:
            results[idx] = acc.ingest_file(files[idx])
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=ingest, args=(i,)) for i in range(num_files)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors during concurrent ingest: {errors}"
    total_ingested = sum(results)
    assert total_ingested == acc.total_rows
    assert acc.total_rows == num_files * rows_per_file


# ---------------------------------------------------------------------------
# 5. CSV parsing fuzz: arbitrary CSV content doesn't crash
# ---------------------------------------------------------------------------


@given(
    header=st.lists(
        safe_text.filter(lambda s: "," not in s and "\n" not in s),
        min_size=1,
        max_size=5,
    ),
    rows=st.lists(
        st.lists(safe_text.filter(lambda s: "\n" not in s), min_size=1, max_size=5),
        max_size=10,
    ),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_data_accumulator_csv_fuzz(header: list[str], rows: list[list[str]]) -> None:
    from labclaw.daemon import DataAccumulator

    acc = DataAccumulator()
    tmpdir = Path(tempfile.mkdtemp())
    p = tmpdir / "fuzz.csv"

    with p.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            # Pad or trim row to match header length
            padded = (row + [""] * len(header))[: len(header)]
            writer.writerow(padded)

    # Should not raise
    result = acc.ingest_file(p)
    assert result >= 0


# ---------------------------------------------------------------------------
# 6. GovernanceDecision: any role string produces a valid decision
# ---------------------------------------------------------------------------


@given(role=safe_text)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_governance_any_role(role: str) -> None:
    engine = GovernanceEngine()
    decision = engine.check(
        action="read",
        actor="test-user",
        role=role,
    )
    assert isinstance(decision, GovernanceDecision)
    assert isinstance(decision.allowed, bool)
    # Known roles with 'read' permission should be allowed
    if role in engine._role_permissions:
        perms = engine._role_permissions[role]
        if "*" in perms or "read" in perms:
            assert decision.allowed


# ---------------------------------------------------------------------------
# 7. PluginMetadata: arbitrary strings produce valid model
# ---------------------------------------------------------------------------


@given(
    name=safe_text,
    version=safe_text,
    description=safe_text,
    author=safe_text,
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_plugin_metadata_arbitrary_strings(
    name: str, version: str, description: str, author: str
) -> None:
    meta = PluginMetadata(
        name=name,
        version=version,
        description=description,
        author=author,
        plugin_type="device",
    )
    dumped = meta.model_dump(mode="json")
    restored = PluginMetadata.model_validate(dumped)
    assert restored.name == name
    assert restored.version == version
    assert restored.description == description
    assert restored.author == author
