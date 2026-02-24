"""LabClaw Daemon — 24/7 self-improving lab intelligence service.

Runs the full pipeline continuously:
  Edge Watcher → Session Chronicle → Discovery → Evolution → Memory

Usage:
    python -m labclaw.daemon --data-dir /opt/labclaw/data --port 18800
"""

from __future__ import annotations

import argparse
import csv
import logging
import signal
import subprocess
import sys
import threading
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import uvicorn

from labclaw.api.app import app
from labclaw.api.deps import (
    get_evolution_engine,
    get_pattern_miner,
    get_tier_a_backend,
    set_data_dir,
    set_memory_root,
)
from labclaw.core.events import event_registry
from labclaw.core.schemas import EvolutionTarget, LabEvent
from labclaw.discovery.mining import MiningConfig
from labclaw.edge.watcher import EdgeWatcher
from labclaw.memory.markdown import MemoryEntry

logger = logging.getLogger("labclaw")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PORT = 18800
DASHBOARD_PORT = 18801
DISCOVERY_INTERVAL_SECONDS = 300  # 5 minutes
EVOLUTION_INTERVAL_SECONDS = 1800  # 30 minutes
MIN_ROWS_FOR_MINING = 10


# ---------------------------------------------------------------------------
# Data accumulator — collects CSV/TSV rows from detected files
# ---------------------------------------------------------------------------


class DataAccumulator:
    """Thread-safe accumulator for data rows from detected files."""

    def __init__(self) -> None:
        self._rows: deque[dict[str, Any]] = deque(maxlen=100_000)
        self._file_row_offsets: dict[str, int] = {}
        self._files_in_progress: set[str] = set()
        self._lock = threading.Lock()

    def ingest_file(self, path: Path) -> int:
        """Parse a CSV/TSV file and add rows. Returns number of rows added."""
        str_path = str(path)

        if path.suffix.lower() not in (".csv", ".tsv", ".txt"):
            logger.debug("Skipping non-tabular file: %s", path)
            return 0

        with self._lock:
            if str_path in self._files_in_progress:
                return 0
            previous_offset = self._file_row_offsets.get(str_path, 0)
            self._files_in_progress.add(str_path)

        try:
            delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
            with path.open(newline="") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                new_rows: list[dict[str, Any]] = []
                for row in reader:
                    parsed: dict[str, Any] = {}
                    for k, v in row.items():
                        if k is None:
                            continue
                        try:
                            parsed[k] = float(v)
                        except (ValueError, TypeError):
                            parsed[k] = v
                    if parsed:
                        new_rows.append(parsed)

            if len(new_rows) < previous_offset:
                logger.info(
                    "File %s appears truncated; resetting ingest cursor (%d -> 0)",
                    path,
                    previous_offset,
                )
                previous_offset = 0
            new_rows = new_rows[previous_offset:]

            with self._lock:
                total_rows = len(self._rows)
                if new_rows:
                    self._file_row_offsets[str_path] = previous_offset + len(new_rows)
                    self._rows.extend(new_rows)
                    total_rows = len(self._rows)

            if not new_rows:
                logger.debug("No new rows to ingest from %s", path)
                return 0

            logger.info("Ingested %d rows from %s (total: %d)", len(new_rows), path, total_rows)
            return len(new_rows)

        except Exception:
            logger.exception("Failed to ingest file: %s", path)
            return 0
        finally:
            with self._lock:
                self._files_in_progress.discard(str_path)

    def get_all_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._rows)

    @property
    def total_rows(self) -> int:
        with self._lock:
            return len(self._rows)

    @property
    def files_processed(self) -> int:
        with self._lock:
            return len(self._file_row_offsets)


# ---------------------------------------------------------------------------
# Main daemon
# ---------------------------------------------------------------------------


