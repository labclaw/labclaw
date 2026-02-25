"""Discovery endpoints — pattern mining and hypothesis generation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from labclaw.api.deps import get_hypothesis_generator, get_pattern_miner
from labclaw.discovery.hypothesis import HypothesisGenerator, HypothesisInput, HypothesisOutput
from labclaw.discovery.mining import MiningConfig, MiningResult, PatternMiner, PatternRecord

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class MineRequest(BaseModel):
    data: list[dict[str, Any]]
    config: MiningConfig | None = None


class HypothesizeRequest(BaseModel):
    patterns: list[PatternRecord]
    context: str = ""
    constraints: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/mine")
def mine_patterns(
    body: MineRequest,
    miner: PatternMiner = Depends(get_pattern_miner),
) -> MiningResult:
    return miner.mine(body.data, config=body.config)


@router.post("/hypothesize")
def generate_hypotheses(
    body: HypothesizeRequest,
    generator: HypothesisGenerator = Depends(get_hypothesis_generator),
) -> list[HypothesisOutput]:
    inp = HypothesisInput(
        patterns=body.patterns,
        context=body.context,
        constraints=body.constraints,
    )
    return generator.generate(inp)
