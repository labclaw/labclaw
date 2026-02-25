"""Provenance endpoints — query full traceability chains for findings."""

from __future__ import annotations

from collections import OrderedDict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from labclaw.validation.provenance import ProvenanceTracker
from labclaw.validation.statistics import ProvenanceChain, ProvenanceStep

router = APIRouter()

# In-process store (process-scoped; replaced by persistent store in v0.1.0)
_chains: OrderedDict[str, ProvenanceChain] = OrderedDict()
_MAX_CHAINS = 10_000


class ProvenanceStepIn(BaseModel):
    """Request schema for a single provenance step."""

    node_id: str
    node_type: str
    description: str


class ProvenanceRequest(BaseModel):
    """Request body for registering a new provenance chain."""

    finding_id: str
    steps: list[ProvenanceStepIn]


@router.post("/", status_code=201)
def create_provenance_chain(body: ProvenanceRequest) -> ProvenanceChain:
    """Register a provenance chain for a finding.

    Args:
        body: finding_id and ordered steps.

    Returns:
        The created ProvenanceChain.

    Raises:
        HTTPException 400: If steps list is empty.
    """
    tracker = ProvenanceTracker()
    steps = [
        ProvenanceStep(
            node_id=s.node_id,
            node_type=s.node_type,
            description=s.description,
        )
        for s in body.steps
    ]
    try:
        chain = tracker.build_chain(body.finding_id, steps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid provenance chain") from exc
    if body.finding_id in _chains:
        _chains.move_to_end(body.finding_id)
    _chains[body.finding_id] = chain
    while len(_chains) > _MAX_CHAINS:
        _chains.popitem(last=False)
    return chain


@router.get("/{finding_id}")
def get_provenance_chain(finding_id: str) -> ProvenanceChain:
    """Retrieve the provenance chain for a specific finding.

    Args:
        finding_id: The finding whose chain is requested.

    Returns:
        The ProvenanceChain associated with finding_id.

    Raises:
        HTTPException 404: If no chain is registered for finding_id.
    """
    chain = _chains.get(finding_id)
    if chain is None:
        raise HTTPException(
            status_code=404,
            detail=f"No provenance chain found for finding {finding_id!r}",
        )
    return chain
