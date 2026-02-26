# Open-Source Release Preparation Plan

> **Date:** 2026-02-26
> **Goal:** Prepare LabClaw for public GitHub release (open-source readiness, not the v0.1.0 paper milestone)

---

## 1. Positioning (3 sentences)

LabClaw is a science/lab AI system that builds its own researcher community
on top of OpenClaw's technology stack. We reuse OpenClaw for chat, LLM
routing, and AgentSkill distribution — we build the science engine, lab
memory, hardware safety, and domain plugins. OpenClaw is the acquisition
channel; LabClaw is the retention community.

---

## 2. Current State

### Branches and PRs

| Branch | PR | Status | Fixes |
|--------|-----|--------|-------|
| `chore/open-source-readiness` | #26 | OPEN | deploy.sh, CHANGELOG, ROADMAP, paper refs |
| `fix/code-quality` | #27 | OPEN | lint, format, 500 handler coverage |
| `fix/release-metadata` | #28 | OPEN | version sync, PyPI URLs, README, CHANGELOG |
| `fix/infra-hardening` | #29 | OPEN | Dockerfile USER, SHA-pin CI, gitignore |
| `fix/capability-assertions` | #30 | OPEN | BDD p < 0.05 assertions |
| `fix/code-health` | #31 | OPEN | mypy errors, plans exclusion from docs |

**All 6 PRs are OPEN, none merged to main.** Main still has all original issues.

### Issues on main (verified 2026-02-25)

| Issue | Fixed by | Status |
|-------|----------|--------|
| `__init__.py` version 0.0.2 vs pyproject 0.0.10 | PR #28 | pending merge |
| `[project.urls]` missing from pyproject.toml | PR #28 | pending merge |
| CONTRIBUTING says 90% coverage | PR #28 | pending merge |
| README has Launch Checklist | PR #28 | pending merge |
| CHANGELOG missing v0.0.4-0.0.10 | PR #28 | pending merge |
| 3 lint errors + 55 unformatted files | PR #27 | pending merge |
| API 500 handler uncovered | PR #27 | pending merge |
| Dockerfile runs as root | PR #29 | pending merge |
| CODE_OF_CONDUCT minimal | PR #29 | pending merge |
| docs.yml not SHA-pinned | PR #29 | pending merge |
| BDD p-value only range-checked | PR #30 | pending merge |
| 36 mypy errors | PR #31 | pending merge |
| deploy.sh hardcoded `claw` + IP | PR #26 | pending merge |
| CHANGELOG "DO server" / "Tailscale" | PR #26 | pending merge |
| ROADMAP "Paper Release" | PR #26 | pending merge |
| `--dashboard-host` option | **nobody** | not started |
| Caddy reverse proxy config | **nobody** | not started |
| OpenClaw positioning in README/docs | **nobody** | not started |
| Demo server actual deployment | **nobody** | not started |

---

## 3. Work Packages

### Phase A: Merge Existing PRs

Merge PRs #27-31 into main. Order matters due to potential conflicts.

| Step | Action | Why this order |
|------|--------|----------------|
| A1 | Merge PR #27 `fix/code-quality` | Fixes lint/format baseline; other PRs may conflict with reformatted files |
| A2 | Merge PR #28 `fix/release-metadata` | Version sync, PyPI metadata, CHANGELOG — foundational |
| A3 | Merge PR #29 `fix/infra-hardening` | Dockerfile, CI, gitignore — independent |
| A4 | Merge PR #30 `fix/capability-assertions` | BDD assertions — independent |
| A5 | Merge PR #31 `fix/code-health` | mypy fixes — may need rebase after #27 format changes |
| A6 | Rebase PR #26 `chore/open-source-readiness` on main | Gets all fixes, then we add remaining work here |

After A6, the `chore/open-source-readiness` branch has everything from
PRs #27-31 plus the existing cleanup commit (6cf1831).

### Phase B: Demo Server (on `chore/open-source-readiness`)

#### B1: `feat(daemon): add --dashboard-host bind option`

| File | Change |
|------|--------|
| `src/labclaw/daemon.py` | Add `dashboard_host` param (default `127.0.0.1`) |
| `src/labclaw/cli.py` | Add `--dashboard-host` to help text |
| `Dockerfile` | Add `--dashboard-host 0.0.0.0` to ENTRYPOINT |
| `tests/unit/test_daemon.py` | Test dashboard_host param + default |

#### B2: `fix(config): normalize dict/BaseModel LLM configs from YAML`

