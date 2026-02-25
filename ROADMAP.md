# LabClaw Roadmap

> Detailed plan: [docs/plans/2026-02-24-v004-to-v010-roadmap.md](docs/plans/2026-02-24-v004-to-v010-roadmap.md)

## v0.0.4 — Foundation (C5: REPRODUCE)

- TDD + BDD dual-layer testing, 100% coverage
- End-to-end pipeline on synthetic behavioral data
- `labclaw pipeline --once` CLI for single-cycle execution
- Deterministic mode (`--seed 42`) for reproducibility

## v0.0.5 — First Discovery (C1: DISCOVER)

- Real behavioral data through the pipeline
- Claude API hypothesis generation with cost guard (`--max-llm-calls N`)
- First real ValidationReport with p-values
- First automated MEMORY.md entry from discovery

## v0.0.6 — Self-Evolution (C2: EVOLVE)

- 10+ evolution cycles on real data with fitness tracking
- Ablation framework: `labclaw ablation --no-evolution`
- Statistical comparison: full system vs no-evolution (paired t-test)
- Persona promotion verification (intern -> analyst)

## v0.0.7 — Persistent Memory (C3: REMEMBER)

- Cross-session memory: restart -> query returns past findings
- Pattern deduplication: skip already-known patterns
- Memory-assisted hypothesis: LLM prompt includes past findings

## v0.0.8 — Provenance & Interfaces (C4: TRACE)

- Full provenance chains: RecordingNode -> AnalysisNode -> FindingNode
- NWB export: `labclaw export --format nwb --session X`
- MCP server hardening with integration tests
- REST API version tag (`/api/v0/`)

## v0.0.9 — Production Stability

- Daemon 24h+ soak test (memory stable, no crashes)
- Crash recovery from Tier A/B + evolution_state.json
- Structured JSON logging
- Enhanced `/health` endpoint (component status, last cycle time)

## Planned: v0.1.0 — Paper Release

v0.1.0 will be the version cited in the paper. All 5 capabilities proven by integration tests and BDD scenarios.

| Capability | Criteria | Status |
|-----------|---------|--------|
| C1 DISCOVER | Real data -> finding with p < 0.05 | Proven |
| C2 EVOLVE | 10 cycles, fitness +15%, ablation significant | Proven |
| C3 REMEMBER | Restart -> 90% findings retrievable | Proven |
| C4 TRACE | 100% findings have complete provenance | Proven |
| C5 REPRODUCE | Same input + seed = same output | Proven |

Deliverables: ablation study, 4 publication figures, `labclaw reproduce` command, demo dataset, PyPI package, Docker image, MkDocs site.
