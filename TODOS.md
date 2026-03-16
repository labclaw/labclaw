# TODOS.md — LabClaw

> Generated from EXPANSION Review 2026-03-16. Review: `docs/plans/2026-03-16-expansion-review.md`

## P0 — Prerequisites (before v0.0.13)

### TODO-1: Async Daemon Rewrite
- **What:** Rewrite `daemon.py` to use `asyncio.create_task()` instead of `threading.Thread`. Remove `_sync_llm_complete()` from `steps.py`. All steps naturally async.
- **Why:** Current daemon uses `asyncio.run()` inside threads which creates nested event loops. This WILL crash when MCP client is added (MCP SDK is async). The `_sync_llm_complete()` function uses `ThreadPoolExecutor + asyncio.run()` — double nesting, deadlock risk on GIL contention.
- **Pros:** Eliminates event loop bomb, enables MCP client, simplifies code (no sync/async bridging), better resource usage (no thread overhead).
- **Cons:** ~2-3 day effort, touches daemon.py + steps.py + tests. All daemon tests need async rewrite.
- **Context:** `daemon.py` lines 228-239 create `threading.Thread` for discovery/evolution. `steps.py` lines 26-45 has `_sync_llm_complete()`. Both need replacement. The uvicorn server can use `uvicorn.Server` with async startup.
- **Effort:** M (2-3 days)
- **Priority:** P0
- **Depends on:** Nothing
- **Blocks:** TODO-3 (MCP client)

### TODO-2: SQLite WAL Data Accumulator
- **What:** Replace `DataAccumulator`'s in-memory `deque(maxlen=100_000)` with SQLite WAL-mode table. Add configurable retention policy (time-based or row-count with explicit archival).
- **Why:** Current deque silently drops old rows when full (100K limit). Data is lost on daemon crash. No query capability beyond `get_all_rows()` which copies entire deque. Real labs generate continuous data — silent eviction is unacceptable.
- **Pros:** Crash-safe, queryable, configurable retention, no silent data loss, supports windowed mining queries.
- **Cons:** ~2-3 day effort, adds SQLite dependency to hot path, write latency (~5ms per insert vs ~0ms for deque append).
- **Context:** `daemon.py` lines 58-132 define `DataAccumulator`. Key methods: `ingest_file()`, `get_all_rows()`, `total_rows`. Replace `deque` with `aiosqlite` table: `CREATE TABLE data_rows (id INTEGER PRIMARY KEY, instrument_id TEXT, data_json TEXT, ingested_at TEXT)`. Add indexes on `instrument_id` and `ingested_at`. WAL mode for concurrent reads during mining.
- **Effort:** M (2-3 days)
- **Priority:** P0
- **Depends on:** TODO-1 (async daemon, for aiosqlite integration)
- **Blocks:** Nothing directly, but enables crash recovery (v0.0.15)

---

## P1 — v0.0.13 Deliverables

### TODO-3: MCP Bidirectional Client
- **What:** Add MCP client capability to labclaw. LabClaw discovers and calls external MCP tools: device-use instruments (data retrieval), ToolUniverse (600+ scientific tools), BioMCP (PubMed, ClinicalTrials, MyVariant). Add OrchestratorAgent that decides when to call external tools during the scientific loop.
- **Why:** Currently labclaw is MCP server only — it exposes tools but can't use external ones. The v0.0.13 roadmap requires bidirectional MCP for the "AI scientist" vision. Without it, labclaw can't autonomously fetch literature context, access external analysis tools, or receive instrument data in real-time.
- **Pros:** Enables autonomous scientific research, connects to 600+ tools, enables device-use data pipeline, positions labclaw as universal lab intelligence hub.
- **Cons:** Large effort (~5-7 days), adds MCP client SDK dependency, new trust boundary (external tool responses need validation), increases system complexity.
- **Context:** `mcp/server.py` already uses `FastMCP` for server side. Client side: use `mcp` SDK's client capabilities. New file: `mcp/client.py`. Integration with orchestrator: new `OrchestratorAgent` class that wraps `ScientificLoop` with external tool calling. See roadmap in `docs/roadmap.md` lines 37-43.
- **Effort:** L (5-7 days)
- **Priority:** P1
- **Depends on:** TODO-1 (async daemon — MCP client is async)
- **Blocks:** TODO-4 (data pipeline)

