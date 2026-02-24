"""Tests for EvolutionEngine.propose_candidates_llm and remaining uncovered branches.

Targets:
- evolution/engine.py lines 138, 234-235, 239, 344-382, 424
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from labclaw.core.schemas import EvolutionStage, EvolutionTarget
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.schemas import EvolutionCandidate, FitnessScore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate(target: EvolutionTarget = EvolutionTarget.ANALYSIS_PARAMS) -> EvolutionCandidate:
    return EvolutionCandidate(target=target, description="test candidate", proposed_by="test")


def _baseline(target: EvolutionTarget = EvolutionTarget.ANALYSIS_PARAMS) -> FitnessScore:
    return FitnessScore(target=target, metrics={"accuracy": 0.9})


def _fitness(metrics: dict | None = None) -> FitnessScore:
    return FitnessScore(
        target=EvolutionTarget.ANALYSIS_PARAMS, metrics=metrics or {"accuracy": 0.95}
    )


# ---------------------------------------------------------------------------
# propose_candidates — empty-templates branch (line 138)
# ---------------------------------------------------------------------------


class TestProposeCandidatesEmptyTarget:
    def test_propose_candidates_unknown_target_returns_empty(self) -> None:
        """When _PROPOSAL_TEMPLATES has no entry for a target, returns []."""
        from labclaw.evolution import engine as eng_module

        original = eng_module._PROPOSAL_TEMPLATES.copy()
        # Temporarily remove all templates for ANALYSIS_PARAMS
        eng_module._PROPOSAL_TEMPLATES.clear()

        try:
            e = EvolutionEngine()
            result = e.propose_candidates(EvolutionTarget.ANALYSIS_PARAMS, n=3)
            assert result == []
        finally:
            eng_module._PROPOSAL_TEMPLATES.update(original)


# ---------------------------------------------------------------------------
# advance_stage — ValueError from unadvanceable stage (lines 234-235, 239)
# ---------------------------------------------------------------------------


class TestAdvanceStageEdgeCases:
    def test_advance_from_unadvanceable_stage_raises(self) -> None:
        """A stage not in _STAGE_ORDER triggers the inner ValueError (lines 234-235)."""
        from labclaw.evolution import engine as eng_module

        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        # Patch _STAGE_ORDER so current stage is absent
        original_order = eng_module._STAGE_ORDER[:]
        eng_module._STAGE_ORDER.clear()

        try:
            with pytest.raises(ValueError, match="unadvanceable stage"):
                engine.advance_stage(cycle.cycle_id, _fitness())
        finally:
            eng_module._STAGE_ORDER[:] = original_order

    def test_advance_from_final_stage_raises(self) -> None:
        """If already at last stage in _STAGE_ORDER, raises ValueError (line 239)."""
        from labclaw.evolution import engine as eng_module

        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        # Force cycle to the last stage in _STAGE_ORDER (PROMOTED) manually,
        # bypassing the promoted-check by using _STAGE_ORDER[-1] directly but not
        # setting cycle.promoted/completed. We need a stage that IS in _STAGE_ORDER
        # and is at the last position but NOT caught by the "already promoted" guard.
        # The guard checks cycle.stage == PROMOTED; so we need a stage that is last in
        # _STAGE_ORDER but is not PROMOTED in the guard sense.
        # Easiest: temporarily append a new fake stage at the end and set cycle to it.
        engine._cycles[cycle.cycle_id].stage = eng_module._STAGE_ORDER[-1]
        # Now remove the PROMOTED guard by patching — actually the guard fires first.
        # Instead: just use CANARY (index 2, not last) and put CANARY at end temporarily.
        # Restore and use a cleaner approach: set cycle stage to CANARY, then shrink
        # _STAGE_ORDER so CANARY is the last element.
        engine._cycles[cycle.cycle_id].stage = EvolutionStage.CANARY
        original_order = eng_module._STAGE_ORDER[:]
        # Keep only up to and including CANARY (index 2)
        eng_module._STAGE_ORDER[:] = original_order[:3]  # [BACKTEST, SHADOW, CANARY]

        try:
            with pytest.raises(ValueError, match="already at the final stage"):
                engine.advance_stage(cycle.cycle_id, _fitness())
        finally:
            eng_module._STAGE_ORDER[:] = original_order


# ---------------------------------------------------------------------------
# propose_candidates_llm (lines 344-382)
# ---------------------------------------------------------------------------


class TestProposeCandidatesLLM:
    @pytest.mark.asyncio
    async def test_llm_returns_list(self) -> None:
        """LLM returns a valid JSON list → candidates with proposed_by='llm'."""
        engine = EvolutionEngine()
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(
            return_value='[{"description": "test", "config_diff": {"x": 1}}]'
        )

        candidates = await engine.propose_candidates_llm(
            EvolutionTarget.ANALYSIS_PARAMS,
            context="test context",
            llm_provider=mock_llm,
            n=1,
        )

        assert len(candidates) == 1
        assert candidates[0].proposed_by == "llm"
        assert candidates[0].description == "test"
        assert candidates[0].config_diff == {"x": 1}

    @pytest.mark.asyncio
    async def test_llm_returns_dict_wrapped_in_list(self) -> None:
        """LLM returns a JSON object (not list) → wrapped in list."""
        engine = EvolutionEngine()
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(
            return_value='{"description": "single", "config_diff": {"y": 2}}'
        )

        candidates = await engine.propose_candidates_llm(
            EvolutionTarget.PROMPTS,
            context="ctx",
            llm_provider=mock_llm,
            n=1,
        )

        assert len(candidates) == 1
        assert candidates[0].proposed_by == "llm"
        assert candidates[0].description == "single"

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_templates(self) -> None:
        """LLM raises → falls back to template-based proposals."""
        engine = EvolutionEngine()
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM error"))

        candidates = await engine.propose_candidates_llm(
            EvolutionTarget.ANALYSIS_PARAMS,
            context="ctx",
            llm_provider=mock_llm,
            n=2,
        )

        # Template fallback must return candidates
        assert len(candidates) >= 1
        for c in candidates:
            assert c.proposed_by == "system"

    @pytest.mark.asyncio
    async def test_llm_with_fitness_history_in_prompt(self) -> None:
        """History is included in the prompt when fitness records exist."""
        engine = EvolutionEngine()
        # Record some fitness history
        engine.measure_fitness(
            EvolutionTarget.ANALYSIS_PARAMS,
            {"accuracy": 0.88},
            data_points=10,
        )

        captured_prompts: list[str] = []

        async def capture_prompt(prompt: str) -> str:
            captured_prompts.append(prompt)
            return '[{"description": "from history", "config_diff": {"z": 3}}]'

        mock_llm = MagicMock()
        mock_llm.complete = capture_prompt

        candidates = await engine.propose_candidates_llm(
            EvolutionTarget.ANALYSIS_PARAMS,
            context="history test",
            llm_provider=mock_llm,
            n=1,
        )

        assert len(candidates) == 1
        assert candidates[0].description == "from history"
        # Verify the prompt contained history
        assert len(captured_prompts) == 1
        assert "accuracy" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_llm_empty_candidates_fallback_to_templates(self) -> None:
        """LLM returns an empty list → fallback to template-based proposals."""
        engine = EvolutionEngine()
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="[]")

        candidates = await engine.propose_candidates_llm(
            EvolutionTarget.ANALYSIS_PARAMS,
            context="ctx",
            llm_provider=mock_llm,
            n=3,
        )

        # Empty LLM list → fallback
        assert len(candidates) >= 1
        for c in candidates:
            assert c.proposed_by == "system"

    @pytest.mark.asyncio
    async def test_llm_missing_description_uses_default(self) -> None:
        """LLM response with missing 'description' uses default description."""
        engine = EvolutionEngine()
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value='[{"config_diff": {"a": 1}}]')

        candidates = await engine.propose_candidates_llm(
            EvolutionTarget.PROMPTS,
            context="ctx",
            llm_provider=mock_llm,
            n=1,
        )

        assert len(candidates) == 1
        assert "prompts" in candidates[0].description.lower()


# ---------------------------------------------------------------------------
# get_cycle unknown ID (line 424)
# ---------------------------------------------------------------------------


class TestGetCyclePublic:
    def test_get_cycle_unknown_id_raises_key_error(self) -> None:
        engine = EvolutionEngine()
        with pytest.raises(KeyError, match="nonexistent"):
            engine.get_cycle("nonexistent")

    def test_get_cycle_known_id_returns_cycle(self) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        fetched = engine.get_cycle(cycle.cycle_id)
        assert fetched.cycle_id == cycle.cycle_id
