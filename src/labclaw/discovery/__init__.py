"""Discovery — pattern mining, hypothesis generation, predictive modeling.

Spec: docs/specs/L3-discovery.md
Design doc: section 5.3 (Discovery Loop)

Maps to the ASK -> HYPOTHESIZE -> PREDICT steps of the scientific method:
  mining.py       — ASK: what patterns exist in the data?
  unsupervised.py — ASK: what hidden structure exists?
  hypothesis.py   — HYPOTHESIZE: template-based (MVP) / LLM + stats (future)
  modeling.py     — PREDICT: predictive models + uncertainty quantification
"""

from __future__ import annotations

from labclaw.discovery.hypothesis import (
    HypothesisGenerator,
    HypothesisInput,
    HypothesisOutput,
    LLMHypothesisGenerator,
)
from labclaw.discovery.mining import (
    MiningConfig,
    MiningResult,
    PatternMiner,
    PatternRecord,
)
from labclaw.discovery.modeling import (
    ModelConfig,
    ModelTrainResult,
    PredictiveModel,
    UncertaintyEstimate,
)
from labclaw.discovery.unsupervised import (
    ClusterConfig,
    ClusterDiscovery,
    ClusterResult,
    DimensionalityReducer,
    ReductionConfig,
    ReductionResult,
)

__all__ = [
    "ClusterConfig",
    "ClusterDiscovery",
    "ClusterResult",
    "DimensionalityReducer",
    "HypothesisGenerator",
    "HypothesisInput",
    "HypothesisOutput",
    "LLMHypothesisGenerator",
    "MiningConfig",
    "MiningResult",
    "ModelConfig",
    "ModelTrainResult",
    "PatternMiner",
    "PatternRecord",
    "PredictiveModel",
    "ReductionConfig",
    "ReductionResult",
    "UncertaintyEstimate",
]
