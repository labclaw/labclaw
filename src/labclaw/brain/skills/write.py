"""Scientific writing skill — report and paper section generation.

Uses an LLM provider to generate structured scientific text: methods,
results, discussion, etc. Also provides citation formatting (no LLM needed).

Implements the CloudSkill protocol.
"""

from __future__ import annotations

import logging
from typing import Any

from labclaw.brain.skills.base import SkillCapability, SkillMetadata
from labclaw.brain.types import BrainResult, ToolInfo
from labclaw.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

_SECTION_PROMPTS: dict[str, str] = {
    "abstract": (
        "Write a concise scientific abstract summarizing the following findings. "
        "Include background, methods, key results, and conclusions."
    ),
    "methods": (
        "Write a Methods section describing the experimental procedures "
        "based on the following protocol and parameters."
    ),
    "results": (
        "Write a Results section presenting the following experimental data "
        "and statistical findings. Be quantitative and specific."
    ),
    "discussion": (
        "Write a Discussion section interpreting the following results "
        "in the context of the current literature. Identify limitations."
    ),
    "summary": (
        "Write a brief summary of the following experimental cycle, "
        "highlighting key discoveries and next steps."
    ),
}


class WriteSkill:
    """Scientific writing skill — text generation for the cloud brain."""

    metadata: SkillMetadata = SkillMetadata(
        name="write",
        version="0.1.0",
        description="Scientific writing: methods, results, discussions, citations.",
        capabilities=[
            SkillCapability.WRITING,
        ],
    )

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm_provider = llm_provider

    async def execute(self, tool_name: str, **kwargs: Any) -> BrainResult:
        """Route to the appropriate tool by name."""
        if tool_name == "write_section":
            return await self._write_section(**kwargs)
        if tool_name == "format_citation":
            return await self._format_citation(**kwargs)
        return BrainResult(
            success=False,
            error=f"Unknown tool '{tool_name}'. Available: write_section, format_citation",
        )

    async def _write_section(
        self,
        section: str = "summary",
        context: str = "",
        **kwargs: Any,
    ) -> BrainResult:
        """Generate a scientific text section from context."""
        if self._llm_provider is None:
            return BrainResult(success=False, error="No LLM provider configured")
        try:
            system_prompt = _SECTION_PROMPTS.get(
                section,
                f"Write a {section} section for a scientific paper based on the following.",
            )
            result = await self._llm_provider.complete(
                context,
                system=system_prompt,
                temperature=0.4,
                max_tokens=2048,
            )
            return BrainResult(
                success=True,
                data={"text": str(result).strip(), "section": section},
            )
        except Exception as exc:
            logger.warning("Scientific writing failed: %s", exc)
            return BrainResult(success=False, error=str(exc))

    async def _format_citation(
        self,
        title: str = "",
        authors: list[str] | None = None,
        year: int = 0,
        journal: str = "",
        doi: str = "",
        style: str = "apa",
        **kwargs: Any,
    ) -> BrainResult:
        """Format a citation in the specified style. No LLM needed."""
        author_str = ", ".join(authors) if authors else "Unknown"
        year_str = str(year) if year else "n.d."

        if style == "apa":
            citation = f"{author_str} ({year_str}). {title}."
            if journal:
                citation += f" {journal}."
            if doi:
                citation += f" https://doi.org/{doi}"
        else:
            citation = f"{author_str}. {title}. {journal} ({year_str})."
            if doi:
                citation += f" doi:{doi}"

        return BrainResult(
            success=True,
            data={"citation": citation, "style": style},
        )

    async def list_tools(self) -> list[ToolInfo]:
        """Return the 2 available tools."""
        return [
            ToolInfo(
                name="write_section",
                description=(
                    "Generate a scientific text section (abstract, methods, "
                    "results, discussion, or summary) from context."
                ),
                skill="write",
                category="writing",
            ),
            ToolInfo(
                name="format_citation",
                description="Format a scientific citation in APA or other styles.",
                skill="write",
                category="writing",
            ),
        ]

    async def health_check(self) -> bool:
        """Always True — format_citation works without LLM."""
        return True