### TODO-4: Device-Use → LabClaw Auto Data Pipeline
- **What:** Device-use pushes instrument data to labclaw via MCP events. When NMR processes a spectrum or plate reader completes a read, the result automatically flows to labclaw's DataAccumulator. No more manual CSV drops.
- **Why:** The device-use ↔ labclaw integration is currently manual (user copies files). For "Physical AI for Science", instruments must feed data to the brain automatically. This is the critical link between "hands" and "brain".
- **Pros:** Real-time instrument data ingestion, no manual steps, enables cross-instrument correlation, completes the autonomous loop.
- **Cons:** ~3 day effort, requires both device-use and labclaw changes, needs data format contract between instruments and discovery engine.
- **Context:** device-use `integrations/labclaw.py` already has `GUIDriver` + `DeviceUsePlugin`. Add MCP event emission: when `orchestrator.py` completes a pipeline step with data output, emit MCP event `instrument.data.ready` with structured payload. Labclaw MCP client subscribes and routes to `DataAccumulator.ingest()`.
- **Effort:** M (3 days)
- **Priority:** P1
- **Depends on:** TODO-3 (MCP client)
- **Blocks:** Delight #11 (cross-instrument correlation)

---

## P2 — v0.0.14

### TODO-5: Prometheus Metrics + Structured Logging
- **What:** Add `/api/metrics` Prometheus endpoint. Convert Python logging to structured JSON (structlog or python-json-logger). Metrics: discovery cycle duration, patterns/cycle, LLM API calls/cost, instrument health, daemon heartbeat, memory growth, evolution fitness trends.
- **Why:** Zero observability today. No way to know if daemon is healthy, if discovery is working, or if LLM costs are rising. Required before real lab deployment.
- **Pros:** Grafana dashboards, alerting, cost tracking, trend analysis.
- **Cons:** ~3 day effort, adds prometheus_client dependency, structured logging changes all log output format.
- **Context:** `api/routers/health.py` already exists. Add `api/routers/metrics.py` with prometheus_client. Add `logging_config.py` structured formatter. Key metrics: `labclaw_discovery_cycles_total`, `labclaw_patterns_found`, `labclaw_llm_calls_total`, `labclaw_llm_tokens_total`, `labclaw_data_rows_total`, `labclaw_findings_total`.
- **Effort:** M (3 days)
- **Priority:** P2
- **Depends on:** Nothing
- **Blocks:** Nothing

### TODO-6: Type Safety + Guards
- **What:** (a) Replace `StepContext.proposals: list[Any]` and `StepContext.patterns: list[PatternRecord | dict]` with proper Pydantic models. (b) Add NaN guard in `EvolutionEngine.measure_fitness()` — reject NaN metrics. (c) Add mutex on `POST /api/orchestrator/cycle` to prevent concurrent discovery triggers. (d) Add request body size limits on API endpoints.
- **Why:** `Any` types hide data structure bugs. NaN fitness can promote garbage evolution candidates. Concurrent discovery triggers can race. Large payloads can exhaust memory.
- **Pros:** Catches bugs at type boundary, prevents NaN evolution corruption, prevents concurrent races.
- **Cons:** ~1 day effort, may require updating tests that pass dicts where models are expected.
- **Context:** `orchestrator/steps.py` lines 66-78 define `StepContext`. `evolution/engine.py` `measure_fitness()` needs `math.isnan()` check. `api/routers/orchestrator.py` needs `asyncio.Lock()`.
- **Effort:** S (1 day)
- **Priority:** P2
- **Depends on:** Nothing
- **Blocks:** Nothing

---

## Delight Items (v0.0.14+)

### DELIGHT-7: Instrument Heartbeat Dashboard
- **What:** Device-use pings each instrument every 30s. Labclaw dashboard shows green/yellow/red status grid with last-seen timestamp. Scientists see at a glance which instruments are online.
- **Effort:** S (30 min)
- **Priority:** P3
- **Depends on:** TODO-4 (data pipeline)

### DELIGHT-8: Provenance Visualization
- **What:** "Why did labclaw discover this?" button — one-click provenance chain visualization from finding → hypothesis → patterns → raw data. Uses existing `ProvenanceChain` in `ConcludeStep`.
- **Effort:** S (30 min)
- **Priority:** P3
- **Depends on:** Nothing (provenance chains already exist)

### DELIGHT-9: Daily Lab Digest
- **What:** Automated morning summary via email/Slack webhook: "Yesterday: 3 new patterns, 1 confirmed hypothesis, 2 instruments used. Top finding: [X]."
- **Effort:** S (30 min)
- **Priority:** P3
- **Depends on:** TODO-5 (metrics for aggregation)

### DELIGHT-10: Live Discovery Sparkline
- **What:** Real-time Streamlit visualization showing patterns emerging as data accumulates. Scrolling timeline: each cycle is a dot, size = patterns found, color = significance.
- **Effort:** S (30 min)
- **Priority:** P3
- **Depends on:** Nothing

### DELIGHT-11: Cross-Instrument Correlation Alerts
- **What:** When labclaw detects correlation between data from TWO different instruments (e.g., NMR shift ↔ plate reader absorbance), flag as "cross-instrument discovery" with special highlighting. THE killer feature of the platform.
- **Effort:** M (2 hours)
- **Priority:** P3
- **Depends on:** TODO-4 (data pipeline with instrument_id tagging)
