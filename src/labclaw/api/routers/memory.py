"""Memory endpoints — Tier A (SOUL/MEMORY.md) + Tier B (KG) + findings."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from labclaw.api.deps import get_tier_a_backend
from labclaw.memory.markdown import MemoryEntry, SearchResult, TierABackend

router = APIRouter()

_ENTITY_ID_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_-]|\.(?!\.)){0,127}")


def _validate_entity_id_or_400(entity_id: str) -> None:
    if _ENTITY_ID_PATTERN.fullmatch(entity_id):
        return
    raise HTTPException(
        status_code=400,
        detail="entity_id must match [A-Za-z0-9](?:[A-Za-z0-9_-]|\\.(?!\\.)){0,127}",
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class MemoryAppendRequest(BaseModel):
    category: str = Field(max_length=200)
    detail: str = Field(max_length=10_000)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MarkdownDocResponse(BaseModel):
    path: str
    frontmatter: dict
    content: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/search/query")
def search_memory(
    q: str = "",
    limit: int = Query(default=10, ge=1),
    backend: TierABackend = Depends(get_tier_a_backend),
) -> list[SearchResult]:
    if not q:
        return []
    return backend.search(q, limit=limit)


@router.get("/{entity_id}/soul")
def read_soul(
    entity_id: str,
    backend: TierABackend = Depends(get_tier_a_backend),
) -> MarkdownDocResponse:
    _validate_entity_id_or_400(entity_id)
    try:
        doc = backend.read_soul(entity_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"SOUL.md not found for {entity_id!r}")
    return MarkdownDocResponse(path=str(doc.path), frontmatter=doc.frontmatter, content=doc.content)


@router.get("/{entity_id}/memory")
def read_memory(
    entity_id: str,
    backend: TierABackend = Depends(get_tier_a_backend),
) -> MarkdownDocResponse:
    _validate_entity_id_or_400(entity_id)
    try:
        doc = backend.read_memory(entity_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"MEMORY.md not found for {entity_id!r}")
    return MarkdownDocResponse(path=str(doc.path), frontmatter=doc.frontmatter, content=doc.content)


@router.post("/{entity_id}/memory", status_code=201)
def append_memory(
    entity_id: str,
    body: MemoryAppendRequest,
    backend: TierABackend = Depends(get_tier_a_backend),
) -> dict[str, str]:
    _validate_entity_id_or_400(entity_id)
    entry = MemoryEntry(
        timestamp=datetime.now(UTC),
        category=body.category,
        detail=body.detail,
    )
    backend.append_memory(entity_id, entry)
    return {"entity_id": entity_id, "category": body.category, "status": "appended"}


# ---------------------------------------------------------------------------
# Findings (Tier A+B) endpoints
# ---------------------------------------------------------------------------


@router.get("/findings")
async def list_findings(
    q: str = "",
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """List stored findings. Reads from SessionMemoryManager if available,
    otherwise falls back to Tier A markdown parsing."""
    from labclaw.api.deps import _default_memory_root

    root = _default_memory_root()
    from labclaw.memory.session_memory import SessionMemoryManager

    mgr = SessionMemoryManager(memory_root=root)
    await mgr.init()
    try:
        findings = await mgr.retrieve_findings(query=q)
    finally:
        await mgr.close()
    return findings[:limit]


# ---------------------------------------------------------------------------
# Knowledge Graph (Tier B) endpoints
# ---------------------------------------------------------------------------


@router.get("/kg/nodes")
async def list_kg_nodes(
    node_type: str = "",
    label: str = "",
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """List nodes in the knowledge graph with optional type/label filtering."""
    from labclaw.memory.knowledge_graph import KGQueryFilter, TierBBackend

    kg = TierBBackend()
    filt = KGQueryFilter()
    if node_type:
        filt = KGQueryFilter(node_type=node_type)
    if label:
        filt = KGQueryFilter(node_type=node_type or None, tags=[label])
    nodes = kg.query_nodes(filt)
    return [n.model_dump(mode="json") for n in nodes[:limit]]


@router.get("/kg/neighbors/{node_id}")
async def get_kg_neighbors(
    node_id: str,
    relation: str = "",
    direction: str = "outgoing",
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get neighbor nodes for a given node in the knowledge graph."""
    from labclaw.memory.knowledge_graph import TierBBackend

    kg = TierBBackend()
    node = kg.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")
    neighbors = kg.get_neighbors(
        node_id,
        relation=relation or None,
        direction=direction,
    )
    return [n.model_dump(mode="json") for n, _edge in neighbors[:limit]]
