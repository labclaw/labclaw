# Deep Audit Report

Date: 2026-03-13
Workspace: `/Users/robert/workspace/36-labclaw`
Mode: code audit + runtime verification + project-record audit

This report audits and tracks subsequent fix work for:
- local repos
- local worktrees
- Claude project records
- Codex global traces
- git history and current working-tree state

This document began as a pure audit. It now also records the first repair batches completed on 2026-03-13, including exact commands and verification results.

## Audit Approach

This audit did not rely on a single source of truth.

Evidence was collected from:
- local repo docs: `CLAUDE.md`, `docs/progress.md`, repo-specific docs
- global Claude records: `~/.claude/projects/-Users-robert-workspace-36-labclaw/`
- global Claude task logs: `~/.claude/tasks/<session-id>/`
- global Codex traces: `~/.codex/history.jsonl`
- git history in each child repo
- actual test runs and targeted runtime reproductions

Multi-agent support was used during the audit:
- subagents were dispatched for parallel code/review passes
- the strongest concrete findings below are still backed by main-thread verification commands
- some additional spawned agents failed due model availability limits, so final conclusions below prefer directly verified evidence

## Source Of Truth Map

### Most authoritative project-memory files

1. Global Claude project memory
   - `~/.claude/projects/-Users-robert-workspace-36-labclaw/memory/MEMORY.md`
   - `~/.claude/projects/-Users-robert-workspace-36-labclaw/memory/progress.md`

2. Local workspace governance
   - `/Users/robert/workspace/36-labclaw/CLAUDE.md`

3. Repo-local progress files
   - `/Users/robert/workspace/36-labclaw/device-use/docs/progress.md`
   - `/Users/robert/workspace/36-labclaw/wt-device-use-e2e/docs/progress.md`

4. Claude session/task evidence
   - `~/.claude/projects/-Users-robert-workspace-36-labclaw/*.jsonl`
   - `~/.claude/tasks/c326d3df-61cf-430a-9f51-2eb45ed3ddce/1.json`

5. Codex global traces
   - `~/.codex/history.jsonl`

### What these records actually contain

- `~/.claude/projects/-Users-robert-workspace-36-labclaw/memory/MEMORY.md` is the highest-signal workspace summary.
  - It records current status, architecture, environment, priorities, CUA/VNC lessons, and demo direction.
  - Example: it claims `device-use v0.1.0 on main — operators merged (PR #3+#5), 522 tests passing`.

- `~/.claude/projects/-Users-robert-workspace-36-labclaw/memory/progress.md` is the richest session log.
  - It records session-by-session milestones, PRs, merged branches, review pipelines, and decision logs.
  - It is useful, but it is not automatically synchronized with actual repo state.

- Local repo progress files are materially stale in places.
  - `device-use/docs/progress.md`
  - `wt-device-use-e2e/docs/progress.md`
  - Both still describe `feat/ai-scientist-loop` and a 442/451 test baseline from 2026-03-11.

- Claude task files prove that project management state exists outside the repos.
  - Example task:
    - `~/.claude/tasks/c326d3df-61cf-430a-9f51-2eb45ed3ddce/1.json`
    - Description: “Check current labwork-web state, recent commits, open issues, and understand what's been built vs what's needed for demo”

- Codex history confirms operational work not cleanly reflected in repo docs.
  - `~/.codex/history.jsonl` contains the recent `labclaw-video` iteration and VNC/TopSpin reproducibility work.

## Current Git Snapshot

The workspace root is not a git repo.

Child repo states at audit time:

| Repo | Branch | Head | Upstream | Working tree |
|------|--------|------|----------|--------------|
| `labclaw` | `main` | `854e499` | `origin/main` | clean |
| `labwork` | `main` | `48f5d65` | `origin/main` | clean |
| `labwork-web` | `main` | `bbb9643` | `origin/main` | dirty |
| `device-use` | `main` | `1393e73` | `origin/main` | dirty, ahead 1 |
| `device-skills` | `main` | `86cc35a` | `origin/main` | dirty |
| `wt-device-use-e2e` | `feat/e2e-closed-loop` | `5727da0` | none | dirty |

Working-tree drift:

- `labwork-web`
  - untracked: `.mcp.json`, `demo-mockup.html`, `docs/`, `public/`, `screenshots/`

- `device-use`
  - modified: `CLAUDE.md`, `demos/demo_full_experiment.py`
  - untracked: `docs/JAVA_AX_INVESTIGATION.md`, `docs/MACOS_AUTOMATION_RESEARCH.md`, `docs/acceptance-criteria.md`, `docs/superpowers/`, `scripts/`

- `device-skills`
  - untracked: `uv.lock`

