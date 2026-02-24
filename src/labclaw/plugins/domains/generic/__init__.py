"""Generic domain plugin — default, no domain-specific logic.

Satisfies the DomainPlugin protocol with empty/no-op implementations so that
LabClaw works out-of-the-box without any domain pack installed.
"""

from __future__ import annotations

from typing import Any

from labclaw.plugins.base import DomainPlugin, PluginMetadata


class GenericDomainPlugin:
    """Default domain plugin with no domain-specific extensions."""

    metadata: PluginMetadata = PluginMetadata(
        name="generic",
        version="1.0.0",
        description="Generic domain — no domain-specific nodes, rules, or templates.",
        author="labclaw-core",
        plugin_type="domain",
    )

    def get_sample_node_types(self) -> dict[str, type]:
        """No domain-specific sample node types."""
        return {}

    def get_sentinel_rules(self) -> list[dict[str, Any]]:
        """No domain-specific sentinel rules."""
        return []

    def get_hypothesis_templates(self) -> list[dict[str, Any]]:
        """No domain-specific hypothesis templates."""
        return []


assert isinstance(GenericDomainPlugin(), DomainPlugin)  # protocol check
