# LabClaw as an OpenClaw Extension

LabClaw is a science-focused system built on top of the
[OpenClaw](https://github.com/openclaw/openclaw) platform. This document
describes what each project provides, how they connect, and how the two
communities relate.

---

## What LabClaw Reuses from OpenClaw

| Component | OpenClaw provides | LabClaw uses it for |
|-----------|-------------------|---------------------|
| Chat interface | Built-in multi-model chat UI | Lab members interact with their AI assistant |
| LLM routing | Provider abstraction (Anthropic, OpenAI, local) | Hypothesis generation, report writing, memory search |
| AgentSkill framework | Package format for distributing agent capabilities | Distributing the `labclaw-skill` package (see below) |
| Plugin marketplace | Skill discovery and one-click install | Making LabClaw accessible to OpenClaw users |

LabClaw does **not** fork OpenClaw. It runs OpenClaw as a dependency and
extends it through the official AgentSkill interface.

---

## What LabClaw Builds

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Science engine | `orchestrator/`, `discovery/` | 7-step scientific method loop (OBSERVE → ASK → HYPOTHESIZE → PREDICT → EXPERIMENT → ANALYZE → CONCLUDE) |
| Lab memory | `memory/` | Three-tier memory: Markdown/git (Tier A), knowledge graph (Tier B), agent shared blocks (Tier C) |
| Hardware safety | `hardware/` | Device registry, safety rules, controlled shutdown, audit log |
| Provenance tracking | `validation/` | Full chain from raw file → analysis → finding; SHA-256 checksums; NWB export |
| Domain plugins | `plugins/` | Neuroscience pack (NWB, DLC, LFP); future packs for chemistry and imaging |
| Researcher community | `lab/`, `members/`, `devices/` | Per-lab profiles, per-member memory, per-device configuration |

None of these exist in OpenClaw. They are LabClaw's core value.

---

## Integration Pattern

The integration point is a thin HTTP bridge called `labclaw-skill` (planned,
post-v0.1.0). It is a standard OpenClaw AgentSkill package that:

1. Registers tool definitions with the OpenClaw agent runtime.
2. Forwards tool calls to the LabClaw REST API (`http://localhost:18800/api/`).
3. Returns structured results that OpenClaw renders in its chat UI.

```
OpenClaw chat
    └── labclaw-skill (AgentSkill package)
            └── HTTP  →  LabClaw API (:18800)
                              ├── graph DB
                              ├── memory tiers
                              ├── science loop
                              └── hardware layer
```

LabClaw can also run standalone without OpenClaw: the Streamlit dashboard
(`:18801`) and CLI (`labclaw serve`) provide full access to all features.

---

## Community Model

| Concern | OpenClaw | LabClaw |
|---------|----------|---------|
| Docs site | openclaw.dev | docs.labclaw.dev (MkDocs) |
| Demo server | OpenClaw cloud | demo.labclaw.dev (self-hosted) |
| Community | OpenClaw Discord / forums | LabClaw GitHub Discussions (science-specific) |
| Distribution | OpenClaw marketplace | PyPI (`labclaw`, `labclaw-skill`) |
| Vertical focus | General-purpose agents | Wet-lab and computational research |

OpenClaw serves as the **acquisition channel**: researchers who already use
OpenClaw discover LabClaw through the marketplace. LabClaw serves as the
**retention community**: once researchers adopt the science engine and lab
memory, they stay within LabClaw's ecosystem for experiment management,
provenance, and domain collaboration.

---

## FAQ

**Do I need OpenClaw to use LabClaw?**
No. LabClaw runs independently. OpenClaw is optional and adds a chat
interface on top.

**Does LabClaw contribute back to OpenClaw?**
Any general-purpose improvements to LLM routing or skill packaging will be
proposed upstream. Science-specific code stays in LabClaw.

**When will `labclaw-skill` be available?**
After v0.1.0. See [ROADMAP.md](../ROADMAP.md).