- `wt-device-use-e2e`
  - untracked: `demos/25_vnc_cu_demo.py`, `demos/record_demo.py`, `demos/record_demo_hq.py`, `demos/record_full_showcase.py`, `demos/record_showcase.py`, `docs/superpowers/`

## Verification Commands Run

### Repo tests

- `labclaw`
  - `cd labclaw && PYTHONPATH=src .venv/bin/python -m pytest -q`
  - Result: `2407 passed, 23 skipped`

- `labwork`
  - `cd labwork && npm test -- --run`
  - Result: `82` files passed, `491` tests passed

- `labwork-web`
  - `cd labwork-web && npx playwright test`
  - Result: `25 failed, 1 passed`

- `device-use`
  - `cd device-use && .venv/bin/python -m pytest -q`
  - Result: `11 failed, 519 passed, 1 skipped`

- `device-skills`
  - `cd device-skills && pytest -q`
  - Result: collection failure, `ModuleNotFoundError: No module named 'numpy'`

### Targeted runtime repros

- `labclaw` task queue race
  - `TaskQueue.dequeue()` called concurrently via `asyncio.gather(...)`
  - Result: both consumers received the same `task_id`

- `device-use` conftest collision
  - `python` with `device-skills` on `sys.path` resolves `import conftest` to:
    - `/Users/robert/workspace/36-labclaw/device-skills/conftest.py`

### Environment checks

- `device-use/.venv/bin/pytest` has stale shebang:
  - `#!/Users/robert/workspace/34-device-use/.venv/bin/python3.14`

## Executive Summary

What is healthy:
- `labclaw` has the strongest raw test baseline, but it still contains hidden concurrency/caching correctness issues not covered by current tests.
- `labwork` test suite is healthy, but the runtime security boundary is materially weaker than the project docs imply.

What is weakest:
- `labwork-web` has severe record drift: repo history and memory files say major reviews passed, but the current Playwright E2E suite is largely dead.
- `wt-device-use-e2e` is not yet a deterministic demo harness, despite project memory describing reproducible demo progress.
- `device-use` has both test-isolation and packaging-entry issues; test counts look good, but the failing slice is not cosmetic.

Highest-risk meta finding:
- project memory is useful but not trustworthy on its own
- repo-local progress files are stale
- git state, test state, and memory state are no longer aligned

## Findings

### P1 — `labwork` runtime security boundary is explicitly weakened

Status:
- verified by source inspection
- not a hypothetical hardening gap

Evidence:
- `labwork/src/main/index.ts:167-171`
  - Browser window created with `sandbox: false`
- `labwork/src/main/index.ts:483-486`
  - startup forcibly sets `configStore.set('sandboxEnabled', false)`

Impact:
- even if a user expects sandboxing to be enabled, the app resets it off at startup
- this weakens the desktop trust boundary and makes downstream path and command controls more important

### P1 — `labwork` path-boundary checks use unsafe prefix matching

Status:
- verified by source inspection

Evidence:
- `labwork/src/main/tools/tool-executor.ts:67-70`
- `labwork/src/main/sandbox/path-resolver.ts:108-117`

Issue:
- both checks rely on `startsWith(...)`
- a sibling path such as `/Users/robert/workspace-escape` can match a mount root like `/Users/robert/workspace`

Impact:
- workspace isolation can be bypassed by prefix-collision paths
- this is a classic sandbox boundary bug

### P1 — `labwork` remote gateway defaults allow unauthenticated WebSocket access in allowlist mode

Status:
- verified by source inspection

Evidence:
- `labwork/src/main/remote/types.ts:525-533`
  - empty allowlist explicitly means allow everyone
- `labwork/src/main/remote/gateway.ts:342-345`
  - allowlist mode returns `true` when list is empty
- `labwork/src/main/remote/gateway.ts:693-700`
  - non-token WS modes mark client authenticated without a token
- `labwork/src/main/remote/gateway.ts:704-716`
  - authenticated client proceeds into message routing

Impact:
- if gateway is enabled with default allowlist config, arbitrary WS clients can authenticate and send messages

### P1 — `labwork-web` exposes mutable unauthenticated endpoints on `0.0.0.0`

Status:
- verified by source inspection

Evidence:
- `labwork-web/app.py:366-375`
  - `/api/config` mutates config without auth
- `labwork-web/app.py:520-525`
  - `/vm/frame` accepts raw screenshot body into process memory
- `labwork-web/app.py:818-840`
  - `/ws/chat/{session_id}` accepts and creates sessions without auth
- `labwork-web/app.py:1147-1149`
  - app binds `host="0.0.0.0"`

Impact:
- on any reachable network, another host can mutate config, abuse chat sessions, or push frame payloads

