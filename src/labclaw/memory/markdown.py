"""Tier A: Human-readable memory — markdown files as source of truth.

Spec: docs/specs/L4-memory.md
Design doc: Section 6 (Memory Architecture), Section 10.4 (Memory Tier Consistency)

Handles {root}/{entity_id}/SOUL.md and {root}/{entity_id}/MEMORY.md.
SOUL.md has YAML frontmatter + markdown body.
MEMORY.md is append-only with timestamped entries.
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from labclaw.core.events import event_registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events at module import time
# ---------------------------------------------------------------------------

_EVENTS = [
    "memory.tier_a.created",
    "memory.tier_a.updated",
    "memory.search.executed",
]

for _evt in _EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class MemoryEntry(BaseModel):
    """A single timestamped entry appended to MEMORY.md."""

    timestamp: datetime
    category: str
    detail: str


class MarkdownDoc(BaseModel):
    """Parsed representation of a SOUL.md or MEMORY.md file."""

    path: Path
    frontmatter: dict[str, Any]
    content: str

    model_config = {"arbitrary_types_allowed": True}


class SearchResult(BaseModel):
    """A single result from memory search."""

    entity_id: str
    snippet: str
    score: float
    source: str  # "soul" or "memory"


# ---------------------------------------------------------------------------
# Frontmatter parsing helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split markdown text into YAML frontmatter dict and body content.

    Frontmatter is delimited by --- markers at start of file.
    Returns (frontmatter_dict, body_string).
    """
    if not text.startswith("---"):
        return {}, text

    # Find the closing --- marker at the start of a line
    match = re.search(r"\n---\s*\n", text[3:])
    if match is None:
        # Also handle --- at EOF
        match = re.search(r"\n---\s*$", text[3:])
    if match is None:
        return {}, text
    end_idx = 3 + match.start() + 1  # +1 to skip the \n before ---

    yaml_text = text[3:end_idx].strip()
    body = text[end_idx + 3 :].strip()

    if not yaml_text:
        return {}, body

    try:
        frontmatter = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML frontmatter: {exc}") from exc

    if not isinstance(frontmatter, dict):
        return {}, body

    return frontmatter, body


def _render_frontmatter(frontmatter: dict[str, Any], content: str) -> str:
    """Render frontmatter dict + content into a complete markdown string."""
    if frontmatter:
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True).strip()
        return f"---\n{yaml_str}\n---\n\n{content}"
    return content


def _render_memory_entry(entry: MemoryEntry) -> str:
    """Render a single memory entry as a markdown section."""
    ts = entry.timestamp.isoformat()
    return f"## {ts}\n\n**Category:** {entry.category}\n\n{entry.detail}\n"


# ---------------------------------------------------------------------------
# TierABackend
# ---------------------------------------------------------------------------


