"""Skill registry — registers, indexes, and routes to CloudSkill instances."""

from __future__ import annotations

import logging
from typing import Any

from labclaw.brain.skills.base import CloudSkill
from labclaw.brain.types import BrainResult, ToolInfo

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Central registry for Cloud Brain skills."""

    def __init__(self) -> None:
        self._skills: dict[str, CloudSkill] = {}
        self._tool_map: dict[str, str] = {}
        self._tool_map_dirty: bool = True

    def register(self, skill: CloudSkill) -> None:
        """Register a skill. Raises ValueError if name already taken."""
        name = skill.metadata.name
        if name in self._skills:
            msg = f"Skill '{name}' already registered"
            raise ValueError(msg)
        self._skills[name] = skill
        self._tool_map_dirty = True
        logger.info("Registered skill '%s' v%s", name, skill.metadata.version)

    def unregister(self, name: str) -> None:
        """Remove a skill by name. Raises KeyError if not found."""
        if name not in self._skills:
            msg = f"Skill '{name}' not registered"
            raise KeyError(msg)
        del self._skills[name]
        self._tool_map_dirty = True
        logger.info("Unregistered skill '%s'", name)

    def list_skills(self) -> list[str]:
        """Return names of all registered skills."""
        return list(self._skills)

    async def _rebuild_tool_map(self) -> None:
        """Rebuild the tool_name -> skill_name index."""
        self._tool_map.clear()
        for name, skill in self._skills.items():
            for tool in await skill.list_tools():
                self._tool_map[tool.name] = name
        self._tool_map_dirty = False

    async def list_all_tools(self, category: str = "") -> list[ToolInfo]:
        """Aggregate tools from all skills, optionally filtered by category."""
        if self._tool_map_dirty:
            await self._rebuild_tool_map()

        tools: list[ToolInfo] = []
        for skill in self._skills.values():
            for tool in await skill.list_tools():
                if not category or tool.category == category:
                    tools.append(tool)
        return tools

    async def execute(self, tool_name: str, **kwargs: Any) -> BrainResult:
        """Route execution to the skill that owns *tool_name*."""
        if self._tool_map_dirty:
            await self._rebuild_tool_map()

        skill_name = self._tool_map.get(tool_name)
        if skill_name is None:
            logger.warning("Tool '%s' not found in any registered skill", tool_name)
            return BrainResult(success=False, error=f"Tool '{tool_name}' not found")

        skill = self._skills[skill_name]
        logger.debug("Routing '%s' to skill '%s'", tool_name, skill_name)
        return await skill.execute(tool_name, **kwargs)

    async def health(self) -> dict[str, bool]:
        """Check health of every registered skill concurrently."""
        import asyncio

        names = list(self._skills)
        checks = [self._skills[n].health_check() for n in names]
        results = await asyncio.gather(*checks)
        return dict(zip(names, results))
