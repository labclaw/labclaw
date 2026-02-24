"""MVP integration test: file -> memory -> discovery -> report.

Tests the complete data flow that forms the minimum viable demo:
1. Edge watcher detects new data files
2. Quality checker validates them
3. Session chronicle tracks the session
4. Memory records the session data
5. Discovery mines patterns from accumulated data
6. Validator confirms findings
7. Events flow through the entire pipeline
"""

from __future__ import annotations

import csv
import random
from datetime import UTC, datetime
from pathlib import Path

import pytest
from watchdog.events import FileCreatedEvent

from labclaw.core.events import event_registry
from labclaw.core.schemas import FileReference, LabEvent, QualityLevel
from labclaw.discovery.hypothesis import HypothesisGenerator, HypothesisInput
from labclaw.discovery.mining import MiningConfig, PatternMiner
from labclaw.edge.quality import QualityChecker
from labclaw.edge.sentinel import AlertRule, Sentinel
from labclaw.edge.session_chronicle import SessionChronicle
from labclaw.edge.watcher import FileDetectedHandler
from labclaw.memory.markdown import MemoryEntry, TierABackend
from labclaw.validation.provenance import ProvenanceTracker
from labclaw.validation.statistics import (
    ProvenanceStep,
    StatisticalValidator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class EventCapture:
    """Captures emitted events for assertion in tests."""

    def __init__(self) -> None:
        self.events: list[LabEvent] = []

    def __call__(self, event: LabEvent) -> None:
        self.events.append(event)

    @property
    def names(self) -> list[str]:
        return [e.event_name.full for e in self.events]

    def count(self, name: str) -> int:
        return sum(1 for e in self.events if e.event_name.full == name)


def _generate_csv_files(
    directory: Path,
    count: int = 20,
    seed: int = 42,
) -> list[Path]:
    """Generate synthetic CSV files with control vs treatment data.

    Control group (first half):  latency ~ N(10, 1), accuracy ~ N(0.8, 0.05)
    Treatment group (second half): latency ~ N(12, 1), accuracy ~ N(0.7, 0.05)
    Latency and accuracy are anti-correlated by construction.
    """
    rng = random.Random(seed)
    files: list[Path] = []

    for i in range(count):
        group = "control" if i < count // 2 else "treatment"

        if group == "control":
            latency = rng.gauss(10.0, 1.0)
            accuracy = 0.95 - 0.01 * latency + rng.gauss(0.0, 0.02)
        else:
            latency = rng.gauss(12.0, 1.0)
            accuracy = 0.95 - 0.01 * latency + rng.gauss(0.0, 0.02)

        temperature = rng.gauss(37.0, 0.3)

        path = directory / f"session_{i:03d}.csv"
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["session_id", "group", "latency", "accuracy", "temperature"],
            )
            writer.writeheader()
            writer.writerow({
                "session_id": f"s{i:03d}",
                "group": group,
                "latency": round(latency, 4),
                "accuracy": round(accuracy, 4),
                "temperature": round(temperature, 4),
            })
        files.append(path)

    return files


