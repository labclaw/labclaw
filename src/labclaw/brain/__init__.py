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
    # Try to create LLM provider from environment (Fireworks > OpenAI)
    llm_provider = _create_llm_provider()

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

        registry.register(LifeSciSkill(llm_provider=llm_provider))
    except Exception:
        logger.warning("Failed to register LifeSci", exc_info=True)

    # Write (needs LLM provider)
    try:
        from labclaw.brain.skills.write import WriteSkill

        registry.register(WriteSkill(llm_provider=llm_provider))
    except Exception:
        logger.warning("Failed to register Write", exc_info=True)


def _create_llm_provider() -> Any | None:
    """Create LLM provider from environment variables.

    Priority: Fireworks AI (FIREWORKS_API_KEY) > OpenAI (OPENAI_API_KEY)
    """
    import os

    # Try Fireworks AI first (Kimi 2.5)
    fireworks_key = os.environ.get("FIREWORKS_API_KEY")
    if fireworks_key:
        try:
            from labclaw.llm.providers.openai_provider import FireworksProvider

            logger.info("Using Fireworks AI provider (Kimi 2.5)")
            return FireworksProvider()
        except Exception as exc:
            logger.warning("Failed to create Fireworks provider: %s", exc)

    # Fallback to OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from labclaw.llm.providers.openai_provider import OpenAIProvider

            logger.info("Using OpenAI provider")
            return OpenAIProvider()
        except Exception as exc:
            logger.warning("Failed to create OpenAI provider: %s", exc)

    logger.info("No LLM provider configured (set FIREWORKS_API_KEY or OPENAI_API_KEY)")
    return None


async def execute(tool_name: str, **kwargs: Any) -> BrainResult:
    """Execute a scientific tool by name.

    Args:
        tool_name: Name of the tool to execute.
        **kwargs: Tool-specific arguments.

    Returns:
        BrainResult with success status, data, or error message.
    """
    return await _get_registry().execute(tool_name, **kwargs)


async def list_tools(category: str = "") -> list[ToolInfo]:
    """List all available tools, optionally filtered by category.

    Args:
        category: Optional category filter (e.g., "genomics", "chemistry").

    Returns:
        List of ToolInfo objects describing available tools.
    """
    return await _get_registry().list_all_tools(category=category)


async def reason(question: str, *, domain: str = "general", context: str = "") -> BrainResult:
    """Life science domain reasoning via LLM.

    Args:
        question: The scientific question to answer.
        domain: Domain specialization (e.g., "genomics", "neuroscience").
        context: Additional context to inform the reasoning.

    Returns:
        BrainResult with the reasoning output or error.
    """
    return await _get_registry().execute(
        "reason", question=question, domain=domain, context=context
    )


async def write(*, section: str, context: str) -> BrainResult:
    """Generate a scientific writing section via LLM.

    Args:
        section: Type of section to write (e.g., "methods", "abstract", "intro").
        context: Content or notes to base the writing on.

    Returns:
        BrainResult with the generated text or error.
    """
    return await _get_registry().execute("write_section", section=section, context=context)


async def health() -> HealthStatus:
    """Check Cloud Brain health status.

    Returns:
        HealthStatus with system status, skill health, and tool count.
    """
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
