"""Skill protocol and metadata types."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from labclaw.brain.types import BrainResult, ToolInfo


class SkillCapability(StrEnum):
    """Capabilities a CloudSkill can advertise."""

    TOOL_EXECUTION = "tool_execution"
    LITERATURE_SEARCH = "literature_search"
    DATA_ANALYSIS = "data_analysis"
    REASONING = "reasoning"
    WRITING = "writing"


class SkillMetadata(BaseModel):
    """Descriptive metadata attached to every skill."""

    name: str
    version: str
    description: str
    capabilities: list[SkillCapability]


@runtime_checkable
class CloudSkill(Protocol):
    """Interface that every Cloud Brain skill must satisfy."""

    metadata: SkillMetadata

    async def execute(self, tool_name: str, **kwargs: Any) -> BrainResult: ...

    async def list_tools(self) -> list[ToolInfo]: ...

    async def health_check(self) -> bool: ...
