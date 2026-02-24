"""Orchestrator endpoints — trigger and inspect scientific loop cycles."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from labclaw.orchestrator.loop import CycleResult

router = APIRouter()

# In-process cycle history (process-scoped; cleared on restart)
_cycle_history: list[CycleResult] = []


class CycleRequest(BaseModel):
    """Request body for triggering a cycle."""

    data_rows: list[dict[str, Any]] = []


@router.post("/cycle", status_code=201)
async def run_cycle(body: CycleRequest) -> CycleResult:
    """Trigger one ScientificLoop cycle.

    Pass ``data_rows`` in the request body, or leave empty to use an
    empty observation set (useful for testing the pipeline).
    """
    from labclaw.orchestrator.loop import ScientificLoop

    loop = ScientificLoop()
    try:
        result = await loop.run_cycle(body.data_rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _cycle_history.append(result)
    return result


@router.get("/history")
def cycle_history() -> list[CycleResult]:
    """Return all cycle results for this process lifetime."""
    return list(_cycle_history)


@router.get("/history/{cycle_id}")
def get_cycle(cycle_id: str) -> CycleResult:
    """Retrieve a single cycle result by ID."""
    for result in _cycle_history:
        if result.cycle_id == cycle_id:
            return result
    raise HTTPException(status_code=404, detail=f"Cycle {cycle_id!r} not found")
