"""Life Science LLM skill — domain-specific reasoning for biology and medicine.

Uses an LLM provider with life-science-tuned system prompts to provide
expert reasoning about biological systems and experimental design.

Implements the CloudSkill protocol.
"""

from __future__ import annotations

import logging
from typing import Any

from labclaw.brain.skills.base import SkillCapability, SkillMetadata
from labclaw.brain.types import BrainResult, ToolInfo
from labclaw.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

_LIFESCI_SYSTEM_PROMPT = (
    "You are a life science expert with deep knowledge in molecular biology, "
    "neuroscience, genomics, and experimental design. Provide scientifically "
    "rigorous analysis grounded in current understanding. When uncertain, "
    "state confidence levels and cite relevant biological mechanisms."
)

_EXPERIMENT_DESIGN_PROMPT = (
    "You are an expert in experimental design for biological research. "
    "Consider controls, sample sizes, statistical power, potential confounds, "
    "and ethical requirements. Be specific about protocols and reagents."
)


class LifeSciSkill:
    """Life Science LLM skill — domain reasoning for the cloud brain."""

    metadata: SkillMetadata = SkillMetadata(
        name="lifesci",
        version="0.1.0",
        description="Life science domain reasoning, experiment design, and biological analysis.",
        capabilities=[
            SkillCapability.REASONING,
        ],
    )

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm_provider = llm_provider

    async def execute(self, tool_name: str, **kwargs: Any) -> BrainResult:
        """Route to the appropriate tool by name."""
        if tool_name == "reason":
            return await self._reason(**kwargs)
        if tool_name == "design_experiment":
            return await self._design_experiment(**kwargs)
        return BrainResult(
            success=False,
            error=f"Unknown tool '{tool_name}'. Available: reason, design_experiment",
        )

    async def _reason(
        self,
        question: str = "",
        domain: str = "general",
        **kwargs: Any,
    ) -> BrainResult:
        """Apply life science domain reasoning to a question."""
        if self._llm_provider is None:
            return BrainResult(success=False, error="No LLM provider configured")
        try:
            prompt_parts = [question]
            if domain != "general":
                prompt_parts.append(f"\nFocus domain: {domain}")

            result = await self._llm_provider.complete(
                "\n".join(prompt_parts),
                system=_LIFESCI_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=2048,
            )
            return BrainResult(
                success=True,
                data={"answer": str(result).strip(), "domain": domain},
            )
        except Exception as exc:
            logger.warning("Life science reasoning failed: %s", exc)
            return BrainResult(success=False, error=str(exc))

    async def _design_experiment(
        self,
        description: str = "",
        **kwargs: Any,
    ) -> BrainResult:
        """Design an experiment to test a hypothesis."""
        if self._llm_provider is None:
            return BrainResult(success=False, error="No LLM provider configured")
        try:
            result = await self._llm_provider.complete(
                f"Experiment to design:\n{description}",
                system=_EXPERIMENT_DESIGN_PROMPT,
                temperature=0.4,
                max_tokens=2048,
            )
            return BrainResult(
                success=True,
                data={"design": str(result).strip(), "description": description},
            )
        except Exception as exc:
            logger.warning("Experiment design failed: %s", exc)
            return BrainResult(success=False, error=str(exc))

    async def list_tools(self) -> list[ToolInfo]:
        """Return the 2 available tools."""
        return [
            ToolInfo(
                name="reason",
                description=(
                    "Apply life science domain expertise to answer a biological "
                    "question with scientifically rigorous analysis."
                ),
                skill="lifesci",
                category="reasoning",
            ),
            ToolInfo(
                name="design_experiment",
                description=(
                    "Design a rigorous experiment including controls, sample sizes, "
                    "and protocol details."
                ),
                skill="lifesci",
                category="reasoning",
            ),
        ]

    async def health_check(self) -> bool:
        """Return True if LLM provider is configured."""
        return self._llm_provider is not None
