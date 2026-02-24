"""Evolution endpoints — fitness, history, and evolution cycles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from labclaw.api.deps import get_evolution_engine
from labclaw.core.schemas import EvolutionTarget
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.schemas import EvolutionCycle, FitnessScore

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class FitnessRequest(BaseModel):
    target: EvolutionTarget
    metrics: dict[str, float]
    data_points: int = 0


class CycleStartRequest(BaseModel):
    target: EvolutionTarget
    n_candidates: int = 1


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/history")
def evolution_history(
    target: EvolutionTarget | None = None,
    engine: EvolutionEngine = Depends(get_evolution_engine),
) -> list[EvolutionCycle]:
    return engine.get_history(target=target)


@router.post("/fitness")
def measure_fitness(
    body: FitnessRequest,
    engine: EvolutionEngine = Depends(get_evolution_engine),
) -> FitnessScore:
    return engine.measure_fitness(
        target=body.target,
        metrics=body.metrics,
        data_points=body.data_points,
    )


@router.post("/cycle", status_code=201)
def start_cycle(
    body: CycleStartRequest,
    engine: EvolutionEngine = Depends(get_evolution_engine),
) -> EvolutionCycle:
    # Measure baseline
    baseline = engine.measure_fitness(
        target=body.target,
        metrics={"baseline": 1.0},
        data_points=0,
    )
    # Propose candidates
    candidates = engine.propose_candidates(body.target, n=body.n_candidates)
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail=f"No candidate proposals available for target {body.target.value!r}",
        )
    # Start cycle with first candidate
    return engine.start_cycle(candidates[0], baseline)