class LabClawDaemon:
    """24/7 lab intelligence daemon."""

    def __init__(
        self,
        data_dir: Path,
        memory_root: Path,
        host: str = "127.0.0.1",
        api_port: int = DEFAULT_PORT,
        dashboard_port: int = DASHBOARD_PORT,
        discovery_interval: int = DISCOVERY_INTERVAL_SECONDS,
        evolution_interval: int = EVOLUTION_INTERVAL_SECONDS,
    ) -> None:
        self.data_dir = data_dir
        self.memory_root = memory_root
        self.host = host
        self.api_port = api_port
        self.dashboard_port = dashboard_port
        self.discovery_interval = discovery_interval
        self.evolution_interval = evolution_interval

        self._stop_event = threading.Event()
        self._accumulator = DataAccumulator()
        self._watcher: EdgeWatcher | None = None
        self._dashboard_proc: subprocess.Popen | None = None
        self._dashboard_log: TextIO | None = None
        self._discovery_count = 0
        self._evolution_count = 0

        # Initialize shared state
        set_memory_root(memory_root)
        set_data_dir(data_dir)

    def start(self) -> None:
        """Start all components and block until shutdown."""
        logger.info("=" * 60)
        logger.info("LabClaw Daemon starting")
        logger.info("  Data dir:     %s", self.data_dir)
        logger.info("  Memory root:  %s", self.memory_root)
        logger.info("  API port:     %s", self.api_port)
        logger.info("  Dashboard:    %s", self.dashboard_port)
        logger.info("  Discovery:    every %ds", self.discovery_interval)
        logger.info("  Evolution:    every %ds", self.evolution_interval)
        logger.info("=" * 60)

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.memory_root.mkdir(parents=True, exist_ok=True)

        # Load plugins
        try:
            from labclaw.plugins.loader import PluginLoader

            loader = PluginLoader()
            loaded = loader.load_all(local_dir=self.data_dir.parent / "plugins")
            if loaded:
                logger.info("Loaded %d plugins: %s", len(loaded), ", ".join(loaded))
        except Exception:
            logger.warning("Plugin loading failed", exc_info=True)

        # Load persisted evolution state
        state_path = self.memory_root / "evolution_state.json"
        get_evolution_engine().load_state(state_path)

        # Ingest any existing files in data_dir
        self._ingest_existing_files()

        # Start edge watcher
        self._start_watcher()

        # Start dashboard (Streamlit) in subprocess
        self._start_dashboard()

        # Start background loops
        discovery_thread = threading.Thread(
            target=self._discovery_loop, daemon=True, name="discovery-loop",
        )
        evolution_thread = threading.Thread(
            target=self._evolution_loop, daemon=True, name="evolution-loop",
        )
        discovery_thread.start()
        evolution_thread.start()

        # Log initial state to memory
        self._log_to_memory("system", "daemon_start", f"LabClaw started. Watching {self.data_dir}")

        # Run API server (blocks)
        try:
            uvicorn.run(
                app,
                host=self.host,
                port=self.api_port,
                log_level="info",
            )
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Graceful shutdown."""
        logger.info("LabClaw shutting down...")
        self._stop_event.set()

        if self._watcher:
            self._watcher.stop_all()

        if self._dashboard_proc:
            try:
                if self._dashboard_proc.poll() is None:
                    self._dashboard_proc.terminate()
                    try:
                        self._dashboard_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning(
                            "Dashboard process did not terminate within timeout; killing"
                        )
                        self._dashboard_proc.kill()
                        try:
                            self._dashboard_proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            logger.error("Dashboard process did not exit after kill()")
            except Exception:
                logger.warning("Error while stopping dashboard process", exc_info=True)
            finally:
                self._dashboard_proc = None
        if self._dashboard_log:
            self._dashboard_log.close()
            self._dashboard_log = None

        self._log_to_memory(
            "system", "daemon_stop",
            f"LabClaw stopped. Discoveries: {self._discovery_count}, "
            f"Evolutions: {self._evolution_count}, "
            f"Files: {self._accumulator.files_processed}, "
            f"Rows: {self._accumulator.total_rows}",
        )
        logger.info("LabClaw stopped.")

    # -----------------------------------------------------------------------
    # Edge watcher
    # -----------------------------------------------------------------------

    def _start_watcher(self) -> None:
        self._watcher = EdgeWatcher()

        def _ingest_from_event(event: LabEvent) -> None:
            raw_path = event.payload.get("path")
            if not raw_path:
                logger.warning("hardware.file.detected missing 'path' payload: %s", event.payload)
                return
            self._accumulator.ingest_file(Path(str(raw_path)))

        event_registry.subscribe(
            "hardware.file.detected",
            _ingest_from_event,
        )

        self._watcher.watch(self.data_dir, device_id="labclaw-watcher", recursive=True)
        logger.info("Edge watcher started on %s", self.data_dir)

    def _ingest_existing_files(self) -> None:
        """Ingest any data files already present in data_dir."""
        count = 0
        for path in sorted(self.data_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in (".csv", ".tsv", ".txt"):
                rows = self._accumulator.ingest_file(path)
                if rows > 0:
                    count += 1
        if count:
            logger.info(
                "Ingested %d existing files (%d total rows)",
                count,
                self._accumulator.total_rows,
            )

    # -----------------------------------------------------------------------
    # Discovery loop
    # -----------------------------------------------------------------------

    def _discovery_loop(self) -> None:
        """Periodic discovery: mine patterns + generate hypotheses."""
        while not self._stop_event.is_set():
            self._stop_event.wait(self.discovery_interval)
            if self._stop_event.is_set():
                break
            self._run_discovery()

    def _run_discovery(self) -> None:
        rows = self._accumulator.get_all_rows()
        if len(rows) < MIN_ROWS_FOR_MINING:
            logger.info(
                "Discovery: %d rows (< %d minimum), skipping",
                len(rows), MIN_ROWS_FOR_MINING,
            )
            return

        logger.info("Discovery: running orchestrator on %d rows...", len(rows))
        try:
            import asyncio

            from labclaw.api.deps import get_llm_provider
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

            llm = get_llm_provider()
            loop = ScientificLoop(steps=[
                ObserveStep(),
                AskStep(),
                HypothesizeStep(llm_provider=llm),
                PredictStep(),
                ExperimentStep(),
                AnalyzeStep(),
                ConcludeStep(),
            ])
            result = asyncio.run(loop.run_cycle(rows))

            self._discovery_count += 1
            logger.info(
                "Discovery #%d: %d patterns, %d hypotheses (%.1fs)",
                self._discovery_count, result.patterns_found,
                result.hypotheses_generated, result.total_duration,
            )

            # Log summary to memory
            self._log_to_memory(
                "labclaw", "discovery",
                f"Cycle {result.cycle_id[:8]}: {result.patterns_found} patterns, "
                f"{result.hypotheses_generated} hypotheses",
            )
        except Exception:
            logger.exception("Discovery loop error")

    # -----------------------------------------------------------------------
    # Evolution loop
    # -----------------------------------------------------------------------

    def _evolution_loop(self) -> None:
        """Periodic evolution: measure fitness, propose improvements, run cycles."""
        while not self._stop_event.is_set():
            self._stop_event.wait(self.evolution_interval)
            if self._stop_event.is_set():
                break
            self._run_evolution()

    def _run_evolution(self) -> None:
        """Improved evolution loop that tracks cycles across intervals."""
        rows = self._accumulator.get_all_rows()
        if len(rows) < MIN_ROWS_FOR_MINING:
            return

        try:
            engine = get_evolution_engine()
            target = EvolutionTarget.ANALYSIS_PARAMS

            # Compute current fitness
            miner = get_pattern_miner()
            config = MiningConfig(min_sessions=3)
            result = miner.mine(rows, config)
            numeric_cols = [
                k for k, v in rows[0].items() if isinstance(v, (int, float))
            ] if rows else []

            metrics = {
                "pattern_count": float(len(result.patterns)),
                "data_rows": float(len(rows)),
                "coverage": float(len(result.patterns)) / max(len(numeric_cols), 1),
            }
            current_fitness = engine.measure_fitness(
                target=target, metrics=metrics, data_points=len(rows),
            )

            # Try to advance existing active cycles
            active_cycles = engine.get_active_cycles()
            for cycle in active_cycles:
                if engine.should_advance(cycle.cycle_id):
                    candidate_diff = cycle.candidate.config_diff or {}
                    base_dict = {
                        k: v for k, v in config.__dict__.items()
                        if not k.startswith("_")
                    }
                    base_dict.update(candidate_diff)
                    try:
                        candidate_config = MiningConfig(**base_dict)
                    except Exception:
                        candidate_config = config
                    new_result = miner.mine(rows, candidate_config)
                    improved_metrics = {
                        "pattern_count": float(len(new_result.patterns)),
                        "data_rows": float(len(rows)),
                        "coverage": (
                            float(len(new_result.patterns)) / max(len(numeric_cols), 1)
                            if numeric_cols else 0.0
                        ),
                    }
                    improved_fitness = engine.measure_fitness(
                        target=target, metrics=improved_metrics, data_points=len(rows),
                    )
                    updated = engine.advance_stage(cycle.cycle_id, improved_fitness)
                    self._evolution_count += 1
                    self._log_to_memory(
                        "labclaw", "evolution",
                        f"Cycle {cycle.cycle_id[:8]} advanced to "
                        f"{updated.stage.value}",
                    )

            # If no active cycles, start a new one
            if not active_cycles:
                candidates = engine.propose_candidates(target, n=1)
                if candidates:
                    cycle = engine.start_cycle(candidates[0], current_fitness)
                    self._evolution_count += 1
                    self._log_to_memory(
                        "labclaw", "evolution",
                        f"New cycle {cycle.cycle_id[:8]} started",
                    )

            # Persist state
            state_path = self.memory_root / "evolution_state.json"
            engine.persist_state(state_path)

        except Exception:
            logger.exception("Evolution loop error")

    # -----------------------------------------------------------------------
    # Memory logging
    # -----------------------------------------------------------------------

    def _log_to_memory(self, entity_id: str, category: str, detail: str) -> None:
        try:
            backend = get_tier_a_backend()
            entry = MemoryEntry(
                timestamp=datetime.now(UTC),
                category=category,
                detail=detail,
            )
            backend.append_memory(entity_id, entry)
        except Exception:
            logger.warning("Failed to write memory entry: %s/%s", entity_id, category)

    # -----------------------------------------------------------------------
    # Dashboard
    # -----------------------------------------------------------------------

    def _start_dashboard(self) -> None:
        dashboard_path = Path(__file__).parent / "dashboard" / "app.py"
        try:
            log_dir = self.memory_root.parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            dashboard_log = open(log_dir / "dashboard.log", "a")  # noqa: SIM115
            self._dashboard_log = dashboard_log
            self._dashboard_proc = subprocess.Popen(
                [
                    sys.executable, "-m", "streamlit", "run",
                    str(dashboard_path),
                    "--server.port", str(self.dashboard_port),
                    "--server.address", "127.0.0.1",
                    "--server.headless", "true",
                    "--browser.gatherUsageStats", "false",
                ],
                stdout=subprocess.DEVNULL,
                stderr=dashboard_log,
            )
            logger.info("Streamlit dashboard started on port %d", self.dashboard_port)
        except Exception:
            logger.warning("Failed to start Streamlit dashboard", exc_info=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="LabClaw — 24/7 lab intelligence daemon")
    parser.add_argument(
        "--data-dir", type=Path, default=Path("/opt/labclaw/data"),
        help="Directory to watch for new data files (default: /opt/labclaw/data)",
    )
    parser.add_argument(
        "--memory-root", type=Path, default=Path("/opt/labclaw/memory"),
        help="Root directory for Tier A memory (default: /opt/labclaw/memory)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="API server bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"API server port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--dashboard-port", type=int, default=DASHBOARD_PORT,
        help=f"Streamlit dashboard port (default: {DASHBOARD_PORT})",
    )
    parser.add_argument(
        "--discovery-interval", type=int, default=DISCOVERY_INTERVAL_SECONDS,
        help=f"Seconds between discovery runs (default: {DISCOVERY_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--evolution-interval", type=int, default=EVOLUTION_INTERVAL_SECONDS,
        help=f"Seconds between evolution runs (default: {EVOLUTION_INTERVAL_SECONDS})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    daemon = LabClawDaemon(
        data_dir=args.data_dir,
        memory_root=args.memory_root,
        host=args.host,
        api_port=args.port,
        dashboard_port=args.dashboard_port,
        discovery_interval=args.discovery_interval,
        evolution_interval=args.evolution_interval,
    )

    # Handle signals
    def handle_signal(signum, frame):  # noqa: ANN001
        daemon.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    daemon.start()


if __name__ == "__main__":
    main()