Note:
- prior review notes in `~/.claude/.../progress.md` accepted unauthenticated `/api/config` as “localhost only”
- the current code is not localhost-only at process bind level

### P1 — `labwork-web` E2E suite is functionally broken due to test/UI contract drift

Status:
- verified by running Playwright
- verified by source inspection

Runtime result:
- `25 failed, 1 passed`

Root cause evidence:
- `labwork-web/tests/helpers/mock-ws.ts:109-111`
  - tests still drive `#prompt-input` and `#btn-send`
- `labwork-web/frontend/src/App.tsx:342-359`
  - current input/button render with no such ids
- `labwork-web/tests/e2e/topbar-status.spec.ts` expects:
  - `#topspin-status`
  - `#device-use-status`
  - `#labclaw-status`
  - `#elapsed-time`
  - `#btn-settings`
  - `.status-dot`
  - `.svc-status`
  - `.topbar-right`
- current UI topbar implementation at `frontend/src/App.tsx:116-150` does not expose those selectors

Impact:
- the suite does not currently validate responsiveness, timers, tool-detail persistence, or status indicators
- it mostly validates outdated DOM assumptions

### P1 — `labwork-web` Playwright harness is pinned to one developer machine layout

Status:
- verified by source inspection

Evidence:
- `labwork-web/playwright.config.ts:15-16`
  - hardcoded Python path:
    - `/Users/robert/workspace/36-labclaw/device-use/.venv/bin/python`
  - hardcoded `cwd`:
    - `/Users/robert/workspace/36-labclaw/worktrees/wt-labwork-web-tests`

Impact:
- the test harness is not portable
- even a correct test suite would depend on one exact local folder structure

### P1 — `device-use` test failures are real and concentrated, not random

Status:
- verified by running full pytest and focused subsets

Runtime result:
- full run: `11 failed, 519 passed, 1 skipped`

Failure cluster A:
- `device-use/tests/test_e2e.py:25-27`
- `device-use/tests/test_labclaw.py:184-186`
- helpers do `from conftest import _create_minimal_png`
- under the current workspace, this fails or resolves unpredictably

Observed behavior:
- failing tests report `ModuleNotFoundError: No module named 'conftest'`
- with `device-skills` on `sys.path`, `import conftest` resolves to `/Users/robert/workspace/36-labclaw/device-skills/conftest.py`

Impact:
- test correctness depends on import path accidents
- the same tests can fail differently depending on workspace layout

Failure cluster B:
- `device-use/tests/test_e2e.py:286-326`
- subprocess CLI tests call:
  - `python -m device_use.cli ...`
- but they do not ensure the package is installed or `src/` is on the subprocess path

Observed behavior:
- `ModuleNotFoundError: No module named 'device_use'`

Impact:
- these tests are not validating CLI behavior
- they are validating an environment setup assumption that is not encoded in the test

### P1 — `device-use` environment is partially broken even before tests run

Status:
- verified by environment inspection

Evidence:
- `device-use/.venv/bin/pytest` shebang points to old workspace:
  - `#!/Users/robert/workspace/34-device-use/.venv/bin/python3.14`

Impact:
- direct `./.venv/bin/pytest` invocation fails on this machine state
- scripts and docs that assume the repo-local virtualenv is self-contained are misleading

### P1 — `device-skills` makes optional device dependencies effectively mandatory at collection time

Status:
- verified by running pytest
- verified by source inspection

Runtime result:
- collection aborts with `ModuleNotFoundError: No module named 'numpy'`

Evidence:
- `device-skills/conftest.py:64-70`
  - loads every device submodule eagerly
- `device-skills/conftest.py:88-96`
  - registers every hyphenated device directory during collection
- `device-skills/devices/biotek-gen5/visualizer.py`
  - imports `numpy`, causing collection abort when dep is absent

Impact:
- a missing optional dependency for one device prevents the entire suite from collecting
- this is a packaging/test isolation defect, not just a missing extra

### P1 — `device-skills` import story still depends on pytest shim logic

Status:
- verified by source inspection
- aligns with project-memory note about hyphen/underscore import mismatch

Evidence:
- `device-skills/pyproject.toml:63-66`
  - entry points for `devices.biotek_gen5` and `devices.bruker_topspin` are commented out
- `device-skills/devices/biotek-gen5/__init__.py:5-16`
  - package behavior changes depending on whether `__package__` is set
- `device-skills/conftest.py:50-96`
  - custom registration maps hyphenated directories into importable packages for tests

Impact:
- runtime import behavior is less robust than test behavior
- pytest hides part of the real packaging problem

### P1 — `wt-device-use-e2e` “reproducible demo” is still model-dependent and brittle

Status:
- verified by source inspection
- also confirmed by Claude/Codex record drift

