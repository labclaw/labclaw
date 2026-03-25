"""Tests for Cloud Brain skill base types and protocol."""

from __future__ import annotations

from labclaw.brain.skills.base import CloudSkill, SkillCapability, SkillMetadata
from labclaw.brain.types import BrainResult, ToolInfo


class TestSkillCapability:
    """SkillCapability enum values."""

    def test_tool_execution(self) -> None:
        assert SkillCapability.TOOL_EXECUTION == "tool_execution"

    def test_literature_search(self) -> None:
        assert SkillCapability.LITERATURE_SEARCH == "literature_search"

    def test_data_analysis(self) -> None:
        assert SkillCapability.DATA_ANALYSIS == "data_analysis"

    def test_reasoning(self) -> None:
        assert SkillCapability.REASONING == "reasoning"

    def test_writing(self) -> None:
        assert SkillCapability.WRITING == "writing"

    def test_all_values(self) -> None:
        expected = {
            "tool_execution",
            "literature_search",
            "data_analysis",
            "reasoning",
            "writing",
        }
        assert {v.value for v in SkillCapability} == expected


class TestSkillMetadata:
    """SkillMetadata pydantic model."""

    def test_create_minimal(self) -> None:
        meta = SkillMetadata(
            name="test",
            version="0.1.0",
            description="A test skill",
            capabilities=[SkillCapability.REASONING],
        )
        assert meta.name == "test"
        assert meta.version == "0.1.0"
        assert meta.description == "A test skill"
        assert meta.capabilities == [SkillCapability.REASONING]

    def test_create_multiple_capabilities(self) -> None:
        meta = SkillMetadata(
            name="multi",
            version="1.0.0",
            description="Multi-cap",
            capabilities=[
                SkillCapability.TOOL_EXECUTION,
                SkillCapability.DATA_ANALYSIS,
            ],
        )
        assert len(meta.capabilities) == 2


class TestCloudSkillProtocol:
    """CloudSkill is a runtime_checkable Protocol."""

    def test_is_runtime_checkable(self) -> None:
        """A properly shaped object should satisfy isinstance check."""

        class FakeSkill:
            def __init__(self) -> None:
                self.metadata = SkillMetadata(
                    name="fake",
                    version="0.1.0",
                    description="Fake",
                    capabilities=[SkillCapability.REASONING],
                )

            async def execute(self, tool_name: str, **kwargs: object) -> BrainResult:
                return BrainResult(success=True)

            async def list_tools(self) -> list[ToolInfo]:
                return []

            async def health_check(self) -> bool:
                return True

        skill = FakeSkill()
        assert isinstance(skill, CloudSkill)

    def test_non_conforming_object_fails(self) -> None:
        """An object missing methods should NOT satisfy the Protocol."""

        class NotASkill:
            pass

        assert not isinstance(NotASkill(), CloudSkill)
