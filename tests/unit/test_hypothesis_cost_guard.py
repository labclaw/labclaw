"""TDD unit tests for LLMHypothesisGenerator cost guard (max_calls).

Covers:
- max_calls=0 → always use template fallback
- max_calls=2 → 2 LLM calls, rest template fallback
- default max_calls=50
- _call_count resets on new instance
- cost guard log message (via caplog)
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from labclaw.discovery.hypothesis import (
    HypothesisInput,
    LLMHypothesisGenerator,
    _LLMHypothesisItem,
    _LLMHypothesisResponse,
)
from labclaw.discovery.mining import PatternRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_provider(llm_statement: str = "LLM hypothesis") -> MagicMock:
    llm = MagicMock()
    llm.complete_structured = AsyncMock(
        return_value=_LLMHypothesisResponse(
            hypotheses=[
                _LLMHypothesisItem(
                    statement=llm_statement,
                    testable=True,
                    confidence=0.8,
                    required_experiments=["exp A"],
                    resource_estimate="1 session",
                )
            ]
        )
    )
    return llm


def _make_pattern(pattern_type: str = "correlation") -> PatternRecord:
    return PatternRecord(
        pattern_type=pattern_type,
        description="Synthetic pattern for cost guard tests",
        evidence={"col_a": "speed", "col_b": "distance", "r": 0.9, "p_value": 0.001},
        confidence=0.85,
    )


def _make_input(pattern_type: str = "correlation") -> HypothesisInput:
    return HypothesisInput(patterns=[_make_pattern(pattern_type)])


# ---------------------------------------------------------------------------
# max_calls=0 → always template fallback
# ---------------------------------------------------------------------------


def test_max_calls_zero_always_uses_template() -> None:
    """max_calls=0: every call immediately uses the template fallback."""
    llm = _make_llm_provider()
    gen = LLMHypothesisGenerator(llm=llm, max_calls=0)

    for _ in range(3):
        results = gen.generate(_make_input())
        # Template for correlation always returns exactly 1 hypothesis
        assert len(results) == 1
        # The LLM must never be called
    llm.complete_structured.assert_not_called()


def test_max_calls_zero_call_count_stays_zero() -> None:
    """max_calls=0: _call_count never increments because guard triggers first."""
    llm = _make_llm_provider()
    gen = LLMHypothesisGenerator(llm=llm, max_calls=0)
    gen.generate(_make_input())
    assert gen._call_count == 0


# ---------------------------------------------------------------------------
# max_calls=2 → 2 LLM calls, remaining use template fallback
# ---------------------------------------------------------------------------


def test_max_calls_two_llm_calls_then_template() -> None:
    """max_calls=2: first 2 calls use LLM, calls 3+ use template fallback."""
    llm = _make_llm_provider("LLM hypothesis")
    gen = LLMHypothesisGenerator(llm=llm, max_calls=2)

    # Call 1 — LLM
    r1 = gen.generate(_make_input())
    assert len(r1) == 1
    assert r1[0].statement == "LLM hypothesis"

    # Call 2 — LLM
    r2 = gen.generate(_make_input())
    assert len(r2) == 1
    assert r2[0].statement == "LLM hypothesis"

    assert llm.complete_structured.call_count == 2

    # Call 3 — template fallback (statement differs from LLM stub)
    r3 = gen.generate(_make_input())
    assert len(r3) == 1
    assert r3[0].statement != "LLM hypothesis"

    # LLM call count must not have increased
    assert llm.complete_structured.call_count == 2

    # Call 4 — still template fallback
    r4 = gen.generate(_make_input())
    assert len(r4) == 1
    assert r4[0].statement != "LLM hypothesis"
    assert llm.complete_structured.call_count == 2


def test_max_calls_two_increments_call_count() -> None:
    """_call_count reaches max_calls after the allowed number of LLM calls."""
    llm = _make_llm_provider()
    gen = LLMHypothesisGenerator(llm=llm, max_calls=2)

    gen.generate(_make_input())
    assert gen._call_count == 1

    gen.generate(_make_input())
    assert gen._call_count == 2

    # Beyond limit — counter does NOT increment further
    gen.generate(_make_input())
    assert gen._call_count == 2


# ---------------------------------------------------------------------------
# default max_calls = 50
# ---------------------------------------------------------------------------


def test_default_max_calls_is_50() -> None:
    """Default max_calls must be 50."""
    llm = _make_llm_provider()
    gen = LLMHypothesisGenerator(llm=llm)
    assert gen._max_calls == 50


# ---------------------------------------------------------------------------
# _call_count resets on new instance
# ---------------------------------------------------------------------------


def test_call_count_resets_on_new_instance() -> None:
    """Each new LLMHypothesisGenerator starts with _call_count=0."""
    llm = _make_llm_provider()
    gen1 = LLMHypothesisGenerator(llm=llm, max_calls=1)
    gen1.generate(_make_input())  # _call_count = 1
    assert gen1._call_count == 1

    gen2 = LLMHypothesisGenerator(llm=llm, max_calls=1)
    assert gen2._call_count == 0


# ---------------------------------------------------------------------------
# Cost guard logging
# ---------------------------------------------------------------------------


def test_cost_guard_logs_info_when_triggered(caplog: pytest.LogCaptureFixture) -> None:
    """When guard activates, an INFO log including 'cost guard' is emitted."""
    llm = _make_llm_provider()
    gen = LLMHypothesisGenerator(llm=llm, max_calls=0)

    with caplog.at_level(logging.INFO, logger="labclaw.discovery.hypothesis"):
        gen.generate(_make_input())

    guard_messages = [r for r in caplog.records if "cost guard" in r.message.lower()]
    assert guard_messages, (
        f"Expected a 'cost guard' log message, got: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# HypothesizeStep passes max_llm_calls through to LLMHypothesisGenerator
# ---------------------------------------------------------------------------


def test_hypothesize_step_passes_max_llm_calls() -> None:
    """HypothesizeStep stores max_llm_calls and passes it when creating LLMHypothesisGenerator."""
    from labclaw.orchestrator.steps import HypothesizeStep

    step = HypothesizeStep(llm_provider=None, max_llm_calls=5)
    assert step._max_llm_calls == 5


def test_hypothesize_step_default_max_llm_calls() -> None:
    """HypothesizeStep default max_llm_calls is 50."""
    from labclaw.orchestrator.steps import HypothesizeStep

    step = HypothesizeStep(llm_provider=None)
    assert step._max_llm_calls == 50