Evidence:
- `wt-device-use-e2e/demos/record_full_showcase.py:148-166`
  - verification delegated to `ask_verify(...)`
- `wt-device-use-e2e/demos/record_full_showcase.py:66-85`
  - VNC capture path not validated robustly
- `wt-device-use-e2e/demos/record_full_showcase.py:545-558`
  - script hard-fails without `OPENROUTER_API_KEY`

Impact:
- success still depends on VLM responses, prompt interpretation, and provider availability
- this is not a deterministic scripted demo harness yet

Important management drift:
- `~/.codex/history.jsonl` and recent session traces show the user explicitly asked for “要可复现”
- the existing progress/memory language overstates how reproducible the current demo flow is

### P1 — `wt-device-use-e2e/docs/progress.md` is stale and misleading for this repo

Status:
- verified by inspection

Evidence:
- `/Users/robert/workspace/36-labclaw/wt-device-use-e2e/docs/progress.md`
  - still says:
    - branch: `feat/ai-scientist-loop`
    - worktree: `wt-device-use-ai-scientist`
    - test baseline: `442/451 PASS`
- actual git state:
  - branch is `feat/e2e-closed-loop`
  - head is `5727da0`
  - repo contains multiple untracked demo scripts not reflected in the progress file

Impact:
- this file cannot be trusted as current status for the worktree
- it appears to be copied from `device-use/docs/progress.md`

### P1 — `labclaw` has a real duplicate-consume race in task queue

Status:
- verified by source inspection
- verified by runtime repro

Evidence:
- `labclaw/src/labclaw/core/task_queue.py:209-219`
  - `dequeue()` does a plain `SELECT ... WHERE status = pending`
- `labclaw/src/labclaw/core/task_queue.py:357-360`
  - transition to `RUNNING` happens later in `_execute_task`

Runtime repro:
- two concurrent `dequeue()` calls returned the same `task_id`

Impact:
- multiple workers can claim the same pending task
- this is a correctness bug, not just a throughput issue

### P2 — `labclaw` has a stale-initialization coupling between API reset and KG init state

Status:
- verified by source inspection
- additional runtime repro was performed by subagent during audit

Evidence:
- `labclaw/src/labclaw/api/routers/memory.py:139-152`
  - module-level `_kg_initialized` gate
- `labclaw/src/labclaw/api/deps.py:357-366`
  - `reset_all()` clears dependency caches but does not reset `_kg_initialized`

Impact:
- after reset flows in tests or lifecycle transitions, a fresh backend can be treated as already initialized
- this can produce backend-not-initialized failures on KG paths

### P2 — `labclaw` Tier A memory concurrency is under-tested across processes

Status:
- verified by source inspection
- thread-level coverage exists
- cross-process behavior remains risky

Evidence:
- `labclaw/src/labclaw/memory/markdown.py:141-172`
  - only process-local `threading.Lock`
- `labclaw/src/labclaw/memory/markdown.py:220+`
  - append is still read-modify-write at file level
- `labclaw/tests/unit/test_memory_markdown.py:10-65`
  - current test covers threads, not multi-process writers

Important nuance:
- a fork-based local repro in this audit did not drop entries
- a separate subagent reported a spawn-style multi-process repro with entry loss

Conclusion:
- this is at minimum an under-tested cross-process correctness risk
- do not treat current thread-only coverage as proof of safety

## Project Record Drift

This workspace now has meaningful drift between:
- global Claude memory
- repo-local progress files
- git state
- test state

### Drift 1 — `device-use` status is overstated

Global memory says:
- `device-use v0.1.0 on main — operators merged (PR #3+#5), 522 tests passing`
  - `~/.claude/projects/-Users-robert-workspace-36-labclaw/memory/MEMORY.md:18-22`

Current reality:
- repo is on `main`
- local head `1393e73` is ahead of `origin/main`
- worktree is dirty
- current pytest result is `11 failed, 519 passed, 1 skipped`

This is not a small count drift. It changes whether mainline is considered healthy.

### Drift 2 — root governance says worktree+PR only, but current repo state violates the spirit of that rule

Root governance says:
- `/Users/robert/workspace/36-labclaw/CLAUDE.md:138-145`
  - all development must happen in worktrees
  - never commit directly to main

Current reality:
- `device-use` has a local commit on `main` ahead of upstream
- `device-use` also has local modifications and untracked files on `main`

This is a process-control drift, not just a documentation issue.

### Drift 3 — `labwork-web` progress history says major review/test gates passed, but current E2E protection is gone

Historical progress says:
- `~/.claude/.../progress.md:224-239`
  - prior E2E checks passed
