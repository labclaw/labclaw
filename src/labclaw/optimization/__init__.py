"""Optimization — closed-loop experimental adaptation.

Maps to the EXPERIMENT step of the scientific method:
instead of fixed experimental designs, adapt parameters based on accumulating evidence.

Spec: docs/specs/L3-optimization.md
Design doc: section 5.4 (Conductor), section 9.3 (Two-Layer Safety)
"""

from labclaw.optimization.approval import ApprovalGate, ApprovalRequest
from labclaw.optimization.optimizer import (
    BayesianOptimizer,
    ExperimentProposal,
    OptimizationResult,
    ParameterDimension,
    ParameterSpace,
)
from labclaw.optimization.proposal import ExperimentPipeline
from labclaw.optimization.safety import (
    SafetyCheckDetail,
    SafetyConstraint,
    ScientificSafetyCheck,
    ScientificSafetyValidator,
)

__all__ = [
    "ApprovalGate",
    "ApprovalRequest",
    "BayesianOptimizer",
    "ExperimentPipeline",
    "ExperimentProposal",
    "OptimizationResult",
    "ParameterDimension",
    "ParameterSpace",
    "SafetyCheckDetail",
    "SafetyConstraint",
    "ScientificSafetyCheck",
    "ScientificSafetyValidator",
]
