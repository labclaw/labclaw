# LabClaw End-to-End Demo — GAP Fix Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 7 GAPs so the LabClaw demo runs a complete scientific experiment autonomously — from question to report — with real TopSpin GUI operation and Ralph Loop.

**Architecture:** Python orchestrator script (`demos/demo_full_experiment.py`) drives 5 phases: Research (ToolUniverse + PubChem) → Instrument (TopSpin GUI via GPT-5.4 CU) → Analyze (NMR Brain) → Discover (labclaw API) → Report (k-dense scientific-writer). Ralph Loop wraps the whole flow for autonomous iteration.

**Tech Stack:** Python 3.14, FastAPI, OpenAI SDK (GPT-5.4 CU), Anthropic SDK (NMR Brain), ToolUniverse, k-dense scientific-writer plugin, nmrglue, matplotlib

**Parallelism:** Tasks 1-3 are independent installs (parallel). Task 4 is independent bug fix (parallel with 1-3). Tasks 5-6 depend on 1-4. Task 7 depends on 5-6.

---

## Chunk 1: Independent Installs & Bug Fix (Tasks 1-4, parallel)

### Task 1: Install k-dense Scientific Writer Plugin

**Files:**
- No code changes — plugin installation only

- [ ] **Step 1: Install scientific-writer Python package**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
.venv/bin/pip install scientific-writer
```

Expected: Package installs successfully with dependencies (markitdown, etc.)

- [ ] **Step 2: Install as Claude Code plugin**

```bash
cd /Users/robert/workspace/36-labclaw
claude /plugin marketplace add https://github.com/K-Dense-AI/claude-scientific-writer
claude /plugin install claude-scientific-writer
```

Expected: Plugin registered in `~/.claude/plugins/`

- [ ] **Step 3: Verify plugin skills are available**

```bash
ls ~/.claude/plugins/*/claude-scientific-writer/skills/ 2>/dev/null || ls /tmp/k-dense-writer/skills/
```

Expected: 24 skills listed (scientific-writing, research-lookup, peer-review, etc.)

- [ ] **Step 4: Manually copy skills if plugin install doesn't work**

Fallback — copy from cloned repo:

```bash
cp -r /tmp/k-dense-writer/skills/scientific-writing ~/.claude/skills/
cp -r /tmp/k-dense-writer/skills/research-lookup ~/.claude/skills/
cp -r /tmp/k-dense-writer/skills/scientific-schematics ~/.claude/skills/
cp -r /tmp/k-dense-writer/skills/peer-review ~/.claude/skills/
cp -r /tmp/k-dense-writer/CLAUDE.md /tmp/k-dense-writer-CLAUDE-reference.md
```

---

### Task 2: Install k-dense Scientific Skills (NMR-relevant subset)

**Files:**
- No code changes — skill installation only

- [ ] **Step 1: Copy NMR/chemistry-relevant skills from cloned repo**

```bash
# Already cloned at /tmp/k-dense-skills/
cp -r /tmp/k-dense-skills/scientific-skills/pubchem-database ~/.claude/skills/
cp -r /tmp/k-dense-skills/scientific-skills/scientific-visualization ~/.claude/skills/
cp -r /tmp/k-dense-skills/scientific-skills/matplotlib ~/.claude/skills/
cp -r /tmp/k-dense-skills/scientific-skills/rdkit ~/.claude/skills/
cp -r /tmp/k-dense-skills/scientific-skills/biopython ~/.claude/skills/
cp -r /tmp/k-dense-skills/scientific-skills/scientific-brainstorming ~/.claude/skills/
cp -r /tmp/k-dense-skills/scientific-skills/hypothesis-generation ~/.claude/skills/
cp -r /tmp/k-dense-skills/scientific-skills/statistical-analysis ~/.claude/skills/
```

Expected: Skills copied to `~/.claude/skills/`

- [ ] **Step 2: Verify skills are discoverable**

```bash
ls ~/.claude/skills/ | wc -l
```

Expected: Count increases by 8+ skills

---

### Task 3: Install ToolUniverse SDK

**Files:**
- No code changes — package installation only

- [ ] **Step 1: Install tooluniverse in device-use venv**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
.venv/bin/pip install tooluniverse
```

Expected: Package installs, `tooluniverse>=1.0` satisfied

- [ ] **Step 2: Verify import works**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python -c "from device_use.tools.tooluniverse import ToolUniverseTool; t = ToolUniverseTool(); print('available:', t.available)"
```

Expected: `available: True`

- [ ] **Step 3: Test tool discovery**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python -c "
from device_use.tools.tooluniverse import ToolUniverseTool
t = ToolUniverseTool()
t.connect()
results = t.find_tools('NMR spectroscopy analysis', limit=3)
print(results)
"
```

Expected: Returns list of 3 NMR-related tools from ToolUniverse

---

### Task 4: Fix GPT-5.4 Computer Use Action Extraction Bug

**Files:**
- Modify: `/Users/robert/workspace/36-labclaw/device-use/src/device_use/backends/openai_compat.py` (lines 148-168)
- Test: `/Users/robert/workspace/36-labclaw/device-use/tests/test_backends.py`

**Bug:** In `_extract_computer_calls()`, when `item.actions` contains `None` values or `item.action` is `None`, the code appends `None` to the actions list. Later, iterating over the list and accessing `action.type` crashes with `AttributeError: 'NoneType' object has no attribute 'type'`.

- [ ] **Step 1: Write failing test**

Add to `/Users/robert/workspace/36-labclaw/device-use/tests/test_backends.py`:

```python
def test_extract_computer_calls_handles_none_actions():
    """Regression test: None actions in computer_call should not crash."""
    from unittest.mock import MagicMock
    from device_use.backends.openai_compat import OpenAICompatBackend

    backend = OpenAICompatBackend.__new__(OpenAICompatBackend)

    # Mock response with computer_call containing None action
    mock_item = MagicMock()
    mock_item.type = "computer_call"
    mock_item.call_id = "test_call"
    mock_item.actions = None
    mock_item.action = None

    mock_response = MagicMock()
    mock_response.output = [mock_item]

    results = backend._extract_computer_calls(mock_response)
    assert results == []  # Should return empty, not crash


def test_extract_computer_calls_filters_none_in_actions_list():
    """Regression test: None values within actions list should be skipped."""
    from unittest.mock import MagicMock
    from device_use.backends.openai_compat import OpenAICompatBackend

    backend = OpenAICompatBackend.__new__(OpenAICompatBackend)

    mock_action = MagicMock()
    mock_action.type = "click"
    mock_action.x = 100
    mock_action.y = 200
    mock_action.button = "left"

    mock_item = MagicMock()
    mock_item.type = "computer_call"
    mock_item.call_id = "test_call"
    mock_item.actions = [None, mock_action, None]
    mock_item.action = None

    mock_response = MagicMock()
    mock_response.output = [mock_item]

    results = backend._extract_computer_calls(mock_response)
    assert len(results) == 1
    assert results[0]["action_type"] == "click"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python -m pytest tests/test_backends.py::test_extract_computer_calls_handles_none_actions tests/test_backends.py::test_extract_computer_calls_filters_none_in_actions_list -v
```

Expected: FAIL with AttributeError on `action.type`

- [ ] **Step 3: Fix _extract_computer_calls() — add None filtering**

In `/Users/robert/workspace/36-labclaw/device-use/src/device_use/backends/openai_compat.py`, find the `_extract_computer_calls` method. After the line that builds the `actions` list (around line 150), add None filtering:

```python
# BEFORE (buggy):
actions = item.actions or []
if not actions and item.action is not None:
    actions = [item.action]
if not actions:
    logger.warning("computer_call %s has no actions", call_id)
    continue

for action in actions:
    results.append({
        "call_id": call_id,
        "action_type": action.type,

# AFTER (fixed):
actions = item.actions or []
if not actions and item.action is not None:
    actions = [item.action]
# Filter out None actions to prevent AttributeError on action.type
actions = [a for a in actions if a is not None]
if not actions:
    logger.warning("computer_call %s has no actions", call_id)
    continue

for action in actions:
    results.append({
        "call_id": call_id,
        "action_type": action.type,
```

The fix is a single line: `actions = [a for a in actions if a is not None]`

- [ ] **Step 4: Run tests to verify fix**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python -m pytest tests/test_backends.py -v -k "computer_call"
```

Expected: Both new tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python -m pytest tests/ -x --timeout=30
```

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
git add src/device_use/backends/openai_compat.py tests/test_backends.py
git commit -m "fix(gui): filter None actions in GPT-5.4 Computer Use extraction

Prevents AttributeError when OpenAI API returns computer_call with
None values in actions list. Adds regression tests."
```

---

## Chunk 2: Demo Orchestrator Script (Task 5)

### Task 5: Write End-to-End Demo Orchestrator

**Files:**
- Create: `/Users/robert/workspace/36-labclaw/device-use/demos/demo_full_experiment.py`
- Reference: `demos/06_ai_scientist.py`, `demos/10_lab_report.py`

This script drives the 5-phase experiment. It calls device-use locally (Python imports) and labclaw remotely (HTTP to port 18800).

- [ ] **Step 1: Create demo skeleton with phase structure**

Create `/Users/robert/workspace/36-labclaw/device-use/demos/demo_full_experiment.py`:

```python
#!/usr/bin/env python3
"""LabClaw End-to-End Scientific Experiment Demo.

Runs a complete autonomous experiment:
  Phase 1: RESEARCH — ToolUniverse + PubChem literature search
  Phase 2: INSTRUMENT — TopSpin GUI operation via Computer Use
  Phase 3: ANALYZE — NMR processing + AI brain interpretation
  Phase 4: DISCOVER — labclaw scientific loop (OBSERVE→CONCLUDE)
  Phase 5: REPORT — Generate IMRAD report with findings

Usage:
    python demos/demo_full_experiment.py [--dataset Cyclosporine] [--no-gui] [--no-labclaw]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from demos.lib.terminal import header, info, success, warning, error, dim
from demos.lib.runner import DemoRunner

# Phase result accumulator
RESULTS: dict[str, dict] = {}
OUTPUT_DIR = Path("output/full_experiment")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LabClaw Full Experiment Demo")
    parser.add_argument("--dataset", default="Cyclosporine",
                        help="TopSpin dataset name (default: Cyclosporine)")
    parser.add_argument("--expno", type=int, default=1,
                        help="Experiment number (default: 1)")
    parser.add_argument("--formula", default="C62H111N11O12",
                        help="Molecular formula (default: Cyclosporine A)")
    parser.add_argument("--no-gui", action="store_true",
                        help="Skip GUI phase (use offline processing only)")
    parser.add_argument("--no-labclaw", action="store_true",
                        help="Skip labclaw API calls")
    parser.add_argument("--labclaw-url", default="http://localhost:18800",
                        help="labclaw API base URL")
    parser.add_argument("--output", default="output/full_experiment",
                        help="Output directory")
    return parser.parse_args()


# ─── Phase 1: RESEARCH ───────────────────────────────────────────────

def phase_research(args: argparse.Namespace) -> dict:
    """Search ToolUniverse and PubChem for compound info."""
    header("Phase 1: RESEARCH")
    results = {"tools_found": [], "pubchem": None}

    # 1a. ToolUniverse
    try:
        from device_use.tools.tooluniverse import ToolUniverseTool
        tu = ToolUniverseTool()
        if tu.available:
            tu.connect()
            tools = tu.find_tools(f"NMR spectroscopy {args.dataset}", limit=5)
            results["tools_found"] = tools or []
            success(f"ToolUniverse: found {len(results['tools_found'])} relevant tools")
        else:
            warning("ToolUniverse SDK not installed — skipping tool discovery")
    except Exception as e:
        warning(f"ToolUniverse error: {e}")

    # 1b. PubChem
    try:
        from device_use.tools.pubchem import PubChemTool
        pc = PubChemTool()
        compound = pc.lookup_by_name(args.dataset)
        results["pubchem"] = compound
        if compound:
            success(f"PubChem: {compound.get('IUPACName', 'N/A')} (CID: {compound.get('CID')})")
        else:
            warning(f"PubChem: no results for '{args.dataset}'")
    except Exception as e:
        warning(f"PubChem error: {e}")

    RESULTS["research"] = results
    return results


# ─── Phase 2: INSTRUMENT (TopSpin GUI) ────────────────────────────────

def phase_instrument(args: argparse.Namespace) -> dict:
    """Operate TopSpin via Computer Use (or skip with --no-gui)."""
    header("Phase 2: INSTRUMENT")
    results = {"gui_used": False, "screenshots": []}

    if args.no_gui:
        info("Skipping GUI phase (--no-gui)")
        RESULTS["instrument"] = results
        return results

    try:
        import subprocess
        # Activate TopSpin window
        subprocess.run([
            "osascript", "-e",
            'tell application id "net.java.openjdk.java" to activate'
        ], check=True)
        time.sleep(2)
        info("TopSpin activated")

        # Take initial screenshot
        from mss import mss
        with mss() as sct:
            screenshot_path = OUTPUT_DIR / "01_topspin_initial.png"
            sct.shot(output=str(screenshot_path))
            results["screenshots"].append(str(screenshot_path))
            info(f"Screenshot: {screenshot_path}")

        # GPT-5.4 Computer Use: open dataset and process
        from device_use.backends.openai_compat import OpenAICompatBackend

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            warning("OPENAI_API_KEY not set — skipping Computer Use")
            RESULTS["instrument"] = results
            return results

        backend = OpenAICompatBackend(model="gpt-5.4")

        # Observe current state
        with open(screenshot_path, "rb") as f:
            screenshot_b64 = __import__("base64").b64encode(f.read()).decode()

        observation = await_or_sync(backend.observe(screenshot_b64))
        info(f"AI observation: {observation[:200]}...")

        # Plan: open dataset
        task = f"Open the dataset '{args.dataset}' experiment {args.expno} in TopSpin. Use the File menu or type 're {args.dataset} {args.expno}' in the command line."
        plan_result = await_or_sync(backend.plan(screenshot_b64, task))
        if plan_result:
            info(f"AI plan: {plan_result}")
            results["gui_used"] = True
        else:
            warning("AI returned no plan — falling back to AppleScript command mode")
            _topspin_command(f"re {args.dataset} {args.expno}")
            time.sleep(2)
            _topspin_command("efp")
            time.sleep(1)
            _topspin_command("apbk")
            time.sleep(1)

        # Take post-processing screenshot
        time.sleep(2)
        with mss() as sct:
            screenshot_path2 = OUTPUT_DIR / "02_topspin_processed.png"
            sct.shot(output=str(screenshot_path2))
            results["screenshots"].append(str(screenshot_path2))

        success("TopSpin GUI operation complete")

    except Exception as e:
        warning(f"GUI phase error: {e} — will continue with offline processing")

    RESULTS["instrument"] = results
    return results


def _topspin_command(cmd: str) -> None:
    """Send a command to TopSpin via AppleScript."""
    import subprocess
    script = f'''
    tell application id "net.java.openjdk.java"
        activate
    end tell
    delay 0.5
    tell application "System Events"
        keystroke "{cmd}"
        keystroke return
    end tell
    '''
    subprocess.run(["osascript", "-e", script], check=True)
    info(f"TopSpin command: {cmd}")


def await_or_sync(coro):
    """Run an async coroutine synchronously."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return loop.run_in_executor(pool, asyncio.run, coro)
    except RuntimeError:
        return asyncio.run(coro)


# ─── Phase 3: ANALYZE ─────────────────────────────────────────────────

def phase_analyze(args: argparse.Namespace) -> dict:
    """Process NMR data offline and run AI brain analysis."""
    header("Phase 3: ANALYZE")

    from device_use.instruments.nmr.adapter import TopSpinAdapter
    from device_use.instruments.nmr.visualizer import plot_spectrum
    from device_use.instruments.nmr.brain import NMRBrain

    adapter = TopSpinAdapter()
    adapter.connect()

    # Find dataset
    datasets = adapter.list_datasets()
    target = [d for d in datasets
              if d["sample"] == args.dataset and d["expno"] == args.expno]
    if not target:
        error(f"Dataset not found: {args.dataset}/{args.expno}")
        error(f"Available: {[d['sample'] for d in datasets[:5]]}")
        RESULTS["analyze"] = {"error": "Dataset not found"}
        return RESULTS["analyze"]

    data_path = target[0]["path"]
    info(f"Processing: {data_path}")

    # Process
    t0 = time.time()
    spectrum = adapter.process(data_path)
    proc_time = time.time() - t0
    success(f"Processed in {proc_time:.1f}s — {len(spectrum.peaks)} peaks detected")

    # Visualize
    plot_path = OUTPUT_DIR / f"{args.dataset}_spectrum.png"
    plot_spectrum(spectrum, output_path=str(plot_path))
    success(f"Spectrum plot: {plot_path}")

    # AI Brain interpretation
    brain = NMRBrain()
    info("Running AI brain analysis (streaming)...")
    analysis_text = ""
    for chunk in brain.interpret_spectrum(spectrum, molecular_formula=args.formula, stream=True):
        analysis_text += chunk
        print(chunk, end="", flush=True)
    print()
    success("Brain analysis complete")

    # Suggest next experiment
    info("AI suggesting next experiment...")
    suggestion = ""
    for chunk in brain.suggest_next_experiment(spectrum, stream=True):
        suggestion += chunk
        print(chunk, end="", flush=True)
    print()

    results = {
        "spectrum": {
            "title": spectrum.title,
            "nucleus": spectrum.nucleus,
            "solvent": spectrum.solvent,
            "frequency_mhz": spectrum.frequency_mhz,
            "num_peaks": len(spectrum.peaks),
            "peaks": [{"ppm": p.ppm, "intensity": p.intensity, "width": p.width}
                      for p in spectrum.peaks[:20]],
        },
        "processing_time_s": proc_time,
        "analysis": analysis_text,
        "next_experiment": suggestion,
        "plot_path": str(plot_path),
    }

    RESULTS["analyze"] = results
    return results


# ─── Phase 4: DISCOVER (labclaw API) ──────────────────────────────────

def phase_discover(args: argparse.Namespace) -> dict:
    """Run labclaw scientific loop on the NMR data."""
    header("Phase 4: DISCOVER")

    if args.no_labclaw:
        info("Skipping labclaw phase (--no-labclaw)")
        RESULTS["discover"] = {"skipped": True}
        return RESULTS["discover"]

    base = args.labclaw_url.rstrip("/")

    # Check health
    try:
        r = requests.get(f"{base}/api/health/status", timeout=5)
        health = r.json()
        info(f"labclaw status: {health.get('status', 'unknown')}")
    except Exception as e:
        warning(f"labclaw not reachable at {base}: {e}")
        warning("Skipping discovery phase — start labclaw with: cd labclaw && make run")
        RESULTS["discover"] = {"error": str(e)}
        return RESULTS["discover"]

    # Convert NMR peaks to data_rows for labclaw
    analyze = RESULTS.get("analyze", {})
    peaks = analyze.get("spectrum", {}).get("peaks", [])
    data_rows = []
    for i, peak in enumerate(peaks):
        data_rows.append({
            "sample": args.dataset,
            "peak_index": i,
            "ppm": peak["ppm"],
            "intensity": peak["intensity"],
            "width": peak.get("width", 0),
            "nucleus": analyze.get("spectrum", {}).get("nucleus", "1H"),
        })

    if not data_rows:
        warning("No peaks to send to labclaw")
        RESULTS["discover"] = {"error": "No peaks"}
        return RESULTS["discover"]

    info(f"Sending {len(data_rows)} peaks to labclaw orchestrator...")

    # Run scientific cycle
    try:
        r = requests.post(
            f"{base}/api/orchestrator/cycle",
            json={"data_rows": data_rows},
            timeout=60,
        )
        cycle = r.json()
        success(f"Cycle complete: {cycle.get('cycle_id', 'N/A')}")

        patterns = cycle.get("patterns", [])
        hypotheses = cycle.get("hypotheses", [])
        info(f"Patterns found: {len(patterns)}")
        info(f"Hypotheses generated: {len(hypotheses)}")

    except Exception as e:
        warning(f"labclaw cycle error: {e}")
        cycle = {"error": str(e)}

    # Search memory for related findings
    try:
        r = requests.get(
            f"{base}/api/memory/search/query",
            params={"q": args.dataset, "limit": 5},
            timeout=10,
        )
        findings = r.json()
        info(f"Related findings in memory: {len(findings)}")
    except Exception:
        findings = []

    results = {
        "cycle": cycle,
        "findings": findings,
    }

    RESULTS["discover"] = results
    return results


# ─── Phase 5: REPORT ──────────────────────────────────────────────────

def phase_report(args: argparse.Namespace) -> dict:
    """Generate IMRAD report from all phases."""
    header("Phase 5: REPORT")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    research = RESULTS.get("research", {})
    instrument = RESULTS.get("instrument", {})
    analyze = RESULTS.get("analyze", {})
    discover = RESULTS.get("discover", {})

    spectrum = analyze.get("spectrum", {})
    pubchem = research.get("pubchem", {})
    cycle = discover.get("cycle", {})

    # Build peak table
    peaks = spectrum.get("peaks", [])
    peak_rows = ""
    max_intensity = max((p["intensity"] for p in peaks), default=1)
    for i, p in enumerate(peaks[:15]):
        rel = (p["intensity"] / max_intensity * 100) if max_intensity else 0
        peak_rows += f"| {i+1} | {p['ppm']:.3f} | {rel:.1f}% | {p.get('width', 0):.2f} |\n"

    # Build report markdown
    report = f"""# NMR Analysis Report: {args.dataset}

**Date:** {timestamp}
**Instrument:** Bruker TopSpin 5.0.0
**Mode:** {'GUI + Offline' if instrument.get('gui_used') else 'Offline'}
**Molecular Formula:** {args.formula}

---

## Abstract

This report presents the nuclear magnetic resonance (NMR) spectroscopic analysis of
{args.dataset}, a cyclic undecapeptide with immunosuppressive properties. The sample
was analyzed using 1H NMR at {spectrum.get('frequency_mhz', 'N/A')} MHz in
{spectrum.get('solvent', 'N/A')}. {spectrum.get('num_peaks', 0)} peaks were detected
and analyzed using AI-assisted interpretation.

## Introduction

{args.dataset} is a membrane-active immunosuppressant widely used in organ
transplantation. NMR spectroscopy provides detailed structural information about its
cyclic peptide backbone and N-methylated amino acid residues.

{"### PubChem Reference" if pubchem else ""}
{"| Property | Value |" if pubchem else ""}
{"| --- | --- |" if pubchem else ""}
{"| CID | " + str(pubchem.get("CID", "")) + " |" if pubchem else ""}
{"| IUPAC Name | " + str(pubchem.get("IUPACName", "")) + " |" if pubchem else ""}
{"| Formula | " + str(pubchem.get("MolecularFormula", "")) + " |" if pubchem else ""}
{"| Weight | " + str(pubchem.get("MolecularWeight", "")) + " |" if pubchem else ""}
{"| InChIKey | " + str(pubchem.get("InChIKey", "")) + " |" if pubchem else ""}

## Methods

### Instrument Configuration
- **Spectrometer:** Bruker TopSpin 5.0.0
- **Nucleus:** {spectrum.get('nucleus', '1H')}
- **Frequency:** {spectrum.get('frequency_mhz', 'N/A')} MHz
- **Solvent:** {spectrum.get('solvent', 'N/A')}

### Processing Pipeline
1. Raw FID acquisition from TopSpin examdata
2. Digital filter removal (Bruker artifact correction)
3. Zero filling to 65536 points
4. Exponential apodization (0.3 Hz line broadening)
5. Fourier transform (FFT)
6. Automatic phase correction (ACME algorithm)
7. Polynomial baseline correction
8. Threshold-based peak picking

Processing time: {analyze.get('processing_time_s', 0):.1f} seconds

## Results

### Peak List

| # | Chemical Shift (ppm) | Relative Intensity | Width (Hz) |
|---|---------------------|--------------------|------------|
{peak_rows}

Total peaks detected: {spectrum.get('num_peaks', 0)}

### AI-Assisted Interpretation

{analyze.get('analysis', 'Analysis not available.')}

### Recommended Next Experiments

{analyze.get('next_experiment', 'No suggestions available.')}

## Discussion

{"### Pattern Discovery (labclaw)" if not discover.get("skipped") and not discover.get("error") else ""}
{"Patterns found: " + str(len(cycle.get("patterns", []))) if isinstance(cycle, dict) and cycle.get("patterns") else ""}
{"Hypotheses generated: " + str(len(cycle.get("hypotheses", []))) if isinstance(cycle, dict) and cycle.get("hypotheses") else ""}

{"### ToolUniverse" if research.get("tools_found") else ""}
{"Relevant scientific tools discovered: " + str(len(research.get("tools_found", []))) if research.get("tools_found") else ""}

## Conclusions

The NMR analysis of {args.dataset} identified {spectrum.get('num_peaks', 0)} peaks
consistent with the expected cyclic peptide structure. AI-assisted interpretation
provided peak assignments and structural confirmation.

---

*Generated by LabClaw — AI-Driven Scientific Research Platform*
*device-use v0.1.0 + labclaw v0.1.0*
"""

    # Write report
    report_path = OUTPUT_DIR / f"{args.dataset}_report.md"
    report_path.write_text(report)
    success(f"Report written: {report_path}")

    # Write raw results JSON
    json_path = OUTPUT_DIR / f"{args.dataset}_results.json"
    # Filter non-serializable values
    serializable = {}
    for k, v in RESULTS.items():
        try:
            json.dumps(v)
            serializable[k] = v
        except (TypeError, ValueError):
            serializable[k] = str(v)
    json_path.write_text(json.dumps(serializable, indent=2, default=str))
    info(f"Raw results: {json_path}")

    RESULTS["report"] = {"path": str(report_path), "json_path": str(json_path)}
    return RESULTS["report"]


# ─── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print()
    header("LabClaw End-to-End Scientific Experiment")
    info(f"Dataset: {args.dataset} (exp {args.expno})")
    info(f"Formula: {args.formula}")
    info(f"Output:  {OUTPUT_DIR}")
    print()

    t0 = time.time()

    # Run all phases
    phase_research(args)
    phase_instrument(args)
    phase_analyze(args)
    phase_discover(args)
    phase_report(args)

    elapsed = time.time() - t0
    print()
    header("EXPERIMENT COMPLETE")
    success(f"Total time: {elapsed:.1f}s")
    success(f"Report: {OUTPUT_DIR}/{args.dataset}_report.md")
    success(f"Spectrum: {OUTPUT_DIR}/{args.dataset}_spectrum.png")
    if RESULTS.get("instrument", {}).get("screenshots"):
        success(f"Screenshots: {RESULTS['instrument']['screenshots']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test Phase 1 (Research) standalone**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python -c "
import sys; sys.path.insert(0, 'demos')
from demo_full_experiment import phase_research, RESULTS, OUTPUT_DIR, parse_args
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
args = parse_args()
phase_research(args)
print('OK:', RESULTS['research'].keys())
"
```

Expected: PubChem returns Cyclosporine data. ToolUniverse returns tools (or warns if not installed).

- [ ] **Step 3: Test Phase 3 (Analyze) standalone**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python -c "
import sys; sys.path.insert(0, 'demos')
from demo_full_experiment import phase_analyze, RESULTS, OUTPUT_DIR, parse_args
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
args = parse_args()
phase_analyze(args)
print('Peaks:', RESULTS['analyze']['spectrum']['num_peaks'])
"
```

Expected: Cyclosporine spectrum processed, peaks detected, AI analysis streamed.

- [ ] **Step 4: Test full demo (offline mode, no labclaw)**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python demos/demo_full_experiment.py --dataset Cyclosporine --no-gui --no-labclaw
```

Expected: Phases 1, 3, 5 complete. Report written to `output/full_experiment/`.

- [ ] **Step 5: Test with labclaw (if running)**

```bash
# Terminal 1: Start labclaw
cd /Users/robert/workspace/36-labclaw/labclaw
make run  # or: uvicorn labclaw.api.app:app --port 18800

# Terminal 2: Run demo with labclaw
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python demos/demo_full_experiment.py --dataset Cyclosporine --no-gui
```

Expected: Phase 4 sends peaks to labclaw, gets cycle result back.

- [ ] **Step 6: Test with GUI (TopSpin must be running)**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python demos/demo_full_experiment.py --dataset Cyclosporine
```

Expected: TopSpin window activates, screenshot taken, commands sent.

- [ ] **Step 7: Commit**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
git add demos/demo_full_experiment.py
git commit -m "feat(demo): add end-to-end experiment orchestrator

Drives 5 phases: Research → Instrument → Analyze → Discover → Report.
Connects device-use (NMR) with labclaw (scientific loop).
Supports GUI mode (Computer Use) and offline mode."
```

---

## Chunk 3: Ralph Loop Prompt & Final Integration (Tasks 6-7)

### Task 6: Wire labclaw ↔ device-use Bidirectional

**Files:**
- Modify: `/Users/robert/workspace/36-labclaw/device-use/demos/demo_full_experiment.py` (Phase 4)

The orchestrator already calls labclaw API in Phase 4. This task adds the reverse: labclaw's "suggest next experiment" feeds back into device-use.

- [ ] **Step 1: Add feedback loop to Phase 4**

In `demo_full_experiment.py`, after the cycle result, add:

```python
    # After cycle result, check if labclaw suggests next experiment
    hypotheses = cycle.get("hypotheses", [])
    if hypotheses and not args.no_gui:
        info("labclaw suggests follow-up experiments based on hypotheses:")
        for h in hypotheses[:3]:
            info(f"  → {h.get('description', h)}")
        # Could trigger Phase 2 again with new parameters
        # For demo: just log the suggestion
        info("(In production, this would trigger the next instrument run)")
```

- [ ] **Step 2: Add labclaw agent chat integration**

Add a function to `demo_full_experiment.py` that calls the labclaw agent for interpretation:

```python
def ask_labclaw_agent(base_url: str, question: str) -> str:
    """Ask the labclaw Lab Assistant agent a question."""
    try:
        r = requests.post(
            f"{base_url}/api/agents/chat",
            json={"message": question},
            timeout=30,
        )
        data = r.json()
        return data.get("response", "No response")
    except Exception as e:
        return f"Agent unavailable: {e}"
```

Call it in Phase 4 after the cycle:

```python
    # Ask agent for interpretation
    if not discover.get("error"):
        agent_q = f"We analyzed {args.dataset} by NMR and found {len(peaks)} peaks. The AI brain identified the compound. What patterns do you see in the data? What should we investigate next?"
        info("Asking labclaw Lab Assistant...")
        agent_response = ask_labclaw_agent(base, agent_q)
        info(f"Agent: {agent_response[:300]}...")
        results["agent_response"] = agent_response
```

- [ ] **Step 3: Test bidirectional flow**

```bash
# With labclaw running:
cd /Users/robert/workspace/36-labclaw/device-use
PYTHONPATH=src .venv/bin/python demos/demo_full_experiment.py --dataset Cyclosporine --no-gui
```

Expected: Phase 4 runs cycle + asks agent + reports hypotheses.

- [ ] **Step 4: Commit**

```bash
cd /Users/robert/workspace/36-labclaw/device-use
git add demos/demo_full_experiment.py
git commit -m "feat(demo): add labclaw bidirectional integration

Phase 4 now sends peaks to labclaw orchestrator, asks Lab Assistant
agent for interpretation, and logs suggested follow-up experiments."
```

---

### Task 7: Write Ralph Loop Prompt

**Files:**
- Create: `/Users/robert/workspace/36-labclaw/.claude/ralph-prompts/full-experiment.md`

- [ ] **Step 1: Create the Ralph Loop prompt file**

```bash
mkdir -p /Users/robert/workspace/36-labclaw/.claude/ralph-prompts
```

Create `/Users/robert/workspace/36-labclaw/.claude/ralph-prompts/full-experiment.md`:

```markdown
# LabClaw Full Experiment — Ralph Loop Prompt

Run the complete LabClaw end-to-end scientific experiment demo and iterate until
it produces a high-quality report.

## Task

Execute the full experiment pipeline for Cyclosporine analysis:

1. **Start labclaw API** (if not running):
   ```bash
   cd /Users/robert/workspace/36-labclaw/labclaw && make run &
   ```
   Wait for "Uvicorn running on http://0.0.0.0:18800"

2. **Run the demo orchestrator**:
   ```bash
   cd /Users/robert/workspace/36-labclaw/device-use
   PYTHONPATH=src .venv/bin/python demos/demo_full_experiment.py --dataset Cyclosporine
   ```

3. **Check the output**:
   - Verify `output/full_experiment/Cyclosporine_report.md` exists and is complete
   - Verify `output/full_experiment/Cyclosporine_spectrum.png` exists
   - Verify all 5 phases completed without errors

4. **If any phase failed**, fix the issue and re-run.

5. **Enhance the report** using k-dense scientific-writing skill:
   - Read the generated report
   - Apply IMRAD structure improvements
   - Add proper scientific prose (no bullet points in body)
   - Ensure citations and terminology follow chemistry conventions

6. **Generate final PDF** (if LaTeX available):
   ```bash
   cd output/full_experiment && pandoc Cyclosporine_report.md -o Cyclosporine_report.pdf
   ```

## Completion Promise

When ALL of the following are true, output the completion promise:
- All 5 phases ran successfully
- Report exists at `output/full_experiment/Cyclosporine_report.md`
- Spectrum plot exists at `output/full_experiment/Cyclosporine_spectrum.png`
- Report follows IMRAD structure
- No errors in any phase

<promise>EXPERIMENT_COMPLETE</promise>
```

- [ ] **Step 2: Test Ralph Loop invocation**

```bash
# In Claude Code:
/ralph-loop "$(cat /Users/robert/workspace/36-labclaw/.claude/ralph-prompts/full-experiment.md)" --max-iterations 10 --completion-promise "EXPERIMENT_COMPLETE"
```

Expected: Ralph Loop starts, iterates through the experiment phases.

- [ ] **Step 3: Commit**

```bash
cd /Users/robert/workspace/36-labclaw
# Commit in device-use (demo changes)
cd device-use && git add demos/demo_full_experiment.py && git commit -m "feat(demo): finalize full experiment demo for Ralph Loop"

# Create a simple wrapper script at root level
cd /Users/robert/workspace/36-labclaw
```

---

## Execution Order & Parallelism

```
┌──────────────────────────────────────────────────────┐
│ PARALLEL BATCH 1 (independent installs + bug fix)    │
│                                                      │
│  Agent A: Task 1 (k-dense writer install)            │
│  Agent B: Task 2 (k-dense skills install)            │
│  Agent C: Task 3 (ToolUniverse install)              │
│  Agent D: Task 4 (fix CU bug + tests)               │
│                                                      │
├──────────────────────────────────────────────────────┤
│ SEQUENTIAL (depends on Tasks 1-4)                    │
│                                                      │
│  Agent E: Task 5 (demo orchestrator script)          │
│                                                      │
├──────────────────────────────────────────────────────┤
│ SEQUENTIAL (depends on Task 5)                       │
│                                                      │
│  Agent F: Task 6 (wire bidirectional)                │
│  Agent G: Task 7 (Ralph Loop prompt)                 │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## Verification Checklist

After all tasks complete:

- [ ] `pip list | grep tooluniverse` → installed
- [ ] `pip list | grep scientific-writer` → installed
- [ ] `ls ~/.claude/skills/scientific-writing/` → SKILL.md present
- [ ] `PYTHONPATH=src python -c "from device_use.backends.openai_compat import OpenAICompatBackend"` → no error
- [ ] `python demos/demo_full_experiment.py --no-gui --no-labclaw` → report generated
- [ ] `python demos/demo_full_experiment.py --no-gui` (with labclaw running) → full cycle
- [ ] `python demos/demo_full_experiment.py` (with TopSpin + labclaw) → GUI + full cycle
- [ ] Report at `output/full_experiment/Cyclosporine_report.md` is IMRAD, scientific quality