- local `device-use/docs/progress.md:77-80`
  - still claims `labwork-web 17/17 tests pass`

Current reality:
- `labwork-web` Playwright suite: `25 failed, 1 passed`
- many failures are due to outdated selectors, not flaky runtime

This means historical review success has not been maintained as the UI evolved.

### Drift 4 — `wt-device-use-e2e` progress file is not the repo it claims to describe

The worktree progress file is effectively a stale copy of `device-use` progress.

That makes it unsuitable as operational memory for the demo worktree.

## Repo-By-Repo Assessment

### `labclaw`

Strengths:
- strongest test baseline in the workspace
- clean main branch

Risks:
- duplicate task dequeue race
- KG reset/init coupling
- process-level memory append risk remains insufficiently covered

Overall:
- healthiest codebase here, but not free of correctness defects

### `labwork`

Strengths:
- clean repo
- strong test pass rate

Risks:
- sandbox forcibly disabled
- path boundary bug
- remote gateway auth defaults unsafe

Overall:
- operationally mature, security boundary not mature enough

### `labwork-web`

Strengths:
- active feature history
- recent React upgrade landed on main

Risks:
- unauthenticated exposed surface
- E2E suite mostly dead
- hardcoded local-path test harness
- dirty worktree

Overall:
- presentation layer is moving faster than its test and security posture

### `device-use`

Strengths:
- large body of tests still passes
- main demo/control architecture is substantial

Risks:
- 11 failing tests are concentrated around real correctness/environment issues
- test helpers import `conftest` unsafely
- CLI tests do not validate a real installable package state
- venv entrypoints are stale
- dirty main and ahead-of-upstream main

Overall:
- functionally rich, but release/process hygiene is weak right now

### `device-skills`

Strengths:
- mainline is up to date with recent SKILL.md integration

Risks:
- optional deps break whole test collection
- import path story relies on pytest loader shim
- dirty repo (`uv.lock` untracked)

Overall:
- documentation maturity is ahead of packaging/runtime robustness

### `wt-device-use-e2e`

Strengths:
- active demo-focused exploration
- clear evidence of VNC/Tart learning

Risks:
- not deterministic yet
- worktree progress is stale/misleading
- multiple untracked demo scripts

Overall:
- active experimental branch, not yet a reproducible product artifact

## Recommended Next Audit / Fix Order

1. `labwork-web`
   - decide whether it is localhost-only or a reachable network service
   - if reachable, add auth or bind restriction first
   - then repair the Playwright contract to current UI

2. `device-use`
   - fix `conftest` imports
   - make CLI tests run against a real installable/importable package state
   - repair repo-local venv entrypoints or stop relying on them

3. `labwork`
   - restore sandbox intent or explicitly document why it must remain off
   - replace prefix-based path checks with real path containment checks
   - tighten remote gateway defaults

4. `wt-device-use-e2e`
   - separate deterministic control from model-based verification
   - update worktree progress file to actual branch and artifact set

5. `labclaw`
   - make task claim atomic
   - add regression tests for queue race and KG reset/init
   - add a process-level Tier A append test if cross-process safety matters

## Bottom Line

This workspace is not in a “broken everywhere” state.

It is in a “records and reality have diverged” state:
- historical progress logs are rich
- code velocity is high
- but current test and security guarantees are uneven

The deepest audit conclusion is:
- trust `git + runtime verification + code` over progress files
- use Claude/Codex memory as context, not as ground truth

## Fix Batch Log

This section records the implementation work completed after the initial audit snapshot. Status values:

- `Open`: verified issue, no fix yet
- `Fixed`: code changed
- `Verified`: code changed and passed targeted/full verification

### Issue Ledger

| ID | Area | Initial state | Current state |
|------|------|---------------|---------------|
| `LW-SEC-001` | `labwork` sandbox startup override | verified | `Verified` |
| `LW-SEC-002` | `labwork` path boundary prefix bug | verified | `Verified` |
| `LW-SEC-003` | `labwork` remote gateway empty-allowlist / WS auth | verified | `Verified` |
| `LWW-TEST-001` | `labwork-web` E2E selector drift | verified | `Verified` |
| `LWW-TEST-002` | `labwork-web` Playwright hardcoded local paths | verified | `Verified` |
| `DU-TEST-001` | `device-use` unsafe `conftest` import | verified | `Verified` |
| `DU-TEST-002` | `device-use` CLI subprocess import environment | verified | `Verified` |
| `DS-TEST-001` | `device-skills` optional deps break collection | verified | `Verified` |
| `LC-CONC-001` | `labclaw` duplicate dequeue / double claim | verified | `Verified` |
| `LC-STATE-001` | `labclaw` `reset_all()` leaves KG init flag stale | verified | `Verified` |
| `LWW-SEC-001` | `labwork-web` unauthenticated mutable network surface | verified | `Verified` |
| `E2E-DEMO-001` | `wt-device-use-e2e` deterministic demo gap | verified | `Verified` |
| `LC-CONC-002` | `labclaw` Tier A cross-process append risk | verified | `Verified` |
| `WT-TEST-001` | `wt-device-use-e2e` unsafe `conftest` import | verified | `Verified` |
| `WT-TEST-002` | `wt-device-use-e2e` CLI subprocess import environment | verified | `Verified` |

