"""LabClaw CLI — main entry point."""

from __future__ import annotations

import asyncio
import csv
import json
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Matches UUID v4 strings embedded in finding descriptions (e.g. pattern IDs)
_uuid_re = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "serve":
        from labclaw.daemon import main as daemon_main

        sys.argv = sys.argv[1:]  # shift so argparse sees daemon args
        daemon_main()
    elif cmd == "--dashboard":
        app_path = Path(__file__).parent / "dashboard" / "app.py"
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
    elif cmd == "--api":
        import uvicorn

        from labclaw.api.app import app

        if len(sys.argv) > 2:
            try:
                port = int(sys.argv[2])
            except ValueError:
                print(f"Error: invalid port number '{sys.argv[2]}'", file=sys.stderr)
                sys.exit(1)
        else:
            port = 18800
        uvicorn.run(app, host="127.0.0.1", port=port)
    elif cmd == "demo":
        _demo_cmd(sys.argv[2:])
    elif cmd == "init":
        _init_cmd(sys.argv[2:])
    elif cmd == "mcp":
        from labclaw.mcp.server import main as mcp_main

        mcp_main()
    elif cmd == "plugin":
        _plugin_cmd(sys.argv[2:])
    elif cmd == "pipeline":
        _pipeline_cmd(sys.argv[2:])
    elif cmd == "ablation":
        _ablation_cmd(sys.argv[2:])
    elif cmd == "export":
        _export_cmd(sys.argv[2:])
    elif cmd == "memory":
        _memory_cmd(sys.argv[2:])
    elif cmd == "reproduce":
        _reproduce_cmd(sys.argv[2:])
    else:
        print("Usage: labclaw <command>")
        print()
        print("Commands:")
        print("  serve          Start the full 24/7 LabClaw daemon")
        print("  demo           Run an interactive demo (no API keys needed)")
        print("  init           Scaffold a new LabClaw project directory")
        print("  mcp            Start MCP server (stdio transport)")
        print("  plugin         Manage plugins (see: labclaw plugin --help)")
        print("  pipeline       Run one discovery cycle on CSV data and print JSON result")
        print("  ablation       Run full vs no-evolution comparison and print JSON result")
        print("  memory         Query or inspect persisted memory")
        print("  reproduce      Run pipeline twice with same seed and verify identical output")
        print("  --dashboard    Launch Streamlit dashboard only")
        print("  export         Export findings and provenance (NWB or JSON)")
        print("  --api [PORT]   Launch FastAPI server only")
        print()
        print("Serve options (pass after 'serve'):")
        print("  --data-dir PATH        Directory to watch (default: /opt/labclaw/data)")
        print("  --memory-root PATH     Memory directory (default: /opt/labclaw/memory)")
        print("  --port PORT            API port (default: 18800)")
        print("  --dashboard-port PORT  Dashboard port (default: 18801)")


def _coerce_row_values(row: dict[str, str | None]) -> dict[str, Any]:
    """Parse CSV row values into numeric types when possible."""
    parsed: dict[str, Any] = {}
    for key, value in row.items():
        if key is None or value is None:
            continue
        raw = value.strip()
        if raw == "":
            continue
        try:
            parsed[key] = float(raw)
        except ValueError:
            parsed[key] = value
    return parsed


def _demo_cmd(args: list[str]) -> None:
    """Run the interactive demo."""
    import logging

    from labclaw.demo.runner import DemoRunner

    domain = "generic"
    keep = False
    i = 0
    while i < len(args):
        if args[i] == "--domain" and i + 1 < len(args):
            domain = args[i + 1]
            i += 2
        elif args[i] == "--keep":
            keep = True
            i += 1
        elif args[i] in ("-h", "--help"):
            print("Usage: labclaw demo [--domain generic|neuroscience|chemistry] [--keep]")
            print()
            print("Options:")
            print("  --domain DOMAIN  Sample dataset to use (default: generic)")
            print("  --keep           Keep temporary workspace after demo")
            return
        else:
            i += 1

    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    try:
        runner = DemoRunner(domain=domain, keep=keep)
        runner.run()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nDemo interrupted.")


