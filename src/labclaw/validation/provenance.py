"""Provenance — full traceability from discovery to raw data.

Spec: docs/specs/L3-validation.md
Design doc: section 5.5 (Validator)
"""

from __future__ import annotations

import logging

from labclaw.core.events import event_registry
from labclaw.validation.statistics import ProvenanceChain, ProvenanceStep

logger = logging.getLogger(__name__)


class ProvenanceTracker:
    """Builds and verifies provenance chains for findings."""

    def build_chain(
        self,
        finding_id: str,
        steps: list[ProvenanceStep],
    ) -> ProvenanceChain:
        """Build a provenance chain for a finding.

        Args:
            finding_id: The FindingNode ID this chain traces.
            steps: Ordered provenance steps (subject -> ... -> finding).

        Returns:
            A new ProvenanceChain.

        Raises:
            ValueError: If steps list is empty.
        """
        if not steps:
            raise ValueError("Provenance chain must have at least one step")

        chain = ProvenanceChain(finding_id=finding_id, steps=steps)

        event_registry.emit(
            "validation.provenance.built",
            payload={
                "chain_id": chain.chain_id,
                "finding_id": finding_id,
                "step_count": len(steps),
            },
        )

        return chain

    def verify_chain(self, chain: ProvenanceChain) -> bool:
        """Verify that a provenance chain is valid.

        Checks:
        - Chain has a non-empty finding_id
        - Chain has at least one step
        - All steps have non-empty node_id and node_type
        """
        if not chain.finding_id:
            return False

        if not chain.steps:
            return False

        for step in chain.steps:
            if not step.node_id or not step.node_type:
                return False

        return True