### Batch A — `labwork` Security Boundary Repair

Scope:
- remove the forced sandbox-disable at startup
- replace security-sensitive `startsWith()` checks with shared path containment logic
- stop empty allowlists from acting like allow-all
- stop non-token WebSocket clients from auto-authenticating
- stop silently migrating pairing auth into insecure empty-allowlist mode

Files changed:
- `labwork/src/main/index.ts`
- `labwork/src/main/remote/gateway.ts`
- `labwork/src/main/remote/remote-config-store.ts`
- `labwork/src/main/remote/types.ts`
- `labwork/src/main/sandbox/path-boundary.ts`
- `labwork/src/main/sandbox/path-resolver.ts`
- `labwork/src/main/sandbox/path-guard.ts`
- `labwork/src/main/sandbox/sandbox-sync.ts`
- `labwork/src/main/sandbox/lima-sync.ts`
- `labwork/src/main/sandbox/native-executor.ts`
- `labwork/src/main/sandbox/wsl-agent/index.ts`
- `labwork/src/main/sandbox/lima-agent/index.ts`
- `labwork/src/main/tools/tool-executor.ts`
- `labwork/src/main/tools/sandbox-tool-executor.ts`
- `labwork/tests/sandbox-path-boundary.test.ts`
- `labwork/tests/remote-gateway-auth.test.ts`
- `labwork/tests/sandbox-startup-guard.test.ts`

Implementation notes:
- added `path-boundary.ts` as the shared boundary helper
- replaced prefix-matching with path-relative containment checks in the tool executor, path resolver, native executor, WSL/Lima agents, path guard, and sandbox sync translators
- removed `configStore.set('sandboxEnabled', false)` from app startup
- changed gateway allowlist mode to deny when `allowlist` is empty
- changed `handleWSAuth()` to reject non-token modes for WebSocket auth
- removed the migration that rewrote pairing auth into insecure allowlist-empty config

Verification:
- `cd labwork && npm test -- --run tests/sandbox-path-boundary.test.ts tests/remote-gateway-auth.test.ts tests/sandbox-startup-guard.test.ts tests/remote-default-workdir.test.ts`
- Result: `4` files, `10` tests passed
- `cd labwork && npm test -- --run`
- Result: `85` files, `500` tests passed

Issue status:
- `LW-SEC-001`: `Verified`
- `LW-SEC-002`: `Verified`
- `LW-SEC-003`: `Verified`

Residual risk:
- this batch did not change the Electron `BrowserWindow` `sandbox: false` setting in `src/main/index.ts`
- the remaining unauthenticated network surface in `labwork-web` is tracked separately as `LWW-SEC-001`

### Batch B — `labwork-web` E2E Contract Restoration

Scope:
- align Playwright selectors with the current React UI
- restore portable `playwright.config.ts`
- re-enable timer, tool-detail, pipeline-scroll, and topbar checks against the actual DOM

Files changed:
- `labwork-web/frontend/src/App.tsx`
- `labwork-web/frontend/src/components/StepCard.tsx`
- `labwork-web/frontend/src/components/ToolCard.tsx`
- `labwork-web/playwright.config.ts`
- `labwork-web/tests/helpers/mock-ws.ts`
- `labwork-web/tests/e2e/page-responsiveness.spec.ts`
- `labwork-web/tests/e2e/pipeline-scroll.spec.ts`
- `labwork-web/tests/e2e/timer-behavior.spec.ts`
- `labwork-web/tests/e2e/tool-details.spec.ts`
- `labwork-web/tests/e2e/topbar-status.spec.ts`

Implementation notes:
- added stable `data-testid` hooks to the current UI
- updated WebSocket bootstrap helper to target current selectors
- updated E2E assertions to current DOM behavior instead of removed legacy ids/classes
- removed hardcoded absolute Python path and worktree-specific `cwd` from Playwright config

Verification:
- initial audit baseline: `cd labwork-web && npx playwright test` => `25 failed, 1 passed`
- after fix: `cd labwork-web && npx playwright test`
- result: `26 passed`

Issue status:
- `LWW-TEST-001`: `Verified`
- `LWW-TEST-002`: `Verified`

