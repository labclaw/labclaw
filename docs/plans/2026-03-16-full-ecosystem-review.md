# LabClaw Ecosystem — Full EXPANSION Review Summary

**Date:** 2026-03-16 | **Mode:** SCOPE EXPANSION (all 5 repos) | **Status:** Complete

## Executive Dashboard

| Repo | Version | Tests | Coverage | BDD | Top Issue | Readiness |
|------|---------|-------|----------|-----|-----------|-----------|
| **labclaw** | v0.0.10 | 2410 | 100% ✅ | 46 features ✅ | Async daemon + data pipeline | 75% |
| **device-use** | v0.1.0 | 530 | Not enforced ★ | **0 features** ★★ | BDD + async + Safety L3 | 60% |
| **device-skills** | v0.1.0 | 146 | Not enforced ★ | Partial ★ | Coverage gate + cross-repo tests | 80% |
| **labwork** | v0.1.0-α | 500 | ~70% | BDD-style ✅ | 86 ESLint errors + sandbox | 70% |
| **labwork-web** | v0.1.0 | 59 | N/A | BDD names ✅ | No docs + monolithic app.py | 75% |
| **Total** | — | **3,645** | — | — | — | — |

## Unified Priority Roadmap

### Phase 0: Governance & Infrastructure (parallel, 2 weeks)

```
labclaw:      TODO-1 Async daemon          TODO-2 SQLite WAL
device-use:   DU1 BDD tests + coverage     DU2 Async-first refactor
device-skills: DS1-DS5 Coverage + BDD + cross-repo tests + topspin user/
labwork:      LW1 Fix 86 ESLint errors     LW2 Re-enable sandbox
labwork-web:  LWW1 Create CLAUDE.md + README
```

### Phase 1: Core Integration (sequential, 2-3 weeks)

```
labclaw:      TODO-3 MCP bidirectional client
device-use:   DU3 Safety L3 vision verification
              DU4 MCP event push to labclaw  ←→  labclaw TODO-4 data pipeline
labwork:      LW3 IPC type safety           LW4 Offline degradation
labwork-web:  LWW2 Refactor app.py          LWW3 Input validation
```

### Phase 2: Polish & Expansion (ongoing)

```
labclaw:      TODO-5 Prometheus metrics     TODO-6 Type safety
device-use:   DU5 Operator auto-negotiation DU6 Web cleanup
device-skills: DS6 Validation layer         DS7 Structured logging
labwork:      LW5 E2E tests                LW6 Auto-update
labwork-web:  LWW4 Session persistence      LWW5 Token counting
```

## Cross-Repo Dependency Map

```
                    PHASE 0 (parallel)
                    ══════════════════
  labclaw TODO-1 ──────────────────── device-use DU2
  (async daemon)    same async model   (async-first)
        │                                   │
        ▼                                   ▼
                    PHASE 1 (sequential)
                    ════════════════════
  labclaw TODO-3 ◄──────────────────── device-use DU4
  (MCP client)      needs client first  (MCP push)
        │
        ▼
  labclaw TODO-4 ═══════════════════ device-use DU4
  (data pipeline)   TWO SIDES OF      (MCP push)
                    SAME FEATURE

  device-skills DS5 ──────► device-use + labclaw
  (cross-repo tests)        (verifies compatibility)
```

## Key Architectural Decisions (All Repos)

1. **MCP bidirectional** — labclaw is both MCP server AND client
2. **Async-first** — both labclaw and device-use converge on asyncio
3. **SQLite WAL** — labclaw data accumulation crash-safe
4. **Safety L3 vision** — device-use VLM-based screen verification
5. **Keep labwork-web separate** — different stack, users, deployment
6. **BDD mandatory** — enforce across all 5 repos (device-use is 0, critical)

## Effort Estimates

| Phase | Total Effort | Calendar Time | Parallelism |
|-------|-------------|---------------|-------------|
| P0 | ~40 person-days | 2 weeks | 5 repos parallel |
| P1 | ~30 person-days | 2-3 weeks | 2 tracks (labclaw+DU, labwork+LWW) |
| P2 | ~20 person-days | Ongoing | Per-repo |
| **Total to v0.0.13** | **~70 person-days** | **~6 weeks** | — |

## Critical Findings Across Ecosystem

### Security
| Issue | Repo | Severity |
|-------|------|----------|
| Streamlit dashboard no auth | labclaw | HIGH |
| Electron sandbox disabled | labwork | HIGH |
| CORS allow_origins=["*"] | device-use | MEDIUM |
| Safety L3 stub (always passes) | device-use | HIGH (physical) |
| No CSP headers | labwork | MEDIUM |
| Hardcoded password (demo) | device-skills | LOW |

### Governance
| Issue | Repo | Severity |
|-------|------|----------|
| 0 BDD tests | device-use | CRITICAL |
| No coverage enforcement | device-use, device-skills | HIGH |
| 86 ESLint errors blocking CI | labwork | HIGH |
| No CLAUDE.md | labwork-web | MEDIUM |

### Architecture
| Issue | Repo | Severity |
|-------|------|----------|
| No device-use → labclaw data pipeline | ecosystem | CRITICAL |
| Async/sync split (event loop bomb) | labclaw, device-use | CRITICAL |
| DataAccumulator silent data loss | labclaw | HIGH |
| Operator hierarchy incomplete (L1, L2 stubs) | device-use | MEDIUM |
| 939-line HTML string in Python | device-use | LOW |
| 1179-line monolithic app.py | labwork-web | LOW |