| File | Change |
|------|--------|
| `src/labclaw/config.py` | Handle dict/BaseModel in `model_post_init` |
| `tests/unit/test_config.py` | Test dict + mismatched BaseModel normalization |

#### B3: `chore(deploy): add Caddy reverse proxy for demo server`

| File | Change |
|------|--------|
| `deploy/Caddyfile` (new) | Reverse proxy: `/api/*` → :18800, `/` → :18801, TLS, security headers |
| `deploy/deploy.sh` | Add optional step: `LABCLAW_DOMAIN` → install Caddy + write config + firewall |
| `deploy/labclaw.service` | Keep `127.0.0.1` (no `--host 0.0.0.0`) — behind Caddy |
| `docs/deployment.md` | Document Caddy setup for DO |

### Phase C: OpenClaw Positioning (on same branch)

#### C1: `docs: add OpenClaw extension architecture`

Create `docs/openclaw-extension.md`:
- What LabClaw reuses from OpenClaw (chat, LLM, skills)
- What LabClaw builds (science engine, memory, safety, provenance)
- Integration pattern: `labclaw-skill` calls LabClaw API over HTTP
- Community model: own docs + demo, OpenClaw as distribution channel

#### C2: `docs: update README for open-source release`

| Change | Detail |
|--------|--------|
| Add positioning block | 3 sentences + link to `docs/openclaw-extension.md` |
| Add demo section | Links to demo server (or "coming soon" if not live yet) |
| Add OpenClaw badge | `[![Built on OpenClaw](...)][openclaw]` |
| Fix ROADMAP reference | Verify "Public Release" wording (should be done by 6cf1831) |

### Phase D: Release

#### D1: Final validation

```
make lint          # zero errors
make test          # 100% coverage, all pass
grep -ri tailscale src/ deploy/ docs/ CHANGELOG.md   # nothing
grep -ri '100.86' src/ deploy/ docs/                 # nothing
grep -i 'paper release' ROADMAP.md                   # nothing
```

#### D2: Tag and release

```
git tag -a v0.0.11 -m "v0.0.11: open-source readiness"
git push origin main --tags
```

This triggers `.github/workflows/release.yml`:
- Creates GitHub Release with auto-generated notes
- Publishes to PyPI (if trusted publishing is configured)

#### D3: Deploy demo server

```
LABCLAW_REMOTE=labclaw-server \
LABCLAW_DOMAIN=demo.labclaw.dev \
bash deploy/deploy.sh
```

#### D4: Post-release

- Update README demo links from "coming soon" to actual URLs
- Create 10+ `good first issue` labels
- Announce in OpenClaw community (Discord, awesome-openclaw PR)

---

## 4. Commit Sequence (Phase B + C)

After Phase A (all PRs merged + rebase):

1. `feat(daemon): add --dashboard-host bind option` (B1)
2. `fix(config): normalize dict/BaseModel LLM configs from YAML` (B2)
3. `chore(deploy): add Caddy reverse proxy for demo server` (B3)
4. `docs: add OpenClaw extension architecture` (C1)
5. `docs: update README for open-source release` (C2)

5 commits, ~12 files changed.

---

## 5. Definition of Done

- [ ] PRs #27-31 merged to main
- [ ] `make lint` passes
- [ ] `make test` passes with 100% coverage
- [ ] `grep -ri tailscale src/ deploy/ docs/ CHANGELOG.md` → nothing
- [ ] `grep -ri '100.86' src/ deploy/ docs/` → nothing
- [ ] `grep -i 'paper release' ROADMAP.md` → nothing
- [ ] `__init__.py` version matches `pyproject.toml`
- [ ] `pyproject.toml` has `[project.urls]`
- [ ] `CONTRIBUTING.md` says 100% coverage
- [ ] `docs/openclaw-extension.md` exists
- [ ] README has OpenClaw positioning + demo section
- [ ] `deploy/Caddyfile` exists
- [ ] `deploy/deploy.sh` uses `LABCLAW_REMOTE` env var
- [ ] Demo server accessible with TLS (after D3)
- [ ] `v0.0.11` tag created (after D2)

---

## 6. Out of Scope

| Item | When |
|------|------|
| `labclaw-skill` OpenClaw package | After v0.1.0 |
| Domain plugin packs (neuro, chem) | v0.2.0 |
| Protocol template library | v0.2.0 |
| Benchmark dataset | v0.2.0 |
| GitHub Discussions | After repo public |
| Demo GIF for README | After demo live |
| git history rewrite | Not needed (no credentials in history) |