class TierABackend:
    """Tier A memory backend: markdown files as source of truth.

    Directory layout:
        {root}/{entity_id}/SOUL.md
        {root}/{entity_id}/MEMORY.md
    """

    _memory_file_locks: dict[Path, threading.Lock] = {}
    _memory_file_locks_guard = threading.Lock()

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def _entity_dir(self, entity_id: str) -> Path:
        if not entity_id:
            raise ValueError("entity_id must be non-empty")
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_-]|\.(?!\.)){0,127}", entity_id):
            raise ValueError("entity_id must match [A-Za-z0-9](?:[A-Za-z0-9_-]|\\.(?!\\.)){0,127}")
        return self._root / entity_id

    def _soul_path(self, entity_id: str) -> Path:
        return self._entity_dir(entity_id) / "SOUL.md"

    def _memory_path(self, entity_id: str) -> Path:
        return self._entity_dir(entity_id) / "MEMORY.md"

    @classmethod
    def _memory_file_lock(cls, path: Path) -> threading.Lock:
        normalized = path.resolve()
        with cls._memory_file_locks_guard:
            lock = cls._memory_file_locks.get(normalized)
            if lock is None:
                lock = threading.Lock()
                cls._memory_file_locks[normalized] = lock
            return lock

    def read_soul(self, entity_id: str) -> MarkdownDoc:
        """Read {root}/{entity_id}/SOUL.md.

        Raises FileNotFoundError if the file does not exist.
        """
        path = self._soul_path(entity_id)
        if not path.exists():
            raise FileNotFoundError(f"SOUL.md not found for entity {entity_id!r}: {path}")
        text = path.read_text(encoding="utf-8")
        frontmatter, content = _parse_frontmatter(text)
        return MarkdownDoc(path=path, frontmatter=frontmatter, content=content)

    def read_memory(self, entity_id: str) -> MarkdownDoc:
        """Read {root}/{entity_id}/MEMORY.md.

        Raises FileNotFoundError if the file does not exist.
        """
        path = self._memory_path(entity_id)
        if not path.exists():
            raise FileNotFoundError(f"MEMORY.md not found for entity {entity_id!r}: {path}")
        text = path.read_text(encoding="utf-8")
        frontmatter, content = _parse_frontmatter(text)
        return MarkdownDoc(path=path, frontmatter=frontmatter, content=content)

    def write_soul(self, entity_id: str, doc: MarkdownDoc) -> None:
        """Write SOUL.md with frontmatter + content.

        Creates the entity directory if needed.
        Emits memory.tier_a.created (new) or memory.tier_a.updated (existing).
        """
        path = self._soul_path(entity_id)
        is_new = not path.exists()

        # Create directory if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        text = _render_frontmatter(doc.frontmatter, doc.content)
        path.write_text(text, encoding="utf-8")

        event_name = "memory.tier_a.created" if is_new else "memory.tier_a.updated"
        event_registry.emit(
            event_name,
            payload={"entity_id": entity_id, "path": str(path)},
        )
        logger.info("%s SOUL.md for %s", "Created" if is_new else "Updated", entity_id)

    def append_memory(self, entity_id: str, entry: MemoryEntry) -> None:
        """Append a timestamped entry to MEMORY.md.

        Creates the file and directory if needed.
        Emits memory.tier_a.updated.
        """
        path = self._memory_path(entity_id)
        lock = self._memory_file_lock(path)

        # Serialize read/modify/write per file across all backend instances
        # in this process to avoid dropping entries under concurrent writers.
        with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            rendered = _render_memory_entry(entry)

            if path.exists():
                existing = path.read_text(encoding="utf-8")
                if existing and not existing.endswith("\n"):
                    existing += "\n"
                new_text = existing + "\n" + rendered
            else:
                new_text = rendered

            path.write_text(new_text, encoding="utf-8")

        event_registry.emit(
            "memory.tier_a.updated",
            payload={"entity_id": entity_id, "path": str(path)},
        )
        logger.debug("Appended memory entry for %s: %s", entity_id, entry.category)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Substring search across all SOUL.md and MEMORY.md files.

        Returns results ranked by match count (case-insensitive).
        Emits memory.search.executed.
        """
        results: list[SearchResult] = []
        query_lower = query.lower()
        query_terms = query_lower.split()

        if not self._root.exists():
            event_registry.emit(
                "memory.search.executed",
                payload={"query": query, "result_count": 0},
            )
            return results

        for entity_dir in sorted(self._root.iterdir()):
            if not entity_dir.is_dir():
                continue
            entity_id = entity_dir.name

            # Search SOUL.md
            soul_path = entity_dir / "SOUL.md"
            if soul_path.exists():
                text = soul_path.read_text(encoding="utf-8")
                score = self._score_text(text, query_terms)
                if score > 0:
                    snippet = self._extract_snippet(text, query_lower)
                    results.append(
                        SearchResult(
                            entity_id=entity_id,
                            snippet=snippet,
                            score=score,
                            source="soul",
                        )
                    )

            # Search MEMORY.md
            mem_path = entity_dir / "MEMORY.md"
            if mem_path.exists():
                text = mem_path.read_text(encoding="utf-8")
                score = self._score_text(text, query_terms)
                if score > 0:
                    snippet = self._extract_snippet(text, query_lower)
                    results.append(
                        SearchResult(
                            entity_id=entity_id,
                            snippet=snippet,
                            score=score,
                            source="memory",
                        )
                    )

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:limit]

        event_registry.emit(
            "memory.search.executed",
            payload={"query": query, "result_count": len(results)},
        )
        return results

    @staticmethod
    def _score_text(text: str, query_terms: list[str]) -> float:
        """Score text by counting occurrences of query terms (case-insensitive)."""
        text_lower = text.lower()
        score = 0.0
        for term in query_terms:
            score += text_lower.count(term)
        return score

    @staticmethod
    def _extract_snippet(text: str, query_lower: str, max_len: int = 200) -> str:
        """Extract a snippet around the first occurrence of the query."""
        text_lower = text.lower()
        # Try to find the first query term
        first_term = query_lower.split()[0] if query_lower.split() else query_lower
        idx = text_lower.find(first_term)
        if idx == -1:
            # Fallback: return start of text
            return text[:max_len].strip()

        start = max(0, idx - 50)
        end = min(len(text), idx + max_len - 50)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet
