# Physical AI Scientist — Architecture

> Claude Code IS the brain. Everything else is a plugin.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                        CLAUDE CODE  (Brain)                             │
│                        Opus 4.6 / Sonnet 4.6                           │
│                                                                         │
│   Scientific Reasoning    Domain Knowledge    Report Writing            │
│   NMR peak assignment     Chemistry/Physics   IMRAD papers              │
│   Hypothesis generation   Safety awareness    Lab notebooks             │
│   Experiment planning     Literature review   Data visualization        │
│                                                                         │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│   │ OBSERVE  │→ │HYPOTHESIZE→ │  VERIFY  │→ │  REPORT  │              │
│   └────┬─────┘  └──────────┘  └────┬─────┘  └────┬─────┘              │
│        │         ◄── ITERATE ──►   │              │                     │
│        │                           │              │                     │
└────────┼───────────────────────────┼──────────────┼─────────────────────┘
         │                           │              │
         │ MCP (stdio)               │              │ Built-in tools
         ▼                           ▼              ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────────┐
│                  │ │                  │ │                              │
│   device-use     │ │    labclaw       │ │   Claude Code Skills         │
│   MCP Server     │ │    MCP Server    │ │   + Filesystem               │
│                  │ │                  │ │                              │
│ ┌──────────────┐ │ │ ┌──────────────┐ │ │ Skills:                     │
│ │ 9 MCP Tools  │ │ │ │ 7 MCP Tools  │ │ │  /data-analysis             │
│ │              │ │ │ │              │ │ │  /experiment                 │
│ │ Instruments: │ │ │ │ Memory:      │ │ │  /lab-notebook              │
│ │  nmr_process │ │ │ │  query_memory│ │ │  /instrument                │
│ │  nmr_identify│ │ │ │  list_finding│ │ │  /scientific-writing        │
│ │  nmr_list    │ │ │ │  provenance  │ │ │  /research-lookup           │
│ │  plate_reader│ │ │ │              │ │ │  /pdf                       │
│ │  run_pipeline│ │ │ │ Discovery:   │ │ │                              │
│ │  call_tool   │ │ │ │  discover    │ │ │ Filesystem (Manus pattern): │
│ │              │ │ │ │  hypothesize │ │ │  Read/Write/Edit             │
│ │ Operators:   │ │ │ │              │ │ │  data/ reports/ plots/       │
│ │  L1: API     │ │ │ │ Evolution:   │ │ │  notebooks/ experiments/    │
│ │  L2: Script  │ │ │ │  evo_status  │ │ │                              │
│ │  L3: A11y    │ │ │ │  device_stat │ │ │ External:                   │
│ │  L4: CU      │ │ │ └──────────────┘ │ │  context7 (docs lookup)     │
│ │              │ │ │                  │ │  WebSearch / WebFetch        │
│ │ Remote Libs: │ │ │                  │ │                              │
│ │  PubChem     │ │ └──────────────────┘ └──────────────────────────────┘
│ │  ToolUniverse│ │
│ │  (600+ tools)│ │
│ └──────────────┘ │
│                  │
│ Instruments:     │
│  TopSpin (NMR)   │
│  Gen5 (Plate)    │
│  FIJI (Imaging)  │
│  + future        │
│                  │
└──────────────────┘
```

## MCP Configuration

File: `/Users/robert/workspace/36-labclaw/.mcp.json` (project-level)

```json
{
  "mcpServers": {
    "device-use": {
      "command": ".../device-use/.venv/bin/python",
      "args": ["-m", "device_use.integrations.mcp_server"],
      "env": { "PYTHONPATH": "src" }
    },
    "labclaw": {
      "command": ".../labclaw/.venv/bin/python",
      "args": ["-m", "labclaw", "mcp"]
    }
  }
}
```

## Tool Inventory

### device-use MCP (9 tools)

| Tool | Input | Output | Status |
|------|-------|--------|--------|
| `list_instruments` | — | [{name, vendor, version, mode, connected}] | ✅ |
| `list_tools` | — | [{name, description, params}] | ✅ |
| `call_tool` | tool_name, params | tool result | ✅ |
| `nmr_list_datasets` | — | [{sample, expno, title, path}] | ✅ |
| `nmr_process` | data_path | {peaks, nucleus, solvent, freq_mhz, plot} | ✅ |
| `nmr_identify` | data_path, formula? | {compound, confidence, analysis} | ✅ (needs API key for live AI) |
| `plate_reader_list_assays` | — | [{name, type}] | ✅ |
| `plate_reader_process` | assay_name | {wells, statistics, heatmap} | ✅ |
| `run_pipeline` | steps_json | {results per step} | ✅ |

**Remote Libraries (via call_tool)**:
- **PubChem** — compound lookup by name/formula/CAS, returns CID/SMILES/InChI/weight
- **ToolUniverse** — Harvard's 600+ scientific tools, searchable by domain (chemistry, spectroscopy, drug discovery)

### labclaw MCP (7 tools)

| Tool | Input | Output | Status |
|------|-------|--------|--------|
| `discover` | min_sessions, thresholds | patterns with provenance | ⚠️ needs data |
| `hypothesize` | context, constraints | hypotheses from patterns | ⚠️ needs data |
| `evolution_status` | — | {active_cycles, history, stages} | ✅ |
| `device_status` | — | [{id, name, type, status}] | ✅ |
| `query_memory` | query | findings via hybrid search | ⚠️ P1 bug: KG returns empty |
| `list_findings` | limit | recent findings | ⚠️ P1 bug: daemon doesn't persist |
| `provenance` | finding_id | full provenance chain | ✅ |

### Claude Code Built-in Skills

| Skill | Purpose | Trigger |
|-------|---------|---------|
| `/data-analysis` | Statistical analysis, plotting, model fitting | Scientific data processing |
| `/experiment` | Protocol creation, session tracking, observations | Experiment management |
| `/lab-notebook` | Structured ELN entries, cross-referencing | Documentation |
| `/instrument` | GUI automation via device-use | Instrument operation |
| `/scientific-writing` | IMRAD papers, citations, reporting guidelines | Report generation |
| `/research-lookup` | Literature search, paper finding | Background research |
| `/pdf` | PDF extraction, creation, form filling | Document processing |

## Scientific Workflow

```
User: "这个未知化合物是什么？exam_CMCse_1"

Claude Code (Brain):
  │
  ├─ 1. OBSERVE
  │    ├─ MCP: nmr_list_datasets() → find exam_CMCse_1
  │    ├─ MCP: nmr_process("/opt/topspin5.0.0/examdata/exam_CMCse_1/1")
  │    └─ Result: 10 peaks, 1H, 400MHz, CDCl3
  │
  ├─ 2. HYPOTHESIZE (Claude Code 自己推理)
  │    ├─ 6.62+6.05 ppm → 共轭烯酮
  │    ├─ 0.83 ppm (最强) → gem-dimethyl cyclohexane
  │    ├─ 2.23 ppm → COCH3 methyl ketone
  │    └─ Hypothesis: α-Ionone, C13H20O, DoU=4
  │
  ├─ 3. VERIFY
  │    ├─ MCP: call_tool("pubchem", {name: "alpha-ionone"})
  │    │   └─ CID 5282108, C13H20O ✓, SMILES match ✓
  │    ├─ MCP: query_memory("alpha ionone NMR")
  │    │   └─ Past findings? Similar samples?
  │    ├─ Skill: /research-lookup "alpha ionone NMR characterization"
  │    │   └─ Literature confirmation
  │    └─ MCP: call_tool("tooluniverse", {query: "NMR prediction"})
  │        └─ Find specialized tools for spectrum simulation
  │
  ├─ 4. EVALUATE
  │    ├─ Formula match: ✓ (C13H20O)
  │    ├─ Peak coverage: 10/10
  │    ├─ PubChem confirmed: ✓
  │    ├─ Score: 1.0 > 0.7 threshold → ACCEPT
  │    └─ (If < threshold → ITERATE: try different assignment, request 2D NMR)
  │
  ├─ 5. REPORT
  │    ├─ Skill: /scientific-writing → IMRAD report
  │    ├─ Skill: /lab-notebook → ELN entry
  │    ├─ Write: output/reports/alpha-ionone-report.md
  │    └─ MCP: list_findings() → store for future reference
  │
  └─ 6. NEXT EXPERIMENT (if needed)
       ├─ "Run HSQC to confirm C-H connectivity"
       ├─ MCP: call_tool("topspin", {command: "hsqc"})  ← needs operator wiring
       └─ Loop back to OBSERVE with new data
```

## What's Connected Now vs What's Missing

### ✅ Connected (works today)

```
Claude Code ──MCP──► device-use ──► NMR offline processing (36 datasets)
                                ──► PubChem (compound lookup)
                                ──► ToolUniverse (600+ tools)
                                ──► PlateReader (96-well assays)

Claude Code ──MCP──► labclaw ──► evolution_status
                             ──► device_status
                             ──► provenance

Claude Code ──Skills──► /data-analysis (stats, plotting)
                    ──► /scientific-writing (IMRAD)
                    ──► /lab-notebook (ELN)
                    ──► /research-lookup (literature)
                    ──► /experiment (protocols)
                    ──► /instrument (GUI automation)
                    ──► /pdf (documents)

Claude Code ──Built-in──► filesystem (data, reports, plots)
                      ──► WebSearch / WebFetch (literature)
                      ──► context7 (library docs)
```

### ❌ Not Yet Connected

| Gap | What | Fix |
|-----|------|-----|
| **Instrument operation** | Can't execute commands on live TopSpin | Wire A11y operator → adapter (~50 lines) |
| **Memory persistence** | labclaw query_memory/list_findings return empty | Fix 3 P1 bugs (~60 lines) |
| **Live AI analysis** | nmr_identify needs ANTHROPIC_API_KEY | Set env var in .mcp.json |

## Key Principle

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  Claude Code = Brain (reasoning, planning)      │
│  device-use  = Hands (instrument operation)     │
│  labclaw     = Memory (findings, evolution)     │
│  filesystem  = Infinite context window          │
│  Skills      = Domain expertise (K-Dense)       │
│  MCP         = Universal connector              │
│                                                 │
│  不需要再写 brain。不需要编排层。                   │
│  Claude Code 本身就是 Physical AI Scientist。     │
│                                                 │
└─────────────────────────────────────────────────┘
```
