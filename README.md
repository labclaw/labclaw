# LabClaw

[![CI](https://github.com/labclaw/labclaw/actions/workflows/ci.yml/badge.svg)](https://github.com/labclaw/labclaw/actions/workflows/ci.yml)
[![Security](https://github.com/labclaw/labclaw/actions/workflows/security.yml/badge.svg)](https://github.com/labclaw/labclaw/actions/workflows/security.yml)
[![Release](https://github.com/labclaw/labclaw/actions/workflows/release.yml/badge.svg)](https://github.com/labclaw/labclaw/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Distributed, agentic lab infrastructure for **self-documenting** and **self-improving** neuroscience workflows.

## OpenClaw Integration

LabClaw builds its researcher community on top of the
[OpenClaw](https://github.com/openclaw/openclaw) platform (191k+ stars):
OpenClaw provides chat, LLM routing, and AgentSkill distribution;
LabClaw builds the science engine, lab memory, hardware safety layer,
and domain plugins. See [docs/openclaw-extension.md](docs/openclaw-extension.md)
for the full architecture.

## Why LabClaw

LabClaw turns raw experimental activity into a closed loop:

1. Observe incoming files and session events.
2. Monitor data quality in real time.
3. Mine patterns and generate hypotheses.
4. Track provenance and validation.
5. Evolve analysis behavior safely.

## Core Modules

- `edge/`: File watching, sentinel monitoring, session chronicle
- `discovery/`: Pattern mining, unsupervised discovery, modeling, hypotheses
- `validation/`: Statistical tests, provenance chains, report generation
- `memory/`: Tier-A markdown memory (`SOUL.md`, `MEMORY.md`)
- `evolution/`: Candidate proposals, stage transitions, rollback checks
- `api/`: FastAPI control plane endpoints

## Quick Start

```bash
# Install with dev + science stack
uv sync --extra dev --extra science

# Run API + daemon loop
uv run labclaw serve --data-dir ./data --memory-root ./lab

# Run the dashboard in a separate terminal
uv run labclaw --dashboard
```

## Test Suite

```bash
uv run --extra dev --extra science pytest -q
```

## CI/CD

GitHub Actions now provides:

- CI gates for lint, compatibility, full tests, and package build validation
- Security scanning (CodeQL + dependency audit)
- Tagged release automation (GitHub Release + optional PyPI publish)
- Manual environment deployment workflow (`workflow_dispatch`)
- Weekly dependency update PRs via Dependabot

Setup details and required repository secrets/variables are documented in
`docs/reference/ci-cd.md`.

## API

```bash
uv run labclaw --api 18800
# Health check
curl http://127.0.0.1:18800/api/health
```

## Runtime and API Semantics

- Holm correction uses step-down monotonic adjusted p-values and preserves original test order in output.
- Tier-A memory `entity_id` values are constrained to `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`.
- Tier-A append uses per-file in-process locking to avoid dropped entries under concurrent writers in the same process.
- Memory search API validates `limit >= 1` (`422` on invalid limits).
- Session recording API requires an existing file within `LABCLAW_DATA_DIR`.
- Daemon ingestion retries zero-row files on later events and performs defensive shutdown (`terminate` then `kill` on timeout for dashboard subprocesses).

See:

- `docs/specs/L3-validation.md`
- `docs/specs/L4-memory.md`
- `docs/specs/L3-engine.md`
- `docs/migrations/2026-02-20-api-behavior-changes.md`

## Demo

> Demo server coming soon at `demo.labclaw.dev`. See `deploy/` for self-hosting instructions.

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs and issues are welcome.

## License

Apache 2.0