Residual risk:
- no additional residual risk from this batch; network exposure closure is tracked in Batch E

### Batch C — `device-use` / `device-skills` Test Isolation Repair

Scope:
- make `device-use` test helpers import the local `conftest`
- make CLI subprocess tests run with deterministic import context
- stop `device-skills` optional third-party dependencies from killing global test collection

Files changed:
- `device-use/tests/test_e2e.py`
- `device-use/tests/test_labclaw.py`
- `device-skills/conftest.py`

Implementation notes:
- changed `from conftest import ...` to `from .conftest import ...`
- added `_cli_env()` in `device-use/tests/test_e2e.py` and forced subprocess `cwd` to repo root
- added selective `ModuleNotFoundError` handling in `device-skills/conftest.py`
  - external optional dependency missing: warn and skip registration
  - internal package import error: still raise

Verification:
- `cd device-use && .venv/bin/python -m pytest -q tests/test_e2e.py tests/test_labclaw.py`
- Result: `40 passed`
- `cd device-use && .venv/bin/python -m pytest -q`
- Result: `530 passed, 1 skipped`
- `cd device-skills && pytest -q`
- Result: `146 passed`

Issue status:
- `DU-TEST-001`: `Verified`
- `DU-TEST-002`: `Verified`
- `DS-TEST-001`: `Verified`

Residual risk:
- `device-use/.venv/bin/pytest` still has a stale shebang and remains a repo hygiene issue
- `device-skills` still relies on custom package registration patterns; collection is fixed, packaging elegance is not

### Batch D — `labclaw` Queue Correctness Repair

Scope:
- make dequeue claim atomic
- remove the second RUNNING transition from the runner
- reset memory KG initialization state inside `reset_all()`

Files changed:
- `labclaw/src/labclaw/core/task_queue.py`
- `labclaw/src/labclaw/api/deps.py`
- `labclaw/tests/unit/core/test_task_queue.py`
- `labclaw/tests/unit/test_api_deps_coverage.py`

Implementation notes:
- changed `TaskQueue.dequeue()` from a plain `SELECT` to a single `UPDATE ... RETURNING *`
- `dequeue()` now claims the task as `running` and stamps `started_at` before returning it
- removed the redundant `RUNNING` transition from `TaskRunner._execute_task()`
- updated `reset_all()` to clear `labclaw.api.routers.memory._kg_initialized`
- added regression coverage for concurrent dequeue and KG reset state

Verification:
- initial audit repro: concurrent `dequeue()` returned the same `task_id` twice
- `cd labclaw && PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/core/test_task_queue.py tests/unit/test_api_deps_coverage.py`
- Result: `50 passed`
- `cd labclaw && PYTHONPATH=src .venv/bin/python -m pytest -q`
- Result (latest): `2410 passed, 23 skipped`

Issue status:
- `LC-CONC-001`: `Verified`
- `LC-STATE-001`: `Verified`

Residual risk:
- broader Tier A cross-process append risk moved to Batch F and is now closed under `LC-CONC-002`

### Batch E — `labwork-web` Local-Only Access Gate

Scope:
- close unauthenticated mutable LAN exposure by default
- enforce local-only access for HTTP and WebSocket endpoints
- keep existing behavior for local development and tests

Files changed:
- `labwork-web/app.py`
- `labwork-web/tests/test_local_access.py`

Implementation notes:
- added `_is_loopback_host()` and `_client_host()` helpers
- added HTTP middleware rejecting non-loopback clients with `403 {"error":"local access only"}`
- added WebSocket guard that closes non-loopback clients with close code `1008`
- changed default bind from `0.0.0.0` to `127.0.0.1`

Verification:
- `cd labwork-web && pytest -q tests/test_api_config.py tests/test_local_access.py tests/test_ws_lifecycle.py`
- Result: `17 passed`
- `cd labwork-web && pytest -q`
- Result: `59 passed`
- `cd labwork-web && npx playwright test`
- Result: `26 passed`

Issue status:
- `LWW-SEC-001`: `Verified`

Residual risk:
- local-only default is intentionally strict; any remote access requirement now needs an explicit authenticated design

### Batch F — `labclaw` Tier A Cross-Process Append Hardening

Scope:
- close cross-process write-loss risk for Tier A markdown append path
- add regression coverage that uses spawned processes rather than same-process threads

Files changed:
- `labclaw/src/labclaw/memory/markdown.py`
- `labclaw/tests/unit/test_memory_markdown.py`

Implementation notes:
- added process-level sidecar lock helper for markdown writes (`fcntl.flock` on POSIX, `msvcrt.locking` fallback on Windows)
- wrapped append write path with thread lock + process file lock + atomic replace sequence
- added spawn-process regression test for concurrent append writers

