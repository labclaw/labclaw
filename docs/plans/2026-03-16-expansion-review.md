# LabClaw EXPANSION Review — 2026-03-16

## Review Mode: SCOPE EXPANSION
## Reviewer: Claude Opus 4.6 (CEO Plan Review)
## Status: Complete — all 10 sections reviewed, 0 unresolved decisions

---

## Executive Summary

LabClaw is a well-architected v0.0.10 prototype with solid foundations (5-layer architecture, 7-step scientific method loop, 3-tier memory, 2410 tests at 100% coverage). The EXPANSION review identified **5 critical gaps** that must be fixed before the system can fulfill its "Physical AI for Science" vision:

1. **Missing data pipeline** — device-use and labclaw are not connected (manual CSV drops)
2. **Async time bomb** — daemon uses threads + asyncio.run() that will crash when MCP client is added
3. **Silent data loss** — DataAccumulator's in-memory deque drops old data without warning
4. **No observability** — no metrics, alerts, or structured logging
5. **No feature flags** — can't safely roll out changes

The recommended path: fix infrastructure (P0), then build MCP bidirectional (P1), then observability (P2).

---

## System Audit Findings

| Metric | Value |
|--------|-------|
| labclaw | v0.0.10, 93 source files, ~63K lines, 2410 tests, 100% coverage |
| device-use | MVP, 59 source files, 530 tests |
| Git status | Both repos clean on main, no stashes |
| Open PRs | 3 dependabot (Docker CI), 1 stale `fix/audit-closeout` |
| TODOs/FIXMEs | Zero in Python source |
| Roadmap | v0.0.13 ("MCP Client & Agent Bridge") current, none started |

### Pain Points
- No crash recovery (daemon state in-memory)
- No schema versioning (SQLite `IF NOT EXISTS` only)
- `asyncio.run()` inside threads — fragile
- Thin device-use ↔ labclaw integration (filesystem watches only)
- `lru_cache` singletons with no lifecycle management

### Architecture Strengths
- `core/schemas.py` — clean Pydantic models, StrEnum, event naming validation
- `orchestrator/steps.py` — Protocol-based step abstraction, provenance built in
- device-use GUIDriver ↔ labclaw DevicePlugin adapter — clean protocol boundary

### Anti-Patterns
- `_sync_llm_complete()` — threadpool async/sync bridging
- `Any` type annotations in critical paths (`StepContext.proposals`, `StepContext.patterns`)

---

## Step 0: Nuclear Scope Challenge

### Premise: VALID
LabClaw encodes the scientific method as a computational loop — genuinely novel. The 5-layer architecture is ambitious but well-grounded. Core premise is sound.

### Decision: MCP Bidirectional
Selected as the data pipeline architecture between device-use and labclaw. Aligns with v0.0.13 roadmap and the "Physical AI for Science" vision.

### Dream State (12-month)
```
CURRENT (v0.0.10)              AFTER EXPANSION            12-MONTH IDEAL (v1.0)
─────────────────              ───────────────            ────────────────────
Prototype/demos             →  Production-hardened     →  Multi-lab platform
Manual CSV drops            →  Auto MCP pipeline        Cross-domain discovery
No crash recovery           →  Crash-safe SQLite WAL    Community plugins
Fragile async bridging      →  Proper async arch        Real-time dashboards
MCP server only             →  MCP client + server      Enterprise scale
```

---

## Section 1: Architecture Review (4 issues)

### Issue 1: Device-Use → LabClaw Data Pipeline MISSING (CRITICAL)
**Current**: User manually copies CSV to watched directory
**Proposed**: MCP bidirectional — device-use pushes instrument data to labclaw MCP client
**Decision**: Option B (MCP bidirectional) selected

### Issue 2: Async/Sync Bridging Time Bomb (CRITICAL)
```
daemon thread → asyncio.run() → step.run() → _sync_llm_complete() → ThreadPoolExecutor + asyncio.run()
                ★ Double event loop nesting → WILL crash when MCP client added
```
**Fix**: Rewrite daemon to fully async (asyncio.create_task instead of threads)
**Decision**: Fix as prerequisite to v0.0.13

