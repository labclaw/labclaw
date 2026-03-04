"""Neuroscience domain & analysis plugins.

Implements both :class:`~labclaw.plugins.base.DomainPlugin` and
:class:`~labclaw.plugins.base.AnalysisPlugin` protocols.

Provides
--------
- :class:`AnimalSampleNode` — subject node with species, genotype, sex, etc.
- Sentinel rules — fluorescence baseline, behavioral metric bounds
- Hypothesis templates — gene expression correlation, behaviour-neural coupling
- Mining algorithms — neural-behavioral cross-correlation
- Validators — session consistency check
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from labclaw.core.graph import SampleNode
from labclaw.plugins.base import AnalysisPlugin, DomainPlugin, PluginMetadata

# ---------------------------------------------------------------------------
# Domain-specific sample node
# ---------------------------------------------------------------------------


class AnimalSampleNode(SampleNode):
    """Animal subject node — extends SampleNode with neuro-specific fields.

    ``sample_type`` is set to ``"animal"`` by default.
    """

    species: str = ""
    genotype: str | None = None
    sex: str | None = None
    date_of_birth: datetime | None = None
    surgical_history: list[str] = []
    experiment_id: str | None = None  # ExperimentNode reference

    def model_post_init(self, _context: Any) -> None:
        super().model_post_init(_context)
        if not self.sample_type:
            self.sample_type = "animal"


# ---------------------------------------------------------------------------
# Plugin implementation
# ---------------------------------------------------------------------------


class NeuroscienceDomainPlugin:
    """Domain plugin for neuroscience labs."""

    metadata: PluginMetadata = PluginMetadata(
        name="neuroscience",
        version="1.0.0",
        description="Neuroscience domain: animal subjects, imaging sentinels, neuro hypotheses.",
        author="labclaw-core",
        plugin_type="domain",
    )

    def get_sample_node_types(self) -> dict[str, type]:
        """Return domain-specific sample node types."""
        return {
            "animal": AnimalSampleNode,
        }

    def get_sentinel_rules(self) -> list[dict[str, Any]]:
        """Sentinel rules for neuroscience data quality."""
        return [
            {
                "name": "fluorescence_baseline_low",
                "description": "Two-photon baseline fluorescence below acceptable threshold",
                "metric": "baseline_fluorescence",
                "operator": "<",
                "threshold": 100.0,
                "unit": "a.u.",
                "severity": "warning",
                "action": "flag_session",
            },
            {
                "name": "fluorescence_saturation",
                "description": "Fluorescence signal saturated — likely overexposed",
                "metric": "peak_fluorescence",
                "operator": ">",
                "threshold": 65000.0,
                "unit": "a.u.",
                "severity": "critical",
                "action": "block_analysis",
            },
            {
                "name": "behavioral_accuracy_low",
                "description": "Task accuracy below chance — check behavioral setup",
                "metric": "task_accuracy",
                "operator": "<",
                "threshold": 0.55,
                "unit": "fraction",
                "severity": "warning",
                "action": "flag_session",
            },
            {
                "name": "running_speed_zero",
                "description": "Animal not moving — treadmill or sensor may be disconnected",
                "metric": "mean_running_speed",
                "operator": "==",
                "threshold": 0.0,
                "unit": "cm/s",
                "severity": "warning",
                "action": "flag_session",
            },
        ]

    def get_hypothesis_templates(self) -> list[dict[str, Any]]:
        """Hypothesis templates for neuroscience experiments."""
        return [
            {
                "id": "neuro.gene_expression_behavior",
                "name": "Gene Expression × Behavior Correlation",
                "description": (
                    "Animals with higher expression of {gene} show "
                    "altered performance in {behavior_metric}."
                ),
                "variables": ["gene", "behavior_metric"],
                "statistical_test": "pearson_r",
                "required_columns": ["genotype", "behavior_metric"],
            },
            {
                "id": "neuro.neural_behavior_coupling",
                "name": "Neural Activity × Behavior Coupling",
                "description": (
                    "Activity in {brain_region} is correlated with "
                    "{behavior_metric} on a trial-by-trial basis."
                ),
                "variables": ["brain_region", "behavior_metric"],
                "statistical_test": "pearson_r",
                "required_columns": ["neural_activity", "behavior_metric"],
            },
            {
                "id": "neuro.session_learning_curve",
                "name": "Session-wise Learning Curve",
                "description": (
                    "Performance on {task} improves across sessions, "
                    "reflecting plasticity in {brain_region}."
                ),
                "variables": ["task", "brain_region"],
                "statistical_test": "linear_regression",
                "required_columns": ["session_number", "task_accuracy"],
            },
            {
                "id": "neuro.perturbation_effect",
                "name": "Optogenetic / Pharmacological Perturbation Effect",
                "description": (
                    "Perturbation of {target} significantly changes "
                    "{outcome_metric} compared to control sessions."
                ),
                "variables": ["target", "outcome_metric"],
                "statistical_test": "paired_t_test",
                "required_columns": ["condition", "outcome_metric"],
            },
        ]


# ---------------------------------------------------------------------------
# Analysis plugin
# ---------------------------------------------------------------------------


class NeuroscienceAnalysisPlugin:
    """Analysis plugin for neuroscience — mining algorithms and validators."""

    metadata: PluginMetadata = PluginMetadata(
        name="neuroscience-analysis",
        version="1.0.0",
        description="Neuroscience analysis: neural-behavioral mining, session consistency.",
        author="labclaw-core",
        plugin_type="analysis",
    )

    def get_mining_algorithms(self) -> list[dict[str, Any]]:
        """Return neuroscience-specific mining algorithm descriptors."""
        return [
            {
                "name": "neural_behavioral_correlation",
                "description": (
                    "Cross-correlate neural activity columns with behavioral "
                    "metric columns to discover activity-behavior coupling."
                ),
                "input_columns": {
                    "neural": ["firing_rate", "calcium_signal", "lfp_power"],
                    "behavioral": ["running_speed", "task_accuracy", "lick_rate"],
                },
                "parameters": {
                    "min_correlation": 0.3,
                    "p_value_threshold": 0.05,
                    "lag_range_ms": [-500, 500],
                },
                "output_pattern_type": "correlation",
            },
        ]

    def get_validators(self) -> list[dict[str, Any]]:
        """Return neuroscience-specific validator descriptors."""
        return [
            {
                "name": "session_consistency",
                "description": (
                    "Check that key metrics remain consistent across sessions "
                    "within the same animal. Flags sessions with >3 SD deviation."
                ),
                "metrics": ["baseline_fluorescence", "task_accuracy", "trial_count"],
                "parameters": {
                    "z_threshold": 3.0,
                    "min_sessions": 3,
                    "group_by": "animal_id",
                },
            },
        ]


assert isinstance(NeuroscienceDomainPlugin(), DomainPlugin)  # protocol check
assert isinstance(NeuroscienceAnalysisPlugin(), AnalysisPlugin)  # protocol check
