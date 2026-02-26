"""Cross-session memory manager — persists findings across daemon restarts.

Implements C3 REMEMBER: restart → ≥90% historical findings retrievable.

Tier A (Markdown) stores human-readable finding records.
Tier B (SQLite) stores structured JSON for fast retrieval.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from labclaw.core.events import event_registry
from labclaw.memory.markdown import MarkdownDoc, MemoryEntry, TierABackend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_SESSION_EVENTS = [
    "memory.session.finding_stored",
    "memory.session.findings_retrieved",
    "memory.session.initialized",
]

for _evt in _SESSION_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)

# Entity ID under which all findings are stored in Tier A.
_FINDINGS_ENTITY_ID = "findings"


# ---------------------------------------------------------------------------
# SessionMemoryManager
# ---------------------------------------------------------------------------


class SessionMemoryManager:
    """Manages memory persistence across daemon restarts.

    Uses Tier A (Markdown) as the source of truth and optionally Tier B
    (SQLite) for structured fast-retrieval.  Both are written on every
    ``store_finding`` call; retrieval reads from whichever tier is available.
    """

    def __init__(self, memory_root: Path, db_path: Path | None = None) -> None:
        self._memory_root = memory_root
        self._tier_a = TierABackend(memory_root)
        self._db_path = db_path
        self._tier_b: _SQLiteFindingsStore | None = (
            _SQLiteFindingsStore(db_path) if db_path is not None else None
        )
        self._findings: list[dict[str, Any]] = []
        self._total_stored_count: int = 0
        self._loaded_count: int = 0
        self._prior_stored_count: int = 0

    @property
    def _meta_path(self) -> Path:
        return self._memory_root / _FINDINGS_ENTITY_ID / "META.json"

    def _read_meta(self) -> int:
        """Return persisted total_stored_count, or 0 if metadata file absent."""
        if not self._meta_path.exists():
            return 0
        try:
            data = json.loads(self._meta_path.read_text(encoding="utf-8"))
            return int(data.get("total_stored_count", 0))
        except (json.JSONDecodeError, ValueError):
            return 0

    def _write_meta(self) -> None:
        """Persist total_stored_count to disk."""
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)
        self._meta_path.write_text(
            json.dumps({"total_stored_count": self._total_stored_count}),
            encoding="utf-8",
        )

    async def init(self) -> None:
        """Initialize backends and load existing findings from disk."""
        if self._tier_b is not None:
            await self._tier_b.init_db()
        self._findings = self._load_existing_findings()
        self._prior_stored_count = self._read_meta()
        self._total_stored_count = self._prior_stored_count
        self._loaded_count = len(self._findings)
        event_registry.emit(
            "memory.session.initialized",
            payload={
                "memory_root": str(self._memory_root),
                "finding_count": len(self._findings),
                "has_tier_b": self._tier_b is not None,
            },
        )
        logger.info(
            "SessionMemoryManager initialized — %d existing findings loaded",
            len(self._findings),
        )

    def _load_existing_findings(self) -> list[dict[str, Any]]:
        """Load all previously stored findings from Tier A MEMORY.md."""
        mem_path = self._memory_root / _FINDINGS_ENTITY_ID / "MEMORY.md"
        if not mem_path.exists():
            return []

        text = mem_path.read_text(encoding="utf-8")
        findings: list[dict[str, Any]] = []

        # Each finding is stored as a JSON code fence inside a MEMORY.md section.
        # We parse blocks delimited by ```json … ``` markers.
        lines = text.splitlines()
        in_block = False
        block_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```json") and not in_block:
                in_block = True
                block_lines = []
            elif stripped == "```" and in_block:
                in_block = False
                if block_lines:
                    raw = "\n".join(block_lines)
                    try:
                        finding = json.loads(raw)
                        if isinstance(finding, dict):
                            findings.append(finding)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse finding JSON from MEMORY.md")
            elif in_block:
                block_lines.append(line)

        return findings

    async def store_finding(self, finding: dict[str, Any]) -> str:
        """Store a new finding in Tier A and optionally Tier B.

        Returns the finding_id assigned to this finding.
        """
        finding_id = finding.get("finding_id") or str(uuid.uuid4())
        finding = dict(finding)
        finding["finding_id"] = finding_id
        finding.setdefault("stored_at", datetime.now(UTC).isoformat())

        # Tier A: append to MEMORY.md as a JSON fence
        json_block = "```json\n" + json.dumps(finding, default=str) + "\n```"
        entry = MemoryEntry(
            timestamp=datetime.now(UTC),
            category="finding",
            detail=json_block,
        )
        self._tier_a.append_memory(_FINDINGS_ENTITY_ID, entry)

        # Write a minimal SOUL.md if it does not exist yet
        soul_path = self._memory_root / _FINDINGS_ENTITY_ID / "SOUL.md"
        if not soul_path.exists():
            self._tier_a.write_soul(
                _FINDINGS_ENTITY_ID,
                MarkdownDoc(
                    path=soul_path,
                    frontmatter={"entity_type": "findings_store"},
                    content="# Findings\n\nAll lab findings stored here.",
                ),
            )

        # Tier B
        if self._tier_b is not None:
            await self._tier_b.upsert_finding(finding)

        self._findings.append(finding)
        self._total_stored_count += 1
        self._write_meta()

        event_registry.emit(
            "memory.session.finding_stored",
            payload={"finding_id": finding_id},
        )
        logger.debug("Stored finding %s", finding_id)
        return finding_id

    async def retrieve_findings(self, query: str = "") -> list[dict[str, Any]]:
        """Retrieve past findings, optionally filtered by query.

        Prefers Tier B (SQLite) when available; falls back to Tier A.
        """
        if self._tier_b is not None:
            findings = await self._tier_b.list_findings(query=query)
        else:
            findings = self._filter_findings(self._findings, query)

        event_registry.emit(
            "memory.session.findings_retrieved",
            payload={"query": query, "count": len(findings)},
        )
        return findings

    async def close(self) -> None:
        """Close optional Tier B resources."""
        if self._tier_b is not None:
            await self._tier_b.close()

    def _filter_findings(self, findings: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        """Simple substring filter over stringified findings."""
        if not query:
            return list(findings)
        q = query.lower()
        return [f for f in findings if q in json.dumps(f, default=str).lower()]

    def get_retrieval_rate(self) -> float:
        """Compute fraction of previously stored findings retrieved on last init().

        ``_prior_stored_count`` is the count read from persisted META.json during
        ``init()`` — it reflects findings written in *prior* sessions.
        ``_loaded_count`` is the number actually loaded from disk during ``init()``.
        Returns 1.0 when no findings existed before this session started.
        """
        if self._prior_stored_count == 0:
            return 1.0
        return self._loaded_count / self._prior_stored_count

    def is_known_pattern(self, pattern: dict[str, Any]) -> bool:
        """Return True if *pattern* matches any finding already stored.

        Matching is done on ``column_a`` + ``column_b`` + ``pattern_type``
        (the three fields that identify a unique correlation pattern).
        Falls back to exact ``finding_id`` match when those fields are absent.
        """
        col_a = pattern.get("column_a")
        col_b = pattern.get("column_b")
        ptype = pattern.get("pattern_type")

        for f in self._findings:
            if col_a and col_b and ptype:
                if (
                    f.get("column_a") == col_a
                    and f.get("column_b") == col_b
                    and f.get("pattern_type") == ptype
                ):
                    return True
            elif pattern.get("finding_id") and f.get("finding_id") == pattern["finding_id"]:
                return True

        return False


# ---------------------------------------------------------------------------
# Internal SQLite findings store (thin wrapper — not exposed publicly)
# ---------------------------------------------------------------------------


class _SQLiteFindingsStore:
    """Minimal async SQLite store for structured findings."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: object | None = None  # aiosqlite.Connection

    async def init_db(self) -> None:
        import aiosqlite

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(self._db_path))
        conn.row_factory = aiosqlite.Row
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS findings (
                finding_id TEXT PRIMARY KEY,
                data_json  TEXT NOT NULL,
                stored_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_findings_stored
                ON findings(stored_at);
        """)
        await conn.commit()
        self._db = conn

    def _conn(self) -> object:
        if self._db is None:
            raise RuntimeError("_SQLiteFindingsStore not initialized — call init_db() first")
        return self._db

    async def upsert_finding(self, finding: dict[str, Any]) -> None:
        import aiosqlite

        db: aiosqlite.Connection = self._conn()  # type: ignore[assignment]
        finding_id = finding["finding_id"]
        stored_at = finding.get("stored_at", datetime.now(UTC).isoformat())
        await db.execute(
            """
            INSERT INTO findings (finding_id, data_json, stored_at)
            VALUES (?, ?, ?)
            ON CONFLICT(finding_id) DO UPDATE SET
                data_json = excluded.data_json,
                stored_at = excluded.stored_at
            """,
            (finding_id, json.dumps(finding, default=str), stored_at),
        )
        await db.commit()

    async def list_findings(self, query: str = "") -> list[dict[str, Any]]:
        import aiosqlite

        db: aiosqlite.Connection = self._conn()  # type: ignore[assignment]
        async with db.execute("SELECT data_json FROM findings ORDER BY stored_at") as cur:
            rows = await cur.fetchall()

        findings: list[dict[str, Any]] = []
        for row in rows:
            try:
                f = json.loads(row["data_json"])
                findings.append(f)
            except json.JSONDecodeError:
                logger.warning("Corrupt finding record in SQLite")

        if query:
            q = query.lower()
            findings = [f for f in findings if q in json.dumps(f, default=str).lower()]

        return findings

    async def close(self) -> None:
        import aiosqlite

        db: aiosqlite.Connection | None = self._db  # type: ignore[assignment]
        if db is not None:
            await db.close()
            self._db = None