### Issue 3: Single Points of Failure
- DataAccumulator: deque(maxlen=100K) in memory — data loss on crash, silent eviction
- lru_cache deps: failed init → permanent failure, no reconnect
- Streamlit proc: no auto-restart, no crash detection

### Issue 4: Scaling (10x/100x)
- `get_all_rows()` copies entire deque per cycle — O(N) memory spike
- `PatternMiner.mine()` is O(N² × C²) — minutes at 100K rows
- Rate limit window grows unbounded (50K key eviction)

### Proposed Architecture: Nervous System Model
```
INSTRUMENTS (sensory neurons)  →  DEVICE-USE (peripheral nerves)
    →  LABCLAW INGEST (spinal cord - fast reflexes)
        ├── Sentinel alerts: <1s (reflex arc)
        ├── Discovery: 5min batched (cortex)
        └── Evolution: 30min lazy (prefrontal cortex)
```

---

## Section 2: Error & Rescue Map (10 paths, 5 CRITICAL GAPS)

| METHOD | FAILURE | RESCUED? | USER SEES |
|--------|---------|----------|-----------|
| ScientificLoop.run_cycle | Step raises | Y | Step=failed |
| DataAccumulator.ingest | Parse error | Y | Silent skip |
| DataAccumulator.ingest | Deque full | **N ★** | **Silent data loss** |
| _sync_llm_complete | Event loop conflict | **N ★★** | **Daemon crash** |
| SessionMemory.store | Disk full | **N ★** | Write fails |
| SessionMemory.init | Corrupt JSON | Y | Partial load |
| MCP discover() | Malformed input | **N ★** | 500 error |
| Evolution advance_stage | NaN fitness | **N ★** | Bad promotion |
| GUIDriver.write | VNC disconnect | **N ★** | Error dict |
| enforce_request_security | Auth/rate limit | Y | Clear HTTP error |

### CRITICAL GAPS
1. **RuntimeError from nested event loops** → daemon crash (fixed by async refactor)
2. **DataAccumulator silent eviction** → data lost (fixed by SQLite WAL)
3. **NaN fitness metrics** → garbage evolution (needs NaN guard)
4. **Disk full** → memory writes fail silently (needs health check)
5. **MCP input validation** → no sanitization before mining

---

## Section 3: Security (8 threats, 1 High severity)

| # | Threat | Likelihood | Impact | Mitigated? |
|---|--------|-----------|--------|------------|
| 1 | Streamlit dashboard no auth | Medium | **High** | **NO** |
| 2 | Plugin code unsandboxed | Low | Critical | PARTIAL |
| 3 | EdgeWatcher ingests any file | Low | Medium | NO |
| 4 | LLM prompt injection via data | Medium | Medium | NO |
| 5 | Rate limit memory growth | Low | Low | PARTIAL |
| 6 | API token timing-safe compare | — | — | OK ✅ |
| 7 | Governance RBAC | — | — | OK ✅ |
| 8 | MCP client trust boundary (new) | Medium | Medium | NOT YET |

---

## Section 4: Data Flow & Edge Cases (12 mapped, 6 unhandled)

### Unhandled Edge Cases
1. `POST /api/orchestrator/cycle` — no mutex, concurrent triggers can race
2. `GET /api/memory/search` — no query length limit (10KB+ exploit)
3. `MCP discover()` — no reentrancy guard (called while mining)
4. Evolution advance_stage — NaN fitness not guarded
5. Evolution advance_stage — no lock on concurrent advances
6. Streamlit dashboard — no pagination for 10K+ findings

---

## Section 5: Code Quality (3 DRY violations, 2 under-engineering)

