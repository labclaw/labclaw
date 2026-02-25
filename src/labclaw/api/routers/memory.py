"""Memory (Tier A) endpoints — SOUL.md / MEMORY.md read, append, search."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from labclaw.api.deps import get_tier_a_backend
from labclaw.memory.markdown import MemoryEntry, SearchResult, TierABackend

router = APIRouter()

_ENTITY_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def _validate_entity_id_or_400(entity_id: str) -> None:
    if _ENTITY_ID_PATTERN.fullmatch(entity_id):
        return
    raise HTTPException(
        status_code=400,
        detail="entity_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}",
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class MemoryAppendRequest(BaseModel):
    category: str
    detail: str


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
