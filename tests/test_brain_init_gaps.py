"""Cover brain/__init__.py uncovered lines 42-43, 50-51.

Lines 42-43: except Exception when LifeSciSkill() registration fails.
Lines 50-51: except Exception when WriteSkill() registration fails.
"""

from __future__ import annotations

from unittest.mock import patch

from labclaw.brain.skills.registry import SkillRegistry


class TestRegisterDefaultsLifeSciFailure:
    """_register_defaults handles LifeSci constructor failure (lines 42-43)."""

    def test_lifesci_exception_logged_gracefully(self) -> None:
        import labclaw.brain as brain_mod

        registry = SkillRegistry()

        with patch(
            "labclaw.brain.skills.lifesci.LifeSciSkill",
            side_effect=RuntimeError("LLM init failed"),
        ):
            brain_mod._register_defaults(registry)

        # LifeSci should NOT be registered, but write should still succeed
        names = registry.list_skills()
        assert "lifesci" not in names
        assert "write" in names


class TestRegisterDefaultsWriteFailure:
    """_register_defaults handles Write constructor failure (lines 50-51)."""

    def test_write_exception_logged_gracefully(self) -> None:
        import labclaw.brain as brain_mod

        registry = SkillRegistry()

        with patch(
            "labclaw.brain.skills.write.WriteSkill",
            side_effect=RuntimeError("Write init failed"),
        ):
            brain_mod._register_defaults(registry)

        names = registry.list_skills()
        assert "write" not in names
        assert "lifesci" in names
