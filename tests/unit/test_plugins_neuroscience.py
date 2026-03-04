from __future__ import annotations

from labclaw.plugins.base import AnalysisPlugin, DomainPlugin
from labclaw.plugins.domains.neuroscience import (
    AnimalSampleNode,
    NeuroscienceAnalysisPlugin,
    NeuroscienceDomainPlugin,
)

# ---------------------------------------------------------------------------
# AnimalSampleNode
# ---------------------------------------------------------------------------


def test_animal_sample_node_sets_sample_type() -> None:
    node = AnimalSampleNode(node_id="a-001", label="Mouse 1", species="Mus musculus")

    assert node.sample_type == "animal"
    assert node.label == "Mouse 1"
    assert node.species == "Mus musculus"


# ---------------------------------------------------------------------------
# NeuroscienceDomainPlugin.metadata
# ---------------------------------------------------------------------------


def test_plugin_metadata_name() -> None:
    plugin = NeuroscienceDomainPlugin()

    assert plugin.metadata.name == "neuroscience"


# ---------------------------------------------------------------------------
# get_sample_node_types
# ---------------------------------------------------------------------------


def test_get_sample_node_types_returns_animal_key() -> None:
    plugin = NeuroscienceDomainPlugin()
    types = plugin.get_sample_node_types()

    assert "animal" in types
    assert types["animal"] is AnimalSampleNode


# ---------------------------------------------------------------------------
# get_sentinel_rules
# ---------------------------------------------------------------------------


def test_get_sentinel_rules_returns_four_items() -> None:
    rules = NeuroscienceDomainPlugin().get_sentinel_rules()

    assert len(rules) == 4


def test_get_sentinel_rules_each_has_required_keys() -> None:
    required = {"name", "metric", "threshold", "severity"}
    for rule in NeuroscienceDomainPlugin().get_sentinel_rules():
        assert required <= rule.keys(), f"Rule missing keys: {rule}"


# ---------------------------------------------------------------------------
# get_hypothesis_templates
# ---------------------------------------------------------------------------


def test_get_hypothesis_templates_returns_four_items() -> None:
    templates = NeuroscienceDomainPlugin().get_hypothesis_templates()

    assert len(templates) == 4


def test_get_hypothesis_templates_each_has_required_keys() -> None:
    required = {"id", "name", "variables", "statistical_test"}
    for tmpl in NeuroscienceDomainPlugin().get_hypothesis_templates():
        assert required <= tmpl.keys(), f"Template missing keys: {tmpl}"


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_plugin_is_instance_of_domain_plugin_protocol() -> None:
    assert isinstance(NeuroscienceDomainPlugin(), DomainPlugin)


# ---------------------------------------------------------------------------
# NeuroscienceAnalysisPlugin
# ---------------------------------------------------------------------------


def test_analysis_plugin_metadata() -> None:
    plugin = NeuroscienceAnalysisPlugin()
    assert plugin.metadata.name == "neuroscience-analysis"
    assert plugin.metadata.plugin_type == "analysis"


def test_analysis_plugin_mining_algorithms() -> None:
    algorithms = NeuroscienceAnalysisPlugin().get_mining_algorithms()
    assert len(algorithms) == 1
    algo = algorithms[0]
    assert algo["name"] == "neural_behavioral_correlation"
    assert "input_columns" in algo
    assert "parameters" in algo


def test_analysis_plugin_validators() -> None:
    validators = NeuroscienceAnalysisPlugin().get_validators()
    assert len(validators) == 1
    validator = validators[0]
    assert validator["name"] == "session_consistency"
    assert "metrics" in validator
    assert "parameters" in validator


def test_analysis_plugin_is_instance_of_analysis_protocol() -> None:
    assert isinstance(NeuroscienceAnalysisPlugin(), AnalysisPlugin)