### DRY Violations
1. Provenance entry construction — identical dict in 6 places in steps.py
2. Numeric column detection — duplicated in ObserveStep and ExperimentStep
3. LLM call pattern — identical cost-guard + try/except in Experiment + Conclude

### Under-Engineering
1. `StepContext.proposals: list[Any]` — should be proper Pydantic model
2. `StepContext.patterns: list[PatternRecord | dict]` — `| dict` escape hatch
3. No API request body size limits

---

## Section 6: Test Review

### Current: 2410 tests, 100% coverage, 46 BDD features
### Gaps for EXPANSION:
- Daemon integration test (full lifecycle)
- MCP client (all new)
- Async daemon (all new)
- SQLite WAL accumulator (all new)
- Chaos tests (kill mid-write, corrupt WAL)

---

## Section 7: Performance

| Hot Path | Current | At 10x | Fix |
|----------|---------|--------|-----|
| PatternMiner.mine() | O(N² × C²) | ~10s at 100K | Windowed mining |
| DataAccumulator.get_all_rows() | O(N) copy | ~100MB | SQLite LIMIT |
| SessionMemory._load_existing | Linear scan | Slow at 10K | SQLite-first |
| _rate_limit_window | O(1) | 50K eviction | TTL cache |

---

## Section 8: Observability (8 gaps)

| Missing | Impact | Effort |
|---------|--------|--------|
| Structured JSON logging | Can't parse at scale | S |
| Prometheus metrics | Can't monitor | M |
| Instrument health metrics | Blind to disconnects | S |
| Discovery cycle metrics | No trend data | S |
| Evolution metrics | No fitness tracking | S |
| MCP client call metrics | No latency/error data | M |
| Alert rules | Nobody knows breaks | M |
| Daemon heartbeat | Is it alive? | S |

---

## Section 9: Deployment (4-phase rollout)

```
Phase 1: Async Daemon + SQLite WAL (v0.0.11)
Phase 2: MCP Bidirectional (v0.0.13)
Phase 3: Observability + Dashboard (v0.0.14)
Phase 4: Docker + Crash Recovery (v0.0.15)
```

Rollback: Git revert + restart. <1 minute recovery.

---

## Section 10: Long-Term Trajectory

- Reversibility: 4/5
- Technical debt: 3 items (MCP dep, SQLite complexity, async complexity)
- Platform potential: HIGH — MCP makes labclaw a universal lab intelligence hub
- 12-month: multi-lab with cross-domain discovery

---

## Priority Roadmap

### P0 — Prerequisites (before v0.0.13)
| # | Item | Effort | Depends On |
|---|------|--------|------------|
| 1 | Async daemon rewrite | M (2-3 days) | — |
| 2 | SQLite WAL data accumulator | M (2-3 days) | — |

### P1 — v0.0.13 Deliverables
| # | Item | Effort | Depends On |
|---|------|--------|------------|
| 3 | MCP bidirectional client | L (5-7 days) | #1 |
| 4 | device-use → labclaw auto data pipeline | M (3 days) | #3 |

### P2 — v0.0.14
| # | Item | Effort | Depends On |
|---|------|--------|------------|
| 5 | Prometheus metrics + structured logging | M (3 days) | — |
| 6 | Type safety + NaN guard + concurrency guard | S (1 day) | — |

### Delight Items (v0.0.14+)
| # | Item | Effort |
|---|------|--------|
| 7 | Instrument heartbeat dashboard | S (30 min) |
| 8 | Provenance visualization | S (30 min) |
| 9 | Daily lab digest | S (30 min) |
| 10 | Live discovery sparkline | S (30 min) |
| 11 | Cross-instrument correlation alerts | M (2 hrs) |

---

## Key Decisions Made
1. **MCP bidirectional** for device-use ↔ labclaw data pipeline
2. **Async daemon** as prerequisite (not deferrable)
3. **SQLite WAL** for crash-safe data accumulation
4. **SCOPE EXPANSION** mode — build the cathedral

## Unresolved Decisions
None — all questions answered.
