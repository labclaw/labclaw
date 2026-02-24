from __future__ import annotations

from labclaw.plugins.base import DomainPlugin
from labclaw.plugins.domains.generic import GenericDomainPlugin


def test_get_sample_node_types_empty() -> None:
    assert GenericDomainPlugin().get_sample_node_types() == {}


def test_get_sentinel_rules_empty() -> None:
    assert GenericDomainPlugin().get_sentinel_rules() == []


def test_get_hypothesis_templates_empty() -> None:
    assert GenericDomainPlugin().get_hypothesis_templates() == []


def test_metadata_name_and_plugin_type() -> None:
    plugin = GenericDomainPlugin()

    assert plugin.metadata.name == "generic"
    assert plugin.metadata.plugin_type == "domain"


def test_is_instance_of_domain_plugin_protocol() -> None:
    assert isinstance(GenericDomainPlugin(), DomainPlugin)
