"""Tests for labclaw.core.evaluation — offline replay, shadow mode, benchmarking."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from labclaw.core.evaluation import BenchmarkResult, EvaluationHarness
from labclaw.core.events import event_registry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_data(n: int = 20) -> list[dict[str, Any]]:
    return [
        {"x": float(i), "y": float(i * 2), "label": f"s{i}"}
        for i in range(n)
    ]


def _mock_mining_result(n_patterns: int = 2):
    mock = MagicMock()
    mock.patterns = [MagicMock() for _ in range(n_patterns)]
    return mock


# ---------------------------------------------------------------------------
# offline_replay
# ---------------------------------------------------------------------------


class TestOfflineReplay:
    def test_valid_data(self):
        mock_result = _mock_mining_result(3)
        with patch(
            "labclaw.discovery.mining.PatternMiner"
        ) as mock_miner_cls, patch(
            "labclaw.discovery.mining.MiningConfig"
        ):
            mock_miner_cls.return_value.mine.return_value = mock_result
            harness = EvaluationHarness()
            metrics = harness.offline_replay(_sample_data(20), {})
            assert metrics["pattern_count"] == 3.0
            assert metrics["data_rows"] == 20.0
            assert "replay_duration" in metrics
            assert "coverage" in metrics

    def test_empty_data(self):
        mock_result = _mock_mining_result(0)
        with patch(
            "labclaw.discovery.mining.PatternMiner"
        ) as mock_miner_cls, patch(
            "labclaw.discovery.mining.MiningConfig"
        ):
            mock_miner_cls.return_value.mine.return_value = mock_result
            harness = EvaluationHarness()
            metrics = harness.offline_replay([], {})
            assert metrics["pattern_count"] == 0.0
            assert metrics["data_rows"] == 0.0
            assert metrics["coverage"] == 0.0

    def test_invalid_config_falls_back(self):
        """Invalid config kwargs should cause MiningConfig(**config) to fail,
        falling back to default MiningConfig()."""
        mock_result = _mock_mining_result(1)
        with patch(
            "labclaw.discovery.mining.PatternMiner"
        ) as mock_miner_cls, patch(
            "labclaw.discovery.mining.MiningConfig"
        ) as mock_config_cls:
            # First call (with bad config) raises, second call (defaults) works
            mock_config_cls.side_effect = [TypeError("bad"), MagicMock()]
            mock_miner_cls.return_value.mine.return_value = mock_result
            harness = EvaluationHarness()
            metrics = harness.offline_replay(_sample_data(10), {"bad_param": True})
            assert "pattern_count" in metrics


# ---------------------------------------------------------------------------
# shadow_run
# ---------------------------------------------------------------------------


class TestShadowRun:
    def test_compares_two_configs(self):
        mock_result = _mock_mining_result(2)
        with patch(
            "labclaw.discovery.mining.PatternMiner"
        ) as mock_miner_cls, patch(
            "labclaw.discovery.mining.MiningConfig"
        ):
            mock_miner_cls.return_value.mine.return_value = mock_result
            harness = EvaluationHarness()
            prod, cand = harness.shadow_run(
                production_config={},
                candidate_config={},
                data=_sample_data(15),
            )
            assert "pattern_count" in prod
            assert "pattern_count" in cand
            # offline_replay called twice (once per config) but each call
            # creates its own PatternMiner, so mine is called once per instance.
            # With mock, all instances share the same mock.
            assert mock_miner_cls.return_value.mine.call_count >= 2


# ---------------------------------------------------------------------------
# benchmark
# ---------------------------------------------------------------------------


class TestBenchmark:
    def test_returns_benchmark_result(self):
        mock_result = _mock_mining_result(1)
        with patch(
            "labclaw.discovery.mining.PatternMiner"
        ) as mock_miner_cls, patch(
            "labclaw.discovery.mining.MiningConfig"
        ):
            mock_miner_cls.return_value.mine.return_value = mock_result
            harness = EvaluationHarness()
            result = harness.benchmark(
                dataset=_sample_data(10),
                dataset_name="test_set",
                config={"min_sessions": 5},
            )
            assert isinstance(result, BenchmarkResult)
            assert result.dataset == "test_set"
            assert result.patterns_found == 1
            assert result.duration_seconds >= 0
            assert result.timestamp  # non-empty ISO string
            assert "pattern_count" in result.fitness_metrics

    def test_benchmark_no_config(self):
        mock_result = _mock_mining_result(0)
        with patch(
            "labclaw.discovery.mining.PatternMiner"
        ) as mock_miner_cls, patch(
            "labclaw.discovery.mining.MiningConfig"
        ):
            mock_miner_cls.return_value.mine.return_value = mock_result
            harness = EvaluationHarness()
            result = harness.benchmark(dataset=[], dataset_name="empty")
            assert result.config_used == {}
            assert result.patterns_found == 0


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class TestEvaluationEvents:
    def test_replay_events(self):
        events: list[str] = []

        def handler(event):
            events.append(str(event.event_name))

        event_registry.subscribe("evolution.eval.replay_started", handler)
        event_registry.subscribe("evolution.eval.replay_completed", handler)
        try:
            mock_result = _mock_mining_result(0)
            with patch(
                "labclaw.discovery.mining.PatternMiner"
            ) as mock_miner_cls, patch(
                "labclaw.discovery.mining.MiningConfig"
            ):
                mock_miner_cls.return_value.mine.return_value = mock_result
                harness = EvaluationHarness()
                harness.offline_replay([], {})
            assert "evolution.eval.replay_started" in events
            assert "evolution.eval.replay_completed" in events
        finally:
            event_registry._handlers.pop("evolution.eval.replay_started", None)
            event_registry._handlers.pop("evolution.eval.replay_completed", None)

    def test_shadow_events(self):
        events: list[str] = []

        def handler(event):
            events.append(str(event.event_name))

        event_registry.subscribe("evolution.eval.shadow_started", handler)
        event_registry.subscribe("evolution.eval.shadow_completed", handler)
        try:
            mock_result = _mock_mining_result(0)
            with patch(
                "labclaw.discovery.mining.PatternMiner"
            ) as mock_miner_cls, patch(
                "labclaw.discovery.mining.MiningConfig"
            ):
                mock_miner_cls.return_value.mine.return_value = mock_result
                harness = EvaluationHarness()
                harness.shadow_run({}, {}, [])
            assert "evolution.eval.shadow_started" in events
            assert "evolution.eval.shadow_completed" in events
        finally:
            event_registry._handlers.pop("evolution.eval.shadow_started", None)
            event_registry._handlers.pop("evolution.eval.shadow_completed", None)
