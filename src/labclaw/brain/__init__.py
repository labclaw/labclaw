"""Cloud Brain — unified gateway to 2400+ scientific tools."""

from __future__ import annotations

import logging
from typing import Any

from labclaw.brain.skills.registry import SkillRegistry
from labclaw.brain.types import BrainResult, HealthStatus, ToolInfo

logger = logging.getLogger(__name__)

_registry: SkillRegistry | None = None


def _get_registry() -> SkillRegistry:
    """Get or create the global registry with default skills."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _register_defaults(_registry)
    return _registry


def _register_defaults(registry: SkillRegistry) -> None:
    """Register built-in skills. Gracefully skip unavailable ones."""
    # ToolUniverse (optional dep)
    try:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        registry.register(ToolUniverseSkill())
    except ImportError:
        logger.info("ToolUniverse not installed, skipping")
    except Exception:
        logger.warning("Failed to register ToolUniverse", exc_info=True)

    # LifeSci (needs LLM provider)
    try:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        registry.register(LifeSciSkill())
    except Exception:
        logger.warning("Failed to register LifeSci", exc_info=True)

    # Write (needs LLM provider)
    try:
        from labclaw.brain.skills.write import WriteSkill

        registry.register(WriteSkill())
    except Exception:
        logger.warning("Failed to register Write", exc_info=True)


async def execute(tool_name: str, **kwargs: Any) -> BrainResult:
    """Execute a scientific tool by name."""
    return await _get_registry().execute(tool_name, **kwargs)


async def list_tools(category: str = "") -> list[ToolInfo]:
    """List all available tools, optionally filtered by category."""
    return await _get_registry().list_all_tools(category=category)


async def reason(question: str, *, domain: str = "general", context: str = "") -> BrainResult:
    """Life science domain reasoning."""
    return await _get_registry().execute(
        "reason", question=question, domain=domain, context=context
    )


async def write(*, section: str, context: str) -> BrainResult:
    """Generate a scientific writing section."""
    return await _get_registry().execute("write_section", section=section, context=context)


async def health() -> HealthStatus:
    """Check Cloud Brain health."""
    import labclaw

    reg = _get_registry()
    skill_health = await reg.health()
    all_tools = await reg.list_all_tools()
    status = "ok" if all(skill_health.values()) else "degraded"
    if not skill_health:
        status = "degraded"
    return HealthStatus(
        status=status,
        skills=skill_health,
        tool_count=len(all_tools),
        version=getattr(labclaw, "__version__", "0.0.1"),
    )