def _init_cmd(args: list[str]) -> None:
    """Scaffold a new LabClaw project directory."""
    import shutil

    if not args or args[0] in ("-h", "--help"):
        print("Usage: labclaw init <project-name>")
        print()
        print("Scaffolds a new LabClaw project directory with default configs.")
        if not args:
            sys.exit(1)
        return

    name = args[0]
    project_dir = Path.cwd() / name

    if project_dir.exists():
        print(f"Error: directory '{project_dir}' already exists", file=sys.stderr)
        sys.exit(1)

    project_dir.mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "lab").mkdir()
    (project_dir / "configs").mkdir()

    # Copy default config
    default_cfg = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    dest_cfg = project_dir / "configs" / "default.yaml"
    if default_cfg.exists():
        shutil.copy2(default_cfg, dest_cfg)
    else:
        dest_cfg.write_text(
            "# LabClaw configuration\n"
            "system:\n"
            f"  name: {name}\n"
            "  version: 0.0.1\n"
            "  log_level: INFO\n"
            "\n"
            "llm:\n"
            "  provider: anthropic\n"
            "  model: claude-sonnet-4-6\n"
            "  api_key_env: ANTHROPIC_API_KEY\n"
        )

    # Create Tier A entity docs under lab/lab/...
    entity_dir = project_dir / "lab" / "lab"
    entity_dir.mkdir(parents=True, exist_ok=True)
    soul_text = (
        f"# {name}\n\n"
        "## Identity\n\n"
        f"This is the lab profile for **{name}**.\n\n"
        "## Mission\n\n"
        "<!-- Describe your lab's research mission here -->\n\n"
        "## Protocols\n\n"
        "<!-- List standard operating procedures -->\n"
    )
    memory_text = (
        f"# {name} — Memory Log\n\n<!-- LabClaw will append observations and discoveries here -->\n"
    )
    (entity_dir / "SOUL.md").write_text(soul_text)
    (entity_dir / "MEMORY.md").write_text(memory_text)

    # Backward-compatible legacy paths expected by older tooling.
    (project_dir / "lab" / "SOUL.md").write_text(soul_text)
    (project_dir / "lab" / "MEMORY.md").write_text(memory_text)

    print(f"Project scaffolded: {project_dir}")
    print()
    print("  Project structure:")
    print(f"    {name}/")
    print(f"    {name}/configs/default.yaml")
    print(f"    {name}/data/")
    print(f"    {name}/lab/lab/SOUL.md")
    print(f"    {name}/lab/lab/MEMORY.md")
    print()
    print("  Next steps:")
    print(f"    cd {name}")
    print("    labclaw demo          # Run the interactive demo")
    print("    labclaw serve          # Start the 24/7 daemon")


def _plugin_cmd(args: list[str]) -> None:
    """Dispatch plugin sub-commands."""
    sub = args[0] if args else ""

    if sub == "list":
        from labclaw.plugins import plugin_registry
        from labclaw.plugins.loader import PluginLoader

        PluginLoader().load_all()
        plugins = plugin_registry.list_plugins()
        if not plugins:
            print("No plugins registered.")
            return
        print(f"{'NAME':<30} {'TYPE':<12} {'VERSION':<10} DESCRIPTION")
        print("-" * 80)
        for m in plugins:
            print(f"{m.name:<30} {m.plugin_type:<12} {m.version:<10} {m.description}")

    elif sub == "create":
        if len(args) < 2:
            print(
                "Usage: labclaw plugin create <name> [--type device|domain|analysis] [--out DIR]",
                file=sys.stderr,
            )
            sys.exit(1)

        name = args[1]
        plugin_type = "domain"
        out_dir = Path.cwd()

        i = 2
        while i < len(args):
            if args[i] == "--type" and i + 1 < len(args):
                plugin_type = args[i + 1]
                i += 2
            elif args[i] == "--out" and i + 1 < len(args):
                out_dir = Path(args[i + 1])
                i += 2
            else:
                i += 1

        from labclaw.plugins.scaffold import scaffold_plugin

        try:
            project_dir = scaffold_plugin(name, plugin_type, out_dir)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"Plugin scaffold created: {project_dir}")
        print(f"  cd {project_dir}")
        print("  pip install -e .")

    else:
        print("Usage: labclaw plugin <subcommand>")
        print()
        print("Subcommands:")
        print("  list                      List all registered plugins")
        print("  create <name>             Scaffold a new plugin project")
        print("    --type device|domain|analysis  Plugin type (default: domain)")
        print("    --out DIR                      Output directory (default: .)")


