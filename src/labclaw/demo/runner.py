"""Demo runner — runs an abbreviated LabClaw cycle for quick onboarding.

Usage via CLI:
    labclaw demo [--domain generic|neuroscience|chemistry] [--keep]
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from labclaw.api.deps import (
    get_evolution_engine,
    get_pattern_miner,
    reset_all,
    set_data_dir,
    set_memory_root,
)
from labclaw.core.schemas import EvolutionStage, EvolutionTarget
from labclaw.daemon import DataAccumulator
from labclaw.discovery.mining import MiningConfig
from labclaw.orchestrator.loop import ScientificLoop

logger = logging.getLogger(__name__)

_SAMPLE_DATA_DIR = Path(__file__).parent / "data"

_DOMAIN_FILES: dict[str, str] = {
    "generic": "generic_experiment.csv",
    "neuroscience": "neuroscience_behavior.csv",
    "chemistry": "chemistry_reactions.csv",
}

# ---------------------------------------------------------------------------
# Terminal formatting helpers (no rich dependency)
# ---------------------------------------------------------------------------

_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_RED = "\033[31m"
_RESET = "\033[0m"


def _header(text: str) -> None:
    width = 60
    print()
    print(f"{_BOLD}{_CYAN}{'=' * width}{_RESET}")
    print(f"{_BOLD}{_CYAN}  {text}{_RESET}")
    print(f"{_BOLD}{_CYAN}{'=' * width}{_RESET}")


def _step(icon: str, text: str) -> None:
    print(f"  {icon} {text}")


def _kv(key: str, value: Any) -> None:
    print(f"    {_DIM}{key}:{_RESET} {value}")


# ---------------------------------------------------------------------------
# DemoRunner
# ---------------------------------------------------------------------------


class DemoRunner:
    """Creates temp workspace, runs one scientific cycle + evolution, shows results."""

    def __init__(self, domain: str = "generic", keep: bool = False) -> None:
        if domain not in _DOMAIN_FILES:
            raise ValueError(f"Unknown domain {domain!r}. Choose from: {list(_DOMAIN_FILES)}")
        self.domain = domain
        self.keep = keep
        self._tmpdir: str | None = None
        self._root: Path | None = None

    def run(self) -> None:
        """Entry point — sets up workspace and runs the demo."""
        self._tmpdir = tempfile.mkdtemp(prefix="labclaw-demo-")
        self._root = Path(self._tmpdir)
        data_dir = self._root / "data"
        memory_dir = self._root / "memory"
        data_dir.mkdir()
        memory_dir.mkdir()

        # Copy sample data
        src_csv = _SAMPLE_DATA_DIR / _DOMAIN_FILES[self.domain]
        dst_csv = data_dir / src_csv.name
        shutil.copy2(src_csv, dst_csv)

        _header(f"LabClaw Demo — {self.domain}")
        _step(">>", f"Workspace: {self._root}")
        _step(">>", f"Sample data: {dst_csv.name}")
        print()

        # Configure singletons to point at our temp dirs
        reset_all()
        set_data_dir(data_dir)
        set_memory_root(memory_dir)

        try:
            self._run_pipeline(dst_csv, memory_dir)
        finally:
            if self.keep:
                print(f"\n  {_YELLOW}Keeping workspace at: {self._root}{_RESET}")
            else:
                shutil.rmtree(self._tmpdir, ignore_errors=True)
                print(f"\n  {_DIM}Workspace cleaned up.{_RESET}")
            # Restore singletons
            reset_all()

    def _run_pipeline(self, csv_path: Path, memory_dir: Path) -> None:
        # 1. Ingest data
        _header("Step 1: Data Ingestion")
        accumulator = DataAccumulator()
        n_rows = accumulator.ingest_file(csv_path)
        _step(f"{_GREEN}OK{_RESET}", f"Ingested {n_rows} rows from {csv_path.name}")

        rows = accumulator.get_all_rows()
        if not rows:
            print(f"  {_RED}No data rows found — aborting.{_RESET}")
            return

        # Show a preview
        _kv("Columns", ", ".join(rows[0].keys()))
        _kv("Rows", len(rows))

        # 2. Pattern mining
        _header("Step 2: Pattern Mining")
        miner = get_pattern_miner()
        config = MiningConfig(min_sessions=3)
        result = miner.mine(rows, config)
        _step(
            f"{_GREEN}OK{_RESET}",
            f"Found {len(result.patterns)} patterns",
        )
        for i, p in enumerate(result.patterns[:5], 1):
            _kv(f"Pattern {i}", f"[{p.pattern_type}] {p.description}")
            _kv("  confidence", f"{p.confidence:.2f}")
        if len(result.patterns) > 5:
            _step("...", f"({len(result.patterns) - 5} more)")

        # 3. Scientific loop
        _header("Step 3: Scientific Method Cycle")
        loop = ScientificLoop()
        cycle_result = asyncio.run(loop.run_cycle(rows))
        _step(
            f"{_GREEN}OK{_RESET}" if cycle_result.success else f"{_RED}FAIL{_RESET}",
            f"Cycle {cycle_result.cycle_id[:8]} completed in {cycle_result.total_duration:.2f}s",
        )
        _kv("Steps completed", [s.value for s in cycle_result.steps_completed])
        _kv("Steps skipped", [s.value for s in cycle_result.steps_skipped])
        _kv("Patterns found", cycle_result.patterns_found)
        _kv("Hypotheses generated", cycle_result.hypotheses_generated)

        # 4. Evolution cycle
        _header("Step 4: Evolution")
        engine = get_evolution_engine()
        target = EvolutionTarget.ANALYSIS_PARAMS

        numeric_cols = [k for k, v in rows[0].items() if isinstance(v, (int, float))]
        metrics = {
            "pattern_count": float(len(result.patterns)),
            "data_rows": float(len(rows)),
            "coverage": float(len(result.patterns)) / max(len(numeric_cols), 1),
        }
        baseline = engine.measure_fitness(target=target, metrics=metrics, data_points=len(rows))
        _step(f"{_GREEN}OK{_RESET}", "Baseline fitness measured")
        _kv("Metrics", metrics)

        candidates = engine.propose_candidates(target, n=1)
        if candidates:
            cand = candidates[0]
            _step(">>", f"Candidate: {cand.description}")
            _kv("Config diff", cand.config_diff)

            cycle = engine.start_cycle(cand, baseline)
            _step(f"{_GREEN}OK{_RESET}", f"Cycle {cycle.cycle_id[:8]} started (BACKTEST)")

            # Apply candidate and re-mine
            diff = cand.config_diff or {}
            base_dict = {k: v for k, v in config.__dict__.items() if not k.startswith("_")}
            base_dict.update(diff)
            try:
                cand_config = MiningConfig(**base_dict)
            except Exception:
                cand_config = config
            new_result = miner.mine(rows, cand_config)
            new_metrics = {
                "pattern_count": float(len(new_result.patterns)),
                "data_rows": float(len(rows)),
                "coverage": (
                    float(len(new_result.patterns)) / max(len(numeric_cols), 1)
                    if numeric_cols
                    else 0.0
                ),
            }
            new_fitness = engine.measure_fitness(
                target=target,
                metrics=new_metrics,
                data_points=len(rows),
            )

            # Advance through stages: BACKTEST -> SHADOW -> CANARY -> PROMOTED
            _kv("New metrics", new_metrics)
            stages_to_advance = ["SHADOW", "CANARY", "PROMOTED"]
            for target_name in stages_to_advance:
                updated = engine.advance_stage(cycle.cycle_id, new_fitness)
                _step(f"{_GREEN}OK{_RESET}", f"Advanced to {updated.stage.value}")
                if updated.stage == EvolutionStage.ROLLED_BACK:
                    _step(
                        f"{_YELLOW}ROLLED BACK{_RESET}",
                        f"Reason: {updated.rollback_reason}",
                    )
                    break
            else:
                if updated.promoted:
                    _step(
                        f"{_GREEN}PROMOTED{_RESET}",
                        "Candidate passed all stages!",
                    )

            # Persist
            state_path = memory_dir / "evolution_state.json"
            engine.persist_state(state_path)
            _step(f"{_GREEN}OK{_RESET}", f"State persisted to {state_path.name}")
        else:
            _step(f"{_YELLOW}SKIP{_RESET}", "No candidates proposed")

        # 5. Summary
        _header("Demo Complete")
        _step(">>", f"Domain: {self.domain}")
        _step(">>", f"Data: {n_rows} rows, {len(numeric_cols)} numeric columns")
        _step(">>", f"Patterns: {len(result.patterns)}")
        _step(">>", f"Hypotheses: {cycle_result.hypotheses_generated}")
        _step(">>", f"Evolution: {updated.stage.value if candidates else 'no candidates'}")
        print()
        if self.keep and self._root:
            _step(">>", f"Explore results at: {self._root}")
        print(f"  Run '{_BOLD}labclaw serve{_RESET}' to start the full 24/7 daemon.")
        print()
