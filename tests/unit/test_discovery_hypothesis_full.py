"""Full-coverage tests for labclaw.discovery.hypothesis.

Targets uncovered lines:
  - Line 41: _now() helper
  - Lines 272-277: LLMHypothesisGenerator.generate() inside a running event loop
    (concurrent.futures / ThreadPoolExecutor path)
  - Lines 308-333: LLM response → HypothesisOutput conversion + event emission
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from labclaw.discovery.hypothesis import (
    HypothesisGenerator,
    HypothesisInput,
    HypothesisOutput,
    LLMHypothesisGenerator,
    _LLMHypothesisItem,
    _LLMHypothesisResponse,
    _now,
)
from labclaw.discovery.mining import PatternRecord

# ---------------------------------------------------------------------------
# _now() helper (line 41)
# ---------------------------------------------------------------------------


def test_now_returns_utc_datetime() -> None:
    dt = _now()
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_pattern(
    pattern_type: str = "correlation",
    confidence: float = 0.8,
) -> PatternRecord:
    return PatternRecord(
        pattern_type=pattern_type,
        description="Synthetic test pattern",
        evidence={"col_a": "x", "col_b": "y", "r": 0.9, "p_value": 0.01},
        confidence=confidence,
    )


def _make_llm_response(*items: _LLMHypothesisItem) -> _LLMHypothesisResponse:
    return _LLMHypothesisResponse(hypotheses=list(items))


def _make_llm_item(
    statement: str = "Test hypothesis",
    confidence: float = 0.75,
) -> _LLMHypothesisItem:
    return _LLMHypothesisItem(
        statement=statement,
        testable=True,
        confidence=confidence,
        required_experiments=["Do experiment A"],
        resource_estimate="1 session",
    )


def _make_llm_provider(
    response: _LLMHypothesisResponse | None = None, raise_error: bool = False
) -> MagicMock:
    llm = MagicMock()
    if raise_error:
        llm.complete_structured = AsyncMock(side_effect=RuntimeError("API down"))
    else:
        llm.complete_structured = AsyncMock(return_value=response or _make_llm_response())
    llm.model_name = "mock-llm"
    return llm


# ---------------------------------------------------------------------------
# LLMHypothesisGenerator — __init__ (lines 272-277)
# ---------------------------------------------------------------------------


def test_llm_generator_init() -> None:
    """LLMHypothesisGenerator stores llm and creates a fallback generator."""
    llm = _make_llm_provider()
    gen = LLMHypothesisGenerator(llm=llm)
    assert gen._llm is llm
    assert isinstance(gen._fallback, HypothesisGenerator)


# ---------------------------------------------------------------------------
# LLM generation path — successful response (lines 308-333)
# ---------------------------------------------------------------------------


def test_generate_llm_success_returns_hypotheses() -> None:
    """Successful LLM call converts items to HypothesisOutput and emits events."""
    item1 = _make_llm_item("H1: speed affects accuracy", confidence=0.9)
    item2 = _make_llm_item("H2: drift in fluorescence", confidence=0.6)
    response = _make_llm_response(item1, item2)

    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern("correlation", confidence=0.85)
    inp = HypothesisInput(patterns=[pattern])
    results = gen.generate(inp)

    assert len(results) == 2
    # Sorted descending by confidence
    assert results[0].confidence >= results[1].confidence
    assert results[0].statement == "H1: speed affects accuracy"
    assert results[1].statement == "H2: drift in fluorescence"


def test_generate_llm_sets_patterns_used() -> None:
    """patterns_used contains all input pattern IDs."""
    item = _make_llm_item("H: test", confidence=0.5)
    response = _make_llm_response(item)

    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    p1 = _make_pattern("correlation")
    p2 = _make_pattern("anomaly")
    inp = HypothesisInput(patterns=[p1, p2])
    results = gen.generate(inp)

    assert len(results) == 1
    assert p1.pattern_id in results[0].patterns_used
    assert p2.pattern_id in results[0].patterns_used


def test_generate_llm_clamps_confidence() -> None:
    """Confidence values outside [0, 1] are clamped."""
    item_over = _make_llm_item("H: over", confidence=1.5)
    item_under = _make_llm_item("H: under", confidence=-0.3)
    response = _make_llm_response(item_over, item_under)

    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern()
    inp = HypothesisInput(patterns=[pattern])
    results = gen.generate(inp)

    for h in results:
        assert 0.0 <= h.confidence <= 1.0


def test_generate_llm_empty_hypothesis_list() -> None:
    """LLM returns empty hypotheses list → output is empty."""
    response = _make_llm_response()  # no items

    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern()
    inp = HypothesisInput(patterns=[pattern])
    results = gen.generate(inp)

    assert results == []


def test_generate_llm_output_conforms_to_schema() -> None:
    """Each HypothesisOutput has expected fields populated."""
    item = _make_llm_item("H: testing schema", confidence=0.7)
    response = _make_llm_response(item)

    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern()
    inp = HypothesisInput(patterns=[pattern])
    results = gen.generate(inp)

    assert len(results) == 1
    h = results[0]
    assert isinstance(h, HypothesisOutput)
    assert h.statement == "H: testing schema"
    assert h.testable is True
    assert h.resource_estimate == "1 session"
    assert h.required_experiments == ["Do experiment A"]
    assert isinstance(h.hypothesis_id, str) and len(h.hypothesis_id) > 0


def test_generate_llm_discards_empty_statement() -> None:
    item = _make_llm_item(statement="   ", confidence=0.7)
    response = _make_llm_response(item)
    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern()
    results = gen.generate(HypothesisInput(patterns=[pattern]))
    assert results == []


def test_generate_llm_discards_overly_long_statement() -> None:
    item = _make_llm_item(statement="x" * 1001, confidence=0.7)
    response = _make_llm_response(item)
    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern()
    results = gen.generate(HypothesisInput(patterns=[pattern]))
    assert results == []


def test_generate_llm_discards_missing_experiments() -> None:
    item = _LLMHypothesisItem(
        statement="Valid statement",
        testable=True,
        confidence=0.5,
        required_experiments=[],
        resource_estimate="test",
    )
    response = _make_llm_response(item)
    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern()
    results = gen.generate(HypothesisInput(patterns=[pattern]))
    assert results == []


# ---------------------------------------------------------------------------
# LLM generation path — inside running event loop (lines 272-277)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_inside_running_loop_uses_thread() -> None:
    """When called from inside a running asyncio loop, ThreadPoolExecutor is used."""
    item = _make_llm_item("H: inside loop", confidence=0.8)
    response = _make_llm_response(item)

    llm = _make_llm_provider(response)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern()
    inp = HypothesisInput(patterns=[pattern])

    # We are already inside an async context here (pytest-asyncio)
    # gen.generate() will detect the running loop and use ThreadPoolExecutor
    loop = asyncio.get_running_loop()
    assert loop.is_running()

    results = gen.generate(inp)
    assert len(results) == 1
    assert results[0].statement == "H: inside loop"


@pytest.mark.asyncio
async def test_generate_inside_running_loop_fallback_on_error() -> None:
    """Inside running loop: LLM error still triggers fallback."""
    llm = _make_llm_provider(raise_error=True)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern("temporal", confidence=0.5)
    inp = HypothesisInput(patterns=[pattern])

    results = gen.generate(inp)
    # Fallback template generates at least one hypothesis
    assert len(results) >= 1
    assert all(isinstance(h.statement, str) for h in results)


# ---------------------------------------------------------------------------
# LLM fallback — outside event loop (existing behaviour, re-tested for clarity)
# ---------------------------------------------------------------------------


def test_generate_llm_fallback_outside_loop() -> None:
    """Outside any event loop, asyncio.run is called directly."""
    llm = _make_llm_provider(raise_error=True)
    gen = LLMHypothesisGenerator(llm=llm)

    pattern = _make_pattern("anomaly", confidence=0.7)
    inp = HypothesisInput(patterns=[pattern])
    results = gen.generate(inp)

    assert len(results) >= 1
    for h in results:
        assert isinstance(h, HypothesisOutput)


def test_generate_llm_no_patterns_empty_result() -> None:
    """No patterns → _generate_llm returns [] immediately (line 285-286)."""
    llm = _make_llm_provider()
    gen = LLMHypothesisGenerator(llm=llm)

    inp = HypothesisInput(patterns=[])
    results = gen.generate(inp)
    assert results == []
    # LLM should not have been called
    llm.complete_structured.assert_not_called()


# ---------------------------------------------------------------------------
# _LLMHypothesisResponse schema
# ---------------------------------------------------------------------------


def test_llm_hypothesis_response_schema() -> None:
    item = _LLMHypothesisItem(
        statement="A hypothesis",
        testable=False,
        confidence=0.4,
        required_experiments=["exp1"],
        resource_estimate="2 weeks",
    )
    resp = _LLMHypothesisResponse(hypotheses=[item])
    assert len(resp.hypotheses) == 1
    assert resp.hypotheses[0].testable is False


# ---------------------------------------------------------------------------
# _build_prompt tests (lines 341, 355-358)
# ---------------------------------------------------------------------------


def test_build_prompt_includes_context(monkeypatch: object) -> None:
    """Context string adds 'Domain context:' line (line 341)."""
    pattern = _make_pattern()
    inp = HypothesisInput(patterns=[pattern], context="Mouse locomotion")
    prompt = LLMHypothesisGenerator._build_prompt(inp)
    assert "Domain context: Mouse locomotion" in prompt
    assert "Pattern 1" in prompt


def test_build_prompt_no_context_skips_domain_line() -> None:
    """Empty context → no 'Domain context' line (line 341 NOT executed)."""
    pattern = _make_pattern()
    inp = HypothesisInput(patterns=[pattern], context="")
    prompt = LLMHypothesisGenerator._build_prompt(inp)
    assert "Domain context" not in prompt


def test_build_prompt_with_constraints_adds_constraint_lines() -> None:
    """Non-empty constraints → 'Constraints:' + items + blank line (lines 355-358)."""
    pattern = _make_pattern()
    inp = HypothesisInput(
        patterns=[pattern],
        constraints=["No surgery", "Max 3 sessions"],
    )
    prompt = LLMHypothesisGenerator._build_prompt(inp)
    assert "Constraints:" in prompt
    assert "  - No surgery" in prompt
    assert "  - Max 3 sessions" in prompt


def test_build_prompt_empty_constraints_no_constraint_block() -> None:
    """Empty constraints list → 'Constraints:' section not added."""
    pattern = _make_pattern()
    inp = HypothesisInput(patterns=[pattern], constraints=[])
    prompt = LLMHypothesisGenerator._build_prompt(inp)
    assert "Constraints:" not in prompt


def test_build_prompt_ends_with_instruction() -> None:
    """Prompt always ends with the 'Generate testable hypotheses' instruction."""
    pattern = _make_pattern()
    inp = HypothesisInput(patterns=[pattern])
    prompt = LLMHypothesisGenerator._build_prompt(inp)
    assert "Generate testable hypotheses" in prompt


def test_build_prompt_multiple_patterns_numbered() -> None:
    """Multiple patterns produce 'Pattern 1:', 'Pattern 2:', etc."""
    p1 = _make_pattern("correlation")
    p2 = _make_pattern("anomaly")
    inp = HypothesisInput(patterns=[p1, p2])
    prompt = LLMHypothesisGenerator._build_prompt(inp)
    assert "Pattern 1:" in prompt
    assert "Pattern 2:" in prompt
    assert "Number of patterns discovered: 2" in prompt
