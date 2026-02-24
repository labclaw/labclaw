"""Tests for LLMHypothesisGenerator — prompt building and error fallback.

Covers:
- src/labclaw/discovery/hypothesis.py  (LLMHypothesisGenerator)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from labclaw.discovery.hypothesis import HypothesisInput, LLMHypothesisGenerator
from labclaw.discovery.mining import PatternRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pattern(pattern_type: str = "correlation", confidence: float = 0.8) -> PatternRecord:
    return PatternRecord(
        pattern_type=pattern_type,
        description="Test pattern",
        evidence={"col_a": "x", "col_b": "y", "r": 0.9, "p_value": 0.01},
        confidence=confidence,
    )


def _make_llm(raise_on_complete: bool = False) -> MagicMock:
    """Return a mock LLMProvider."""
    llm = MagicMock()
    if raise_on_complete:
        llm.complete_structured = AsyncMock(side_effect=RuntimeError("API error"))
    else:
        llm.complete_structured = AsyncMock(return_value=MagicMock(hypotheses=[]))
    llm.model_name = "mock-model"
    return llm


# ---------------------------------------------------------------------------
# _build_prompt tests
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_build_prompt_with_context(self) -> None:
        pattern = _make_pattern()
        inp = HypothesisInput(patterns=[pattern], context="Mouse locomotion study")
        prompt = LLMHypothesisGenerator._build_prompt(inp)
        assert "Domain context" in prompt
        assert "Mouse locomotion study" in prompt
        assert "Pattern 1" in prompt

    def test_build_prompt_with_constraints(self) -> None:
        pattern = _make_pattern()
        inp = HypothesisInput(
            patterns=[pattern],
            constraints=["Max 2 sessions", "No invasive procedures"],
        )
        prompt = LLMHypothesisGenerator._build_prompt(inp)
        assert "Constraints:" in prompt
        assert "Max 2 sessions" in prompt
        assert "No invasive procedures" in prompt

    def test_build_prompt_no_context(self) -> None:
        pattern = _make_pattern()
        inp = HypothesisInput(patterns=[pattern])
        prompt = LLMHypothesisGenerator._build_prompt(inp)
        assert "Domain context" not in prompt

    def test_build_prompt_multiple_patterns(self) -> None:
        patterns = [_make_pattern("correlation"), _make_pattern("anomaly")]
        inp = HypothesisInput(patterns=patterns)
        prompt = LLMHypothesisGenerator._build_prompt(inp)
        assert "Pattern 1" in prompt
        assert "Pattern 2" in prompt
        assert "Number of patterns discovered: 2" in prompt

    def test_build_prompt_pattern_fields_present(self) -> None:
        pattern = _make_pattern("temporal", confidence=0.75)
        inp = HypothesisInput(patterns=[pattern])
        prompt = LLMHypothesisGenerator._build_prompt(inp)
        assert "temporal" in prompt
        assert "0.750" in prompt
        assert "Test pattern" in prompt

    def test_build_prompt_empty_constraints_not_shown(self) -> None:
        pattern = _make_pattern()
        inp = HypothesisInput(patterns=[pattern], constraints=[])
        prompt = LLMHypothesisGenerator._build_prompt(inp)
        assert "Constraints:" not in prompt


# ---------------------------------------------------------------------------
# generate() fallback tests
# ---------------------------------------------------------------------------


class TestLLMHypothesisGeneratorFallback:
    def test_generate_falls_back_on_error(self) -> None:
        """When LLM raises, the generator falls back to template results."""
        llm = _make_llm(raise_on_complete=True)
        gen = LLMHypothesisGenerator(llm=llm)

        pattern = _make_pattern("correlation", confidence=0.9)
        inp = HypothesisInput(patterns=[pattern])
        results = gen.generate(inp)

        # Fallback template produces at least one hypothesis
        assert len(results) >= 1
        assert all(h.statement for h in results)

    def test_generate_empty_patterns_returns_empty(self) -> None:
        """No patterns → no LLM call, empty list returned."""
        llm = _make_llm(raise_on_complete=False)
        gen = LLMHypothesisGenerator(llm=llm)
        inp = HypothesisInput(patterns=[])
        results = gen.generate(inp)
        assert results == []

    def test_generate_fallback_produces_hypothesis_output_schema(self) -> None:
        """Fallback results conform to HypothesisOutput schema."""
        llm = _make_llm(raise_on_complete=True)
        gen = LLMHypothesisGenerator(llm=llm)
        pattern = _make_pattern("anomaly", confidence=0.6)
        inp = HypothesisInput(patterns=[pattern])
        results = gen.generate(inp)

        for h in results:
            assert isinstance(h.statement, str)
            assert isinstance(h.confidence, float)
            assert isinstance(h.required_experiments, list)
            assert isinstance(h.patterns_used, list)