Verification:
- `cd labclaw && PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/test_memory_markdown.py`
- Result: `2 passed`
- `cd labclaw && PYTHONPATH=src .venv/bin/python -m pytest -q`
- Result: `2410 passed, 23 skipped`

Issue status:
- `LC-CONC-002`: `Verified`

Residual risk:
- no known data-loss reproduction remains for the tested multi-process append path

### Batch G — `wt-device-use-e2e` Deterministic Demo Closure

Scope:
- make full showcase runnable without provider/API key
- keep VLM checks optional and non-blocking
- ensure deterministic checkpoints remain source-of-truth

Files changed:
- `wt-device-use-e2e/demos/record_full_showcase.py`

Implementation notes:
- hardened VNC capture path to fail loudly on command errors and stale/absent screenshots
- split verification flow into deterministic checkpoints + optional VLM overlay (`verify_checkpoint`)
- made verifier construction optional (`build_optional_verifier`) and fail-fast only when explicit VLM-required mode is requested
- made missing `openai` package non-fatal in deterministic mode
- updated usage header to document deterministic-first execution

Verification:
- `cd wt-device-use-e2e && /Users/robert/workspace/36-labclaw/device-use/.venv/bin/python -m py_compile demos/record_full_showcase.py`
- Result: success (syntax valid)
- `cd wt-device-use-e2e && env DEMO_DISABLE_VLM=1 DEMO_REQUIRE_VLM=0 python3 -u demos/record_full_showcase.py`
- Result: deterministic full run completed with `Pipeline: 7/7 in 172s`; artifacts:
  - `/tmp/full_showcase_output/labclaw_full_20260313_211559.mp4`
  - `/tmp/full_showcase_output/labclaw_full_20260313_211559_4k.mp4`
  - `/tmp/full_showcase_output/labclaw_full_20260313_211559.gif`

Issue status:
- `E2E-DEMO-001`: `Verified`

Residual risk:
- full video runtime still depends on VM reachability (`sshpass`, `vncdo`, and TopSpin availability), but no longer on provider/API key availability

### Batch H — `wt-device-use-e2e` Test Isolation Parity Repair

Scope:
- remove cross-repo `conftest` bleed in this worktree's own tests
- make CLI subprocess tests run with deterministic import context
- verify the full `wt-device-use-e2e` suite on current branch state

Files changed:
- `wt-device-use-e2e/tests/test_e2e.py`
- `wt-device-use-e2e/tests/test_labclaw.py`
- `wt-device-use-e2e/tests/test_record_full_showcase.py`

Implementation notes:
- changed local helper imports from `from conftest import ...` to `from .conftest import ...`
- added `_cli_env()` and forced CLI subprocess `cwd` to the repo root
- kept the new demo regression tests inside the same repo so deterministic-path behavior stays covered with the rest of the suite

Verification:
- initial full-suite baseline: `cd wt-device-use-e2e && pytest -q`
- Result: `11 failed, 528 passed`
- `cd wt-device-use-e2e && pytest -q tests/test_e2e.py tests/test_labclaw.py tests/test_record_full_showcase.py`
- Result: `48 passed`
- `cd wt-device-use-e2e && pytest -q`
- Result: `539 passed`

Issue status:
- `WT-TEST-001`: `Verified`
- `WT-TEST-002`: `Verified`

Residual risk:
- the suite remains warning-heavy under the current Python 3.14 local environment, but the previously failing functional paths are now green

## Post-Fix Verification Matrix

| Repo | Command | Result |
|------|---------|--------|
| `labwork` | `npm test -- --run` | `85 files, 500 tests passed` |
| `labwork-web` | `pytest -q` | `59 passed` |
| `labwork-web` | `npx playwright test` | `26 passed` |
| `device-use` | `.venv/bin/python -m pytest -q` | `530 passed, 1 skipped` |
| `device-skills` | `pytest -q` | `146 passed` |
| `labclaw` | `PYTHONPATH=src .venv/bin/python -m pytest -q` | `2410 passed, 23 skipped` |
| `wt-device-use-e2e` | `pytest -q` | `539 passed` |
| `wt-device-use-e2e` | `python -m py_compile demos/record_full_showcase.py` | `success` |
| `wt-device-use-e2e` | `env DEMO_DISABLE_VLM=1 DEMO_REQUIRE_VLM=0 python3 -u demos/record_full_showcase.py` | `Pipeline: 7/7 in 172s` |

## Remaining Open Items After This Batch

No previously tracked `Open` items remain in this batch ledger.

Operational follow-ups that are intentionally outside the closed issue set:
- optional: design a future authenticated remote-access mode for `labwork-web` if non-local deployment is required
