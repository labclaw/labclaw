"""BDD step definitions for L5 Self-Evolution.

Spec: docs/specs/L5-evolution.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

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
def propose_candidates(
    engine: EvolutionEngine, n: int, target: str
) -> list[EvolutionCandidate]:
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
def get_history_for_target(
    engine: EvolutionEngine, target: str
) -> list[EvolutionCycle]:
    return engine.get_history(EvolutionTarget(target))


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
    assert len(proposed_candidates) == n, (
        f"Expected {n} candidates, got {len(proposed_candidates)}"
    )


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
    assert len(history) == n, (
        f"Expected {n} cycles, got {len(history)}"
    )
