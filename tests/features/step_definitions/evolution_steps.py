"""BDD step definitions for L5 Self-Evolution.

Spec: docs/specs/L5-evolution.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.schemas import EvolutionStage, EvolutionTarget
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.schemas import (
    EvolutionCandidate,
    EvolutionCycle,
    FitnessScore,
)

# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("the evolution engine is initialized", target_fixture="engine")
def evolution_engine_initialized(event_capture: object) -> EvolutionEngine:
    """Provide an EvolutionEngine and subscribe event capture to all events."""
    engine = EvolutionEngine()
    for evt_name in [
        "evolution.cycle.started",
        "evolution.cycle.advanced",
        "evolution.cycle.promoted",
        "evolution.cycle.rolled_back",
        "evolution.fitness.measured",
    ]:
        event_registry.subscribe(evt_name, event_capture)  # type: ignore[arg-type]
    return engine


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a baseline fitness for "{target}" with accuracy {accuracy:f}'),
    target_fixture="baseline_fitness",
)
def baseline_fitness_for_target(
    engine: EvolutionEngine, target: str, accuracy: float
) -> FitnessScore:
    """Measure a baseline fitness score."""
    return engine.measure_fitness(
        EvolutionTarget(target),
        metrics={"accuracy": accuracy},
        data_points=100,
    )


@given(
    parsers.parse('a candidate for "{target}"'),
    target_fixture="candidate",
)
def a_candidate_for_target(target: str) -> EvolutionCandidate:
    """Create a test candidate."""
    return EvolutionCandidate(
        target=EvolutionTarget(target),
        description="Test candidate for evolution",
        config_diff={"correlation_threshold": 0.45},
        proposed_by="test",
    )


@given(
    parsers.parse('a started evolution cycle in stage "{stage}"'),
    target_fixture="cycle",
)
def started_cycle_in_stage(
    engine: EvolutionEngine,
    candidate: EvolutionCandidate,
    baseline_fitness: FitnessScore,
    stage: str,
) -> EvolutionCycle:
    """Start a cycle (stage param confirms the initial stage)."""
    cycle = engine.start_cycle(candidate, baseline_fitness)
    assert cycle.stage == EvolutionStage(stage)
    return cycle


@given(
    parsers.parse('{n:d} completed evolution cycles for "{target}"'),
    target_fixture="completed_cycles",
)
def completed_evolution_cycles(
    engine: EvolutionEngine, n: int, target: str
) -> list[EvolutionCycle]:
    """Create n completed (promoted) evolution cycles."""
    ev_target = EvolutionTarget(target)
    cycles: list[EvolutionCycle] = []

    for i in range(n):
        baseline = engine.measure_fitness(
            ev_target,
            metrics={"accuracy": 0.70 + i * 0.01},
            data_points=50,
        )
        candidate = EvolutionCandidate(
            target=ev_target,
            description=f"Test candidate {i}",
            config_diff={"param": i},
            proposed_by="test",
        )
        cycle = engine.start_cycle(candidate, baseline)

        # Advance through all stages to promoted
        for acc in [0.80, 0.82, 0.85]:
            fitness = FitnessScore(
                target=ev_target,
                metrics={"accuracy": acc},
                data_points=50,
            )
            cycle = engine.advance_stage(cycle.cycle_id, fitness)

        cycles.append(cycle)

    return cycles


@given("a promoted evolution cycle", target_fixture="cycle")
def a_promoted_evolution_cycle(
    engine: EvolutionEngine,
    candidate: EvolutionCandidate,
    baseline_fitness: FitnessScore,
) -> EvolutionCycle:
    """Create a fully promoted cycle."""
    cycle = engine.start_cycle(candidate, baseline_fitness)
    for acc in [0.85, 0.87, 0.88]:
        fitness = FitnessScore(
            target=cycle.target,
            metrics={"accuracy": acc},
            data_points=50,
        )
        cycle = engine.advance_stage(cycle.cycle_id, fitness)
    assert cycle.stage == EvolutionStage.PROMOTED
    return cycle


@given("a rolled-back evolution cycle", target_fixture="cycle")
def a_rolled_back_evolution_cycle(
    engine: EvolutionEngine,
    candidate: EvolutionCandidate,
    baseline_fitness: FitnessScore,
) -> EvolutionCycle:
    """Create a cycle that has been rolled back."""
    cycle = engine.start_cycle(candidate, baseline_fitness)
    cycle = engine.rollback(cycle.cycle_id, "test rollback")
    assert cycle.stage == EvolutionStage.ROLLED_BACK
    return cycle


@given("a started prompts evolution cycle", target_fixture="prompts_cycle")
def started_prompts_evolution_cycle(
    engine: EvolutionEngine,
) -> EvolutionCycle:
    """Start a second cycle for the prompts target."""
    baseline = engine.measure_fitness(
        EvolutionTarget.PROMPTS,
        metrics={"accuracy": 0.75},
        data_points=50,
    )
    candidate = EvolutionCandidate(
        target=EvolutionTarget.PROMPTS,
        description="Prompts candidate",
        config_diff={"temperature": 0.5},
        proposed_by="test",
    )
    return engine.start_cycle(candidate, baseline)


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I measure fitness for target "{target}" with metrics:'),
    target_fixture="measured_fitness",
)
def measure_fitness_with_table(
    engine: EvolutionEngine, target: str, datatable: list[list[str]]
) -> FitnessScore:
    """Measure fitness from a table of metric/value pairs."""
    metrics: dict[str, float] = {}
    for row in datatable:
        # Skip header row
        if row[1] == "value":
            continue
        metrics[row[0]] = float(row[1])
    return engine.measure_fitness(
        EvolutionTarget(target),
        metrics=metrics,
        data_points=len(metrics),
    )


@when(
    parsers.parse('I propose {n:d} candidates for target "{target}"'),
    target_fixture="proposed_candidates",
)
def propose_candidates(engine: EvolutionEngine, n: int, target: str) -> list[EvolutionCandidate]:
    return engine.propose_candidates(EvolutionTarget(target), n=n)


@when("I start an evolution cycle", target_fixture="cycle")
def start_evolution_cycle(
    engine: EvolutionEngine,
    candidate: EvolutionCandidate,
    baseline_fitness: FitnessScore,
) -> EvolutionCycle:
    return engine.start_cycle(candidate, baseline_fitness)


@when(
    parsers.parse("I advance with fitness accuracy {accuracy:f}"),
    target_fixture="cycle",
)
def advance_with_fitness(
    engine: EvolutionEngine, cycle: EvolutionCycle, accuracy: float
) -> EvolutionCycle:
    fitness = FitnessScore(
        target=cycle.target,
        metrics={"accuracy": accuracy},
        data_points=50,
    )
    return engine.advance_stage(cycle.cycle_id, fitness)


@when(
    parsers.parse('I get history for target "{target}"'),
    target_fixture="history",
)
def get_history_for_target(engine: EvolutionEngine, target: str) -> list[EvolutionCycle]:
    return engine.get_history(EvolutionTarget(target))


@when(
    parsers.parse('I get fitness history for "{target}"'),
    target_fixture="fitness_history",
)
def get_fitness_history(engine: EvolutionEngine, target: str) -> list[FitnessScore]:
    return engine.fitness_tracker.get_history(EvolutionTarget(target))


@when(
    parsers.parse('I manually rollback the cycle with reason "{reason}"'),
    target_fixture="cycle",
)
def manually_rollback_cycle(
    engine: EvolutionEngine, cycle: EvolutionCycle, reason: str
) -> EvolutionCycle:
    return engine.rollback(cycle.cycle_id, reason)


@when("I try to advance the promoted cycle", target_fixture="advance_error")
def try_advance_promoted_cycle(engine: EvolutionEngine, cycle: EvolutionCycle) -> Exception | None:
    fitness = FitnessScore(
        target=cycle.target,
        metrics={"accuracy": 0.90},
        data_points=50,
    )
    try:
        engine.advance_stage(cycle.cycle_id, fitness)
        return None
    except ValueError as exc:
        return exc


@when("I try to advance the rolled-back cycle", target_fixture="advance_error")
def try_advance_rolled_back_cycle(
    engine: EvolutionEngine, cycle: EvolutionCycle
) -> Exception | None:
    fitness = FitnessScore(
        target=cycle.target,
        metrics={"accuracy": 0.90},
        data_points=50,
    )
    try:
        engine.advance_stage(cycle.cycle_id, fitness)
        return None
    except ValueError as exc:
        return exc


@when("I get active cycles", target_fixture="active_cycles")
def get_active_cycles(engine: EvolutionEngine) -> list[EvolutionCycle]:
    return engine.get_active_cycles()


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("a FitnessScore is returned with {n:d} metrics"))
def check_fitness_score_metrics(measured_fitness: FitnessScore, n: int) -> None:
    assert len(measured_fitness.metrics) == n, (
        f"Expected {n} metrics, got {len(measured_fitness.metrics)}"
    )


@then(parsers.parse("{n:d} EvolutionCandidates are returned"))
def check_candidate_count(proposed_candidates: list[EvolutionCandidate], n: int) -> None:
    assert len(proposed_candidates) == n, f"Expected {n} candidates, got {len(proposed_candidates)}"


@then("each candidate has a description and config_diff")
def check_candidate_fields(proposed_candidates: list[EvolutionCandidate]) -> None:
    for c in proposed_candidates:
        assert c.description, f"Candidate {c.candidate_id} has empty description"
        assert c.config_diff, f"Candidate {c.candidate_id} has empty config_diff"


@then(parsers.parse('the cycle is in stage "{stage}"'))
def check_cycle_stage(cycle: EvolutionCycle, stage: str) -> None:
    assert cycle.stage == EvolutionStage(stage), (
        f"Expected stage {stage!r}, got {cycle.stage.value!r}"
    )


@then(parsers.parse('the cycle is in stage "{stage}" and promoted is true'))
def check_cycle_stage_and_promoted(cycle: EvolutionCycle, stage: str) -> None:
    assert cycle.stage == EvolutionStage(stage), (
        f"Expected stage {stage!r}, got {cycle.stage.value!r}"
    )
    assert cycle.promoted is True, "Expected promoted to be True"


@then("the cycle is rolled back")
def check_cycle_rolled_back(cycle: EvolutionCycle) -> None:
    assert cycle.stage == EvolutionStage.ROLLED_BACK
    assert cycle.rollback_reason is not None


@then(parsers.parse('the stage is "{stage}"'))
def check_stage_value(cycle: EvolutionCycle, stage: str) -> None:
    assert cycle.stage == EvolutionStage(stage), (
        f"Expected stage {stage!r}, got {cycle.stage.value!r}"
    )


@then(parsers.parse("I receive {n:d} cycles"))
def check_history_count(history: list[EvolutionCycle], n: int) -> None:
    assert len(history) == n, f"Expected {n} cycles, got {len(history)}"


@then(parsers.parse('the latest fitness for "{target}" has accuracy {accuracy:f}'))
def check_latest_fitness_accuracy(engine: EvolutionEngine, target: str, accuracy: float) -> None:
    latest = engine.fitness_tracker.get_latest(EvolutionTarget(target))
    assert latest is not None, f"No fitness recorded for {target!r}"
    assert latest.metrics.get("accuracy") == pytest.approx(accuracy), (
        f"Expected accuracy {accuracy}, got {latest.metrics.get('accuracy')}"
    )


@then(parsers.parse("the fitness history has {n:d} entries"))
def check_fitness_history_count(fitness_history: list[FitnessScore], n: int) -> None:
    assert len(fitness_history) == n, f"Expected {n} fitness entries, got {len(fitness_history)}"


@then("the history is ordered by start time")
def check_history_ordered(history: list[EvolutionCycle]) -> None:
    for i in range(len(history) - 1):
        assert history[i].started_at <= history[i + 1].started_at, (
            f"History not ordered: {history[i].started_at} > {history[i + 1].started_at}"
        )


@then("a ValueError is raised")
def check_value_error_raised(advance_error: Exception | None) -> None:
    assert isinstance(advance_error, ValueError), (
        f"Expected ValueError, got {type(advance_error)}"
    )


@then(parsers.parse('the rollback reason is "{reason}"'))
def check_rollback_reason(cycle: EvolutionCycle, reason: str) -> None:
    assert cycle.rollback_reason == reason, (
        f"Expected reason {reason!r}, got {cycle.rollback_reason!r}"
    )


@then("I can retrieve the cycle by its ID")
def check_cycle_retrievable_by_id(engine: EvolutionEngine, cycle: EvolutionCycle) -> None:
    retrieved = engine.get_cycle(cycle.cycle_id)
    assert retrieved.cycle_id == cycle.cycle_id


@then(parsers.parse("{n:d} active cycle is returned"))
def check_active_cycles_count_singular(active_cycles: list[EvolutionCycle], n: int) -> None:
    assert len(active_cycles) == n, f"Expected {n} active cycles, got {len(active_cycles)}"


@then("the new fitness is better than baseline")
def check_new_fitness_better(
    engine: EvolutionEngine, baseline_fitness: FitnessScore, measured_fitness: FitnessScore
) -> None:
    baseline_acc = baseline_fitness.metrics.get("accuracy", 0.0)
    new_acc = measured_fitness.metrics.get("accuracy", 0.0)
    assert new_acc > baseline_acc, (
        f"New fitness {new_acc} is not better than baseline {baseline_acc}"
    )
