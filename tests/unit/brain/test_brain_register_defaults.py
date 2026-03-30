"""Tests for _register_defaults exception handlers in brain/__init__.py.

Covers lines 42-43 (LifeSci generic exception) and 50-51 (Write generic exception).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from labclaw.brain.skills.registry import SkillRegistry


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset the global registry before each test."""
    import labclaw.brain as brain_mod

    brain_mod._registry = None
    yield
    brain_mod._registry = None


class TestRegisterDefaultsGenericException:
    """Cover the generic Exception handlers for LifeSci and Write registration."""

    def test_lifesci_generic_exception_caught(self) -> None:
        """When LifeSciSkill() raises a non-ImportError, it's caught and logged."""
        import labclaw.brain as brain_mod

        registry = SkillRegistry()

        with patch(
            "labclaw.brain.skills.lifesci.LifeSciSkill",
            side_effect=RuntimeError("LLM init failed"),
        ):
            # ToolUniverse may also fail — patch it too
            with patch(
                "labclaw.brain.skills.tooluniverse.ToolUniverseSkill",
                side_effect=ImportError("no tooluniverse"),
            ):
                brain_mod._register_defaults(registry)

        # LifeSci should NOT be registered since it raised
        assert "lifesci" not in registry.list_skills()

    def test_write_generic_exception_caught(self) -> None:
        """When WriteSkill() raises a non-ImportError, it's caught and logged."""
        import labclaw.brain as brain_mod

        registry = SkillRegistry()

        with patch(
            "labclaw.brain.skills.lifesci.LifeSciSkill",
            side_effect=RuntimeError("no LLM"),
        ):
            with patch(
                "labclaw.brain.skills.write.WriteSkill",
                side_effect=ValueError("write init boom"),
            ):
                with patch(
                    "labclaw.brain.skills.tooluniverse.ToolUniverseSkill",
                    side_effect=ImportError("no tooluniverse"),
                ):
                    brain_mod._register_defaults(registry)

        # Write should NOT be registered
        assert "write" not in registry.list_skills()
