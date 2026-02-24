# Changelog

## 0.0.1 — 2026-02-20

First production release. All 5 layers functional, deployed on DO server.

### Security

- API bound to `127.0.0.1` (access via Tailscale mesh / SSH tunnel)
- Path traversal protection on session recording endpoints
- Service runs as dedicated `labclaw` user (non-root)
- Proper SIGTERM signal handling with graceful shutdown
- `EnvironmentFile` support for secrets in systemd service

### Reliability

- Bounded all in-memory collections to prevent OOM:
  - `DataAccumulator._rows`: deque(maxlen=100,000)
  - `EdgeWatcher._detected_files`: deque(maxlen=10,000)
  - `SessionChronicle._sessions`: max 10,000 with LRU eviction
  - `EvolutionEngine._cycles`: max 1,000 with eviction
  - `TierBBackend._nodes`: max 50,000 with oldest-eviction and 80% warning
- Thread-safe EventRegistry (lock on subscribe + copy-on-iterate in emit)
- TOCTOU race fix in DataAccumulator file ingestion
- Thread-safe `set_memory_root()` / `set_data_dir()` in deps.py
- Thread-safe EdgeWatcher file detection callback

### Algorithm Correctness

- Fixed anomaly detection index mapping (filtered vs. original data)
- P-value approximation uses `math.erfc` (complementary error function)
- PCA deflation applied after each eigenvector (not during power iteration)
- K-means clamps `k = min(n_clusters, len(data))` instead of returning empty
- Bootstrap CI uses actual trained model (RF/LR), not always OLS fallback
- Evolution cycles re-mine with candidate config diff (no fake 2% improvement)

### Polish

- Memory write failures logged at WARNING (not DEBUG)
- Dashboard stderr captured to `logs/dashboard.log`
- Anchored rsync exclude patterns in deploy.sh
- Dynamic remote IP in deploy banner
- Memory router search route declared before `{entity_id}` routes (no collision)
- CLI port argument validated with helpful error message
- Evolution regression check logs warning on missing metrics
- Hypothesis generator parameter renamed from `input` to `hypothesis_input`
- Numeric column detection samples first 5 rows with majority rule
- Migrated enums from `(str, Enum)` to `StrEnum` (Python 3.11+)

### Infrastructure

- 115 tests (feature, integration, unit) — all passing
- Ruff lint clean (`E`, `F`, `I`, `N`, `W`, `UP` rules)
- systemd service with auto-restart, journal logging
- One-command deployment via `deploy/deploy.sh`
- Demo data generator for fresh deployments

### Architecture (5 layers)

- **L1 Hardware:** Device registry, safety checks, interface types
- **L2 Infra:** FastAPI REST API, event bus, gateway, Streamlit dashboard
- **L3 Engine:** Pattern mining, anomaly detection, hypothesis generation, predictive modeling, unsupervised clustering/PCA, session chronicle, quality sentinel, statistical validation
- **L4 Memory:** Tier A (markdown SOUL.md/MEMORY.md), Tier B (in-memory knowledge graph with CRUD + search)
- **L5 Persona:** Digital staff (intern/analyst/specialist), promotion/demotion gates, self-evolution engine (7-step cycle with auto-rollback)