def _parse_csv_to_dicts(files: list[Path]) -> list[dict]:
    """Parse CSV files into a list of dicts with numeric casting."""
    rows: list[dict] = []
    for path in files:
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({
                    "session_id": row["session_id"],
                    "group": row["group"],
                    "latency": float(row["latency"]),
                    "accuracy": float(row["accuracy"]),
                    "temperature": float(row["temperature"]),
                })
    return rows


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_event_registry():
    """Reset the global event registry before and after each test."""
    event_registry.clear()
    # Re-register events by re-importing the modules that register on import.
    # Simpler: just re-register the events we need.
    _events = [
        "hardware.file.detected",
        "hardware.quality.checked",
        "session.chronicle.started",
        "session.recording.added",
        "session.chronicle.ended",
        "sentinel.alert.raised",
        "sentinel.check.completed",
        "memory.tier_a.created",
        "memory.tier_a.updated",
        "memory.search.executed",
        "discovery.pattern.found",
        "discovery.mining.completed",
        "discovery.hypothesis.created",
        "validation.test.completed",
        "validation.report.generated",
        "validation.provenance.built",
    ]
    for evt in _events:
        if not event_registry.is_registered(evt):
            event_registry.register(evt)
    yield
    event_registry.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMVPPipeline:
    """End-to-end MVP pipeline tests."""

    def test_mvp_pipeline_end_to_end(self, tmp_path: Path) -> None:
        """Full MVP pipeline: detect files -> analyze -> discover -> validate."""

        # ---- 1. Set up infrastructure ----
        capture = EventCapture()
        event_registry.subscribe("*", capture)

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        memory_root = tmp_path / "memory"
        memory_root.mkdir()

        memory = TierABackend(root=memory_root)
        chronicle = SessionChronicle(memory=memory)
        quality_checker = QualityChecker()
        sentinel = Sentinel(rules=[
            AlertRule(
                name="empty_file",
                metric_name="file_non_empty",
                threshold=1.0,
                comparison="below",
                level=QualityLevel.WARNING,
            ),
            AlertRule(
                name="missing_file",
                metric_name="file_exists",
                threshold=1.0,
                comparison="below",
                level=QualityLevel.CRITICAL,
            ),
        ])
        miner = PatternMiner()
        validator = StatisticalValidator()
        hypothesis_gen = HypothesisGenerator()
        provenance_tracker = ProvenanceTracker()

        # ---- 2. Simulate file detection (20 CSV files) ----
        csv_files = _generate_csv_files(data_dir, count=20, seed=42)
        assert len(csv_files) == 20

        handler = FileDetectedHandler(device_id="behavior-rig-01")
        detected_refs: list[FileReference] = []

        for csv_path in csv_files:
            event = FileCreatedEvent(str(csv_path))
            handler.on_created(event)

        detected_refs = handler.detected_files
        assert len(detected_refs) == 20
        assert capture.count("hardware.file.detected") == 20

        # ---- 3. Quality check each file ----
        quality_metrics = []
        for file_ref in detected_refs:
            metric = quality_checker.check_file(file_ref)
            assert metric.level == QualityLevel.GOOD
            quality_metrics.append(metric)

            # Run sentinel check
            alerts = sentinel.check_metric(metric)
            assert len(alerts) == 0  # All files are valid

        assert capture.count("hardware.quality.checked") == 20

        # ---- 4. Create a session and add recordings ----
        session = chronicle.start_session(
            operator_id="researcher-01",
            experiment_id="exp-behavior-001",
        )
        assert capture.count("session.chronicle.started") == 1

        for file_ref in detected_refs:
            chronicle.add_recording(
                session_id=session.node_id,
                file_ref=file_ref,
                modality="behavioral_csv",
                device_id="behavior-rig-01",
            )

        assert capture.count("session.recording.added") == 20

        recordings = chronicle.get_recordings(session.node_id)
        assert len(recordings) == 20

        ended_session = chronicle.end_session(session.node_id)
        assert ended_session.duration_seconds is not None
        assert capture.count("session.chronicle.ended") == 1

        # ---- 5. Record session data in memory ----
        from labclaw.memory.markdown import MarkdownDoc

        memory.write_soul(
            entity_id="exp-behavior-001",
            doc=MarkdownDoc(
                path=memory_root / "exp-behavior-001" / "SOUL.md",
                frontmatter={
                    "name": "Behavior Experiment 001",
                    "type": "experiment",
                    "status": "active",
                },
                content="# Behavior Experiment 001\n\nControl vs treatment latency study.",
            ),
        )
        assert capture.count("memory.tier_a.created") == 1

        memory.append_memory(
            entity_id="exp-behavior-001",
            entry=MemoryEntry(
                timestamp=datetime.now(UTC),
                category="session",
                detail=(
                    f"Session {session.node_id}: "
                    f"{len(recordings)} recordings from behavior-rig-01. "
                    f"Duration: {ended_session.duration_seconds:.1f}s."
                ),
            ),
        )
        assert capture.count("memory.tier_a.updated") >= 1

        # Verify memory is searchable
        results = memory.search("behavior")
        assert len(results) > 0
        assert any(r.entity_id == "exp-behavior-001" for r in results)

        # ---- 6. Run discovery on accumulated data ----
        data_dicts = _parse_csv_to_dicts(csv_files)
        assert len(data_dicts) == 20

        mining_config = MiningConfig(
            min_sessions=10,
            correlation_threshold=0.5,
            anomaly_z_threshold=2.0,
        )
        mining_result = miner.mine(data_dicts, config=mining_config)

        # Should find at least the correlation between latency and accuracy
        correlation_patterns = [
            p for p in mining_result.patterns if p.pattern_type == "correlation"
        ]
        assert len(correlation_patterns) >= 1, (
            f"Expected at least 1 correlation pattern, got {len(correlation_patterns)}. "
            f"All patterns: {[p.pattern_type for p in mining_result.patterns]}"
        )

        # Check that latency-accuracy correlation was found
        latency_accuracy = [
            p for p in correlation_patterns
            if (
                "latency" in p.evidence.get("col_a", "")
                and "accuracy" in p.evidence.get("col_b", "")
            ) or (
                "accuracy" in p.evidence.get("col_a", "")
                and "latency" in p.evidence.get("col_b", "")
            )
        ]
        assert len(latency_accuracy) >= 1, "Expected latency-accuracy correlation"

        assert capture.count("discovery.mining.completed") == 1
        assert capture.count("discovery.pattern.found") >= 1

        # Generate hypotheses from patterns
        hyp_input = HypothesisInput(
            patterns=mining_result.patterns,
            context="Behavioral experiment comparing control and treatment groups",
        )
        hypotheses = hypothesis_gen.generate(hyp_input)
        assert len(hypotheses) >= 1, "Expected at least 1 hypothesis"
        assert capture.count("discovery.hypothesis.created") >= 1

        # Verify hypotheses have required fields
        for h in hypotheses:
            assert h.statement
            assert h.testable is True
            assert h.confidence > 0.0

        # ---- 7. Validate a finding ----
        # Split data into control and treatment groups
        control_latency = [d["latency"] for d in data_dicts if d["group"] == "control"]
        treatment_latency = [d["latency"] for d in data_dicts if d["group"] == "treatment"]

        assert len(control_latency) == 10
        assert len(treatment_latency) == 10

        # Run t-test
        t_test_result = validator.run_test(
            "t_test",
            group_a=control_latency,
            group_b=treatment_latency,
        )
        assert t_test_result.significant, (
            f"Expected significant difference between control and treatment. "
            f"p={t_test_result.p_value:.4f}, effect_size={t_test_result.effect_size}"
        )
        assert t_test_result.p_value < 0.05
        assert t_test_result.effect_size is not None
        assert abs(t_test_result.effect_size) > 0.5  # Large effect

        assert capture.count("validation.test.completed") == 1

        # Build provenance chain
        provenance_steps = [
            ProvenanceStep(
                node_id="raw-data",
                node_type="recording",
                description="20 CSV files from behavior-rig-01",
            ),
            ProvenanceStep(
                node_id=session.node_id,
                node_type="session",
                description="Behavioral recording session",
            ),
            ProvenanceStep(
                node_id=mining_result.patterns[0].pattern_id,
                node_type="pattern",
                description="Correlation pattern from mining",
            ),
            ProvenanceStep(
                node_id=hypotheses[0].hypothesis_id,
                node_type="hypothesis",
                description=hypotheses[0].statement[:80],
            ),
        ]
        chain = provenance_tracker.build_chain(
            finding_id="finding-latency-diff",
            steps=provenance_steps,
        )
        assert provenance_tracker.verify_chain(chain)
        assert capture.count("validation.provenance.built") == 1

        # Generate validation report
        report = validator.validate_finding(
            finding_id="finding-latency-diff",
            tests=[t_test_result],
            provenance=chain,
        )
        assert report.conclusion.value == "confirmed"
        assert report.confidence == 1.0
        assert "finding-latency-diff" in report.summary
        assert capture.count("validation.report.generated") == 1

        # ---- 8. Verify event flow ----
        event_names = capture.names

        # Events from all pipeline stages must be present
        required_events = [
            "hardware.file.detected",
            "hardware.quality.checked",
            "session.chronicle.started",
            "session.recording.added",
            "session.chronicle.ended",
            "memory.tier_a.created",
            "memory.tier_a.updated",
            "memory.search.executed",
            "discovery.pattern.found",
            "discovery.mining.completed",
            "discovery.hypothesis.created",
            "validation.test.completed",
            "validation.provenance.built",
            "validation.report.generated",
        ]

        for evt_name in required_events:
            assert evt_name in event_names, (
                f"Missing event {evt_name!r}. Captured events: {sorted(set(event_names))}"
            )

        # Total event count should be substantial
        # (files + quality + session + memory + discovery + validation)
        assert len(capture.events) > 50, (
            f"Expected >50 total events, got {len(capture.events)}"
        )

    def test_mvp_pipeline_insufficient_data(self, tmp_path: Path) -> None:
        """Pipeline with too few data points returns empty mining result."""
        capture = EventCapture()
        event_registry.subscribe("*", capture)

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Only 2 files -- below min_sessions=10
        csv_files = _generate_csv_files(data_dir, count=2, seed=42)
        data_dicts = _parse_csv_to_dicts(csv_files)
        assert len(data_dicts) == 2

        miner = PatternMiner()
        config = MiningConfig(min_sessions=10)
        result = miner.mine(data_dicts, config=config)

        assert len(result.patterns) == 0
        assert result.data_summary["row_count"] == 2
        assert capture.count("discovery.mining.completed") == 1
        assert capture.count("discovery.pattern.found") == 0

    def test_mvp_pipeline_bad_quality_raises_alerts(self, tmp_path: Path) -> None:
        """Pipeline detects quality issues and raises sentinel alerts."""
        capture = EventCapture()
        event_registry.subscribe("*", capture)

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        quality_checker = QualityChecker()
        sentinel = Sentinel(rules=[
            AlertRule(
                name="empty_file",
                metric_name="file_non_empty",
                threshold=1.0,
                comparison="below",
                level=QualityLevel.WARNING,
            ),
            AlertRule(
                name="missing_file",
                metric_name="file_exists",
                threshold=1.0,
                comparison="below",
                level=QualityLevel.CRITICAL,
            ),
        ])

        # Create an empty file
        empty_path = data_dir / "empty.csv"
        empty_path.touch()
        empty_ref = FileReference(path=empty_path, size_bytes=0)
        metric_empty = quality_checker.check_file(empty_ref)
        assert metric_empty.level == QualityLevel.WARNING
        assert metric_empty.name == "file_non_empty"

        alerts_empty = sentinel.check_metric(metric_empty, session_id="bad-session")
        assert len(alerts_empty) == 1
        assert alerts_empty[0].level == QualityLevel.WARNING

        # Create a reference to a non-existent file
        missing_path = data_dir / "does_not_exist.csv"
        missing_ref = FileReference(path=missing_path, size_bytes=None)
        metric_missing = quality_checker.check_file(missing_ref)
        assert metric_missing.level == QualityLevel.CRITICAL
        assert metric_missing.name == "file_exists"

        alerts_missing = sentinel.check_metric(metric_missing, session_id="bad-session")
        assert len(alerts_missing) == 1
        assert alerts_missing[0].level == QualityLevel.CRITICAL

        # Verify sentinel tracked all alerts
        all_alerts = sentinel.get_alerts(session_id="bad-session")
        assert len(all_alerts) == 2

        # Verify events
        assert capture.count("hardware.quality.checked") == 2
        assert capture.count("sentinel.alert.raised") == 2

        # Session quality summary should be CRITICAL
        summary = sentinel.check_session(
            session_id="bad-session",
            metrics=[metric_empty, metric_missing],
        )
        assert summary.overall_level == QualityLevel.CRITICAL
        assert len(summary.alerts) >= 2
        assert capture.count("sentinel.check.completed") == 1