def _pipeline_cmd(args: list[str]) -> None:
    """Run one discovery cycle on CSV data and print the JSON result to stdout.

    Usage:
        labclaw pipeline --once --data-dir PATH [--memory-root PATH] [--seed INT]
                         [--max-llm-calls N]
    """
    if args and args[0] in ("-h", "--help"):
        print(
            "Usage: labclaw pipeline --once --data-dir PATH "
            "[--memory-root PATH] [--seed INT] [--max-llm-calls N]"
        )
        print()
        print("Options:")
        print("  --once              Run exactly one cycle and exit")
        print("  --data-dir PATH     Directory containing .csv files (required)")
        print("  --memory-root PATH  Memory root for Tier A logging (optional)")
        print("  --seed INT          Random seed for reproducibility (optional)")
        print("  --max-llm-calls N   Max LLM calls before template fallback (default: 50)")
        return

    if not args:
        print(
            "Error: --data-dir is required. Run 'labclaw pipeline --help' for usage.",
            file=sys.stderr,
        )
        sys.exit(1)

    data_dir: Path | None = None
    memory_root: Path | None = None
    seed: int | None = None
    max_llm_calls: int = 50

    i = 0
    while i < len(args):
        if args[i] == "--data-dir" and i + 1 < len(args):
            data_dir = Path(args[i + 1])
            i += 2
        elif args[i] == "--memory-root" and i + 1 < len(args):
            memory_root = Path(args[i + 1])
            i += 2
        elif args[i] == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        elif args[i] == "--max-llm-calls" and i + 1 < len(args):
            max_llm_calls = int(args[i + 1])
            i += 2
        else:
            i += 1

    if data_dir is None:
        print(
            "Error: --data-dir is required. Run 'labclaw pipeline --help' for usage.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not data_dir.exists() or not data_dir.is_dir():
        print(f"Error: data-dir '{data_dir}' does not exist or is not a directory", file=sys.stderr)
        sys.exit(1)

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"Error: no .csv files found in '{data_dir}'", file=sys.stderr)
        sys.exit(1)

    if seed is not None:
        random.seed(seed)

    all_rows: list[dict[str, Any]] = []
    for csv_path in csv_files:
        with open(csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                parsed = _coerce_row_values(row)
                if parsed:
                    all_rows.append(parsed)

    from labclaw.orchestrator.loop import ScientificLoop
    from labclaw.orchestrator.steps import (
        AnalyzeStep,
        AskStep,
        ConcludeStep,
        ExperimentStep,
        HypothesizeStep,
        ObserveStep,
        PredictStep,
        ScientificStep,
    )

    conclude = ConcludeStep(memory_root=memory_root)
    steps: list[ScientificStep] = [
        ObserveStep(),
        AskStep(),
        HypothesizeStep(llm_provider=None, max_llm_calls=max_llm_calls),
        PredictStep(),
        ExperimentStep(),
        AnalyzeStep(),
        conclude,
    ]
    loop = ScientificLoop(steps=steps)
    result = asyncio.run(loop.run_cycle(all_rows))
    print(json.dumps(result.model_dump()))


def _ablation_cmd(args: list[str]) -> None:
    """Run full vs no-evolution ablation and print comparison as JSON.

    Usage:
        labclaw ablation --data-dir PATH [--n-cycles INT] [--seed INT]
    """
    if args and args[0] in ("-h", "--help"):
        print("Usage: labclaw ablation --data-dir PATH [--n-cycles INT] [--seed INT]")
        print()
        print("Options:")
        print("  --data-dir PATH  Directory containing .csv files (required)")
        print("  --n-cycles INT   Number of evolution cycles (default: 10)")
        print("  --seed INT       Random seed for reproducibility (default: 42)")
        return

    if not args:
        print(
            "Error: --data-dir is required. Run 'labclaw ablation --help' for usage.",
            file=sys.stderr,
        )
        sys.exit(1)

    data_dir: Path | None = None
    n_cycles: int = 10
    seed: int = 42

    i = 0
    while i < len(args):
        if args[i] == "--data-dir" and i + 1 < len(args):
            data_dir = Path(args[i + 1])
            i += 2
        elif args[i] == "--n-cycles" and i + 1 < len(args):
            n_cycles = int(args[i + 1])
            i += 2
        elif args[i] == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        else:
            i += 1

    if data_dir is None:
        print(
            "Error: --data-dir is required. Run 'labclaw ablation --help' for usage.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not data_dir.exists() or not data_dir.is_dir():
        print(f"Error: data-dir '{data_dir}' does not exist or is not a directory", file=sys.stderr)
        sys.exit(1)

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"Error: no .csv files found in '{data_dir}'", file=sys.stderr)
        sys.exit(1)

    all_rows: list[dict[str, Any]] = []
    for csv_path in csv_files:
        with open(csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                parsed = _coerce_row_values(row)
                if parsed:
                    all_rows.append(parsed)

    from labclaw.evolution.runner import EvolutionRunner
    from labclaw.validation.statistics import StatisticalValidator, ValidationConfig

    runner = EvolutionRunner(n_cycles=n_cycles, seed=seed)
    full_result = runner.run(all_rows)

    runner2 = EvolutionRunner(n_cycles=n_cycles, seed=seed)
    ablation_result = runner2.run_ablation(all_rows)

    # Statistical comparison
    validator = StatisticalValidator()
    cfg = ValidationConfig(min_sample_size=2)
    try:
        stat_result = validator.run_test(
            "permutation",
            full_result.fitness_scores,
            ablation_result.fitness_scores,
            config=cfg,
        )
        p_value: float | None = float(stat_result.p_value)
        significant: bool | None = bool(stat_result.significant)
    except (ValueError, ZeroDivisionError):
        p_value = None
        significant = None

    output = {
        "full": full_result.model_dump(),
        "no_evolution": ablation_result.model_dump(),
        "comparison": {
            "full_mean_fitness": float(full_result.mean_fitness),
            "ablation_mean_fitness": float(ablation_result.mean_fitness),
            "p_value": p_value,
            "significant": significant,
        },
    }
    print(json.dumps(output))


def _export_cmd(args: list[str]) -> None:
    """Export findings and provenance to NWB or JSON.

    Usage:
        labclaw export --format nwb --session SESSION_ID --output PATH
        labclaw export --format json --session SESSION_ID --output PATH
    """
    if not args or args[0] in ("-h", "--help"):
        print("Usage: labclaw export --format nwb|json --session SESSION_ID --output PATH")
        print()
        print("Options:")
        print("  --format nwb|json   Output format (default: json)")
        print("  --session ID        Session ID to export")
        print("  --output PATH       Destination file path (required)")
        if not args:
            sys.exit(1)
        return

    fmt: str = "json"
    session_id: str = ""
    output_path: Path | None = None

    i = 0
    while i < len(args):
        if args[i] == "--format" and i + 1 < len(args):
            fmt = args[i + 1]
            i += 2
        elif args[i] == "--session" and i + 1 < len(args):
            session_id = args[i + 1]
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        else:
            i += 1

    if output_path is None:
        print("Error: --output is required.", file=sys.stderr)
        sys.exit(1)

    if fmt not in ("nwb", "json"):
        print(f"Error: unsupported format {fmt!r}. Use 'nwb' or 'json'.", file=sys.stderr)
        sys.exit(1)

    from labclaw.export.nwb import NWBExporter

    session_data: dict = {
        "session_id": session_id or "unknown",
        "findings": [],
        "provenance_steps": [],
        "finding_chains": [],
        "metadata": {},
        "description": f"LabClaw export for session {session_id or 'unknown'}",
    }

    exporter = NWBExporter()
    if fmt == "nwb":
        out = exporter.export_session(session_data, output_path)
    else:
        out = exporter._export_json_stub(session_data, output_path)

    print(f"Exported to: {out}")


def _memory_cmd(args: list[str]) -> None:
    """Query or inspect the persisted session memory.

    Usage:
        labclaw memory query "search term" [--memory-root PATH] [--db PATH]
        labclaw memory stats [--memory-root PATH] [--db PATH]
    """
    sub = args[0] if args else ""

    if sub in ("-h", "--help", ""):
        print("Usage: labclaw memory <subcommand> [options]")
        print()
        print("Subcommands:")
        print("  query TERM     Search stored findings")
        print("  stats          Show finding count and retrieval rate")
        print()
        print("Options:")
        print("  --memory-root PATH  Memory root directory (default: ./memory)")
        print("  --db PATH           SQLite DB path for Tier B (optional)")
        if not sub:
            sys.exit(1)
        return

    memory_root: Path = Path("memory")
    db_path: Path | None = None
    query_term: str = ""

    i = 1
    while i < len(args):
        if args[i] == "--memory-root" and i + 1 < len(args):
            memory_root = Path(args[i + 1])
            i += 2
        elif args[i] == "--db" and i + 1 < len(args):
            db_path = Path(args[i + 1])
            i += 2
        elif sub == "query" and i == 1:
            query_term = args[i]
            i += 1
        else:
            i += 1

    from labclaw.memory.session_memory import SessionMemoryManager

    async def _run_memory_command() -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
        mgr = SessionMemoryManager(memory_root, db_path)
        await mgr.init()
        try:
            if sub == "query":
                findings = await mgr.retrieve_findings(query=query_term)
                return findings, None
            if sub == "stats":
                stats = {
                    "finding_count": len(mgr._findings),
                    "retrieval_rate": mgr.get_retrieval_rate(),
                }
                return None, stats
            raise ValueError(f"Unknown memory subcommand: {sub!r}")
        finally:
            await mgr.close()

    try:
        findings, stats = asyncio.run(_run_memory_command())
    except ValueError as exc:
        print(f"{exc}", file=sys.stderr)
        sys.exit(1)

    if findings is not None:
        print(json.dumps(findings, default=str, indent=2))
    elif stats is not None:
        print(json.dumps(stats))


def _reproduce_cmd(args: list[str]) -> None:
    """Run the pipeline twice with the same seed and verify identical output.

    Usage:
        labclaw reproduce --data-dir PATH --seed INT [--memory-root PATH]
    """
    if args and args[0] in ("-h", "--help"):
        print("Usage: labclaw reproduce --data-dir PATH --seed INT [--memory-root PATH]")
        print()
        print("Options:")
        print("  --data-dir PATH     Directory containing .csv files (required)")
        print("  --seed INT          Random seed (required for reproducibility)")
        print("  --memory-root PATH  Memory root directory (optional)")
        return

    if not args:
        print(
            "Error: --data-dir is required. Run 'labclaw reproduce --help' for usage.",
            file=sys.stderr,
        )
        sys.exit(1)

    data_dir: Path | None = None
    seed: int = 42
    memory_root: Path | None = None

    i = 0
    while i < len(args):
        if args[i] == "--data-dir" and i + 1 < len(args):
            data_dir = Path(args[i + 1])
            i += 2
        elif args[i] == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        elif args[i] == "--memory-root" and i + 1 < len(args):
            memory_root = Path(args[i + 1])
            i += 2
        else:
            i += 1

    if data_dir is None:
        print(
            "Error: --data-dir is required. Run 'labclaw reproduce --help' for usage.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not data_dir.exists() or not data_dir.is_dir():
        print(f"Error: data-dir '{data_dir}' does not exist or is not a directory", file=sys.stderr)
        sys.exit(1)

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"Error: no .csv files found in '{data_dir}'", file=sys.stderr)
        sys.exit(1)

    all_rows: list[dict[str, Any]] = []
    for csv_path in csv_files:
        with open(csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                parsed = _coerce_row_values(row)
                if parsed:
                    all_rows.append(parsed)

    from labclaw.orchestrator.loop import ScientificLoop
    from labclaw.orchestrator.steps import (
        AnalyzeStep,
        AskStep,
        ConcludeStep,
        ExperimentStep,
        HypothesizeStep,
        ObserveStep,
        PredictStep,
    )

    def _build_steps() -> list:
        conclude = ConcludeStep(memory_root=memory_root)
        return [
            ObserveStep(),
            AskStep(),
            HypothesizeStep(llm_provider=None),
            PredictStep(),
            ExperimentStep(),
            AnalyzeStep(),
            conclude,
        ]

    # Run 1
    random.seed(seed)
    loop1 = ScientificLoop(steps=_build_steps())
    result1 = asyncio.run(loop1.run_cycle(all_rows))

    # Run 2
    random.seed(seed)
    loop2 = ScientificLoop(steps=_build_steps())
    result2 = asyncio.run(loop2.run_cycle(all_rows))

    def _normalize(d: dict) -> None:
        d["cycle_id"] = "X"
        d["total_duration"] = 0.0
        # Redact embedded UUIDs in finding strings (e.g. pattern IDs in per-pattern lines)
        d["findings"] = [_uuid_re.sub("<uuid>", f) for f in d.get("findings", [])]
        # finding_chains contain per-run UUIDs and timestamps — exclude from comparison
        fc = d.get("final_context", {})
        fc.pop("finding_chains", None)
        d["final_context"] = fc

    d1 = result1.model_dump()
    d2 = result2.model_dump()
    _normalize(d1)
    _normalize(d2)

    reproducible = d1 == d2
    output: dict = {
        "reproducible": reproducible,
        "run1": result1.model_dump(),
        "run2": result2.model_dump(),
    }
    if not reproducible:
        output["diff"] = [k for k in d1 if d1[k] != d2[k]]
    else:
        output["diff"] = None

    print(json.dumps(output))
    if not reproducible:
        sys.exit(1)


if __name__ == "__main__":
    main()
