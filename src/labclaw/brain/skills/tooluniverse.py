"""ToolUniverse skill — integration with mims-harvard/ToolUniverse SDK.

Uses the tooluniverse Python package to provide 2000+ scientific tools
covering UniProt, ChEMBL, PubChem, OpenTargets, FAERS, ClinicalTrials, etc.

Implements the CloudSkill protocol with asyncio.Lock for singleton init
and asyncio.wait_for() timeout on all SDK calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from labclaw.brain.skills.base import SkillCapability, SkillMetadata
from labclaw.brain.types import BrainResult, ToolInfo

logger = logging.getLogger(__name__)


class ToolUniverseSkill:
    """ToolUniverse integration — 2000+ scientific tools via SDK."""

    metadata: SkillMetadata = SkillMetadata(
        name="tooluniverse",
        version="0.1.0",
        description=(
            "2000+ scientific tools via ToolUniverse SDK: UniProt, "
            "ChEMBL, PubChem, OpenTargets, ClinicalTrials, and more."
        ),
        capabilities=[
            SkillCapability.TOOL_EXECUTION,
            SkillCapability.DATA_ANALYSIS,
        ],
    )

    def __init__(self) -> None:
        self._tu_instance: Any = None
        self._lock = asyncio.Lock()

    async def init_sdk(self) -> None:
        """Lazy-initialize the ToolUniverse singleton with asyncio.Lock."""
        if self._tu_instance is not None:
            return
        async with self._lock:
            if self._tu_instance is not None:
                return  # pragma: no cover
            try:
                from tooluniverse import ToolUniverse

                loop = asyncio.get_running_loop()
                instance = await loop.run_in_executor(None, ToolUniverse)
                await loop.run_in_executor(None, instance.load_tools)
                self._tu_instance = instance
                logger.info(
                    "ToolUniverse initialized with %d tools",
                    len(instance.return_all_loaded_tools()),
                )
            except (ImportError, ModuleNotFoundError):
                logger.warning("tooluniverse package not installed")
                self._tu_instance = None
            except Exception as exc:
                logger.warning("ToolUniverse init failed: %s", exc)
                self._tu_instance = None

    async def execute(self, tool_name: str, **kwargs: Any) -> BrainResult:
        """Execute a ToolUniverse tool by name."""
        if self._tu_instance is None:
            return BrainResult(
                success=False,
                error="ToolUniverse SDK not initialized. Call init_sdk() first.",
            )
        try:
            tu = self._tu_instance
            payload = {"name": tool_name, "arguments": kwargs}
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, tu.run, payload),
                timeout=30.0,
            )

            if isinstance(result, dict) and result.get("status") == "error":
                return BrainResult(
                    success=False,
                    error=result.get("error", "Unknown error"),
                )

            return BrainResult(success=True, data=result)
        except TimeoutError:
            logger.warning("ToolUniverse run(%s) timed out after 30s", tool_name)
            return BrainResult(success=False, error=f"Tool {tool_name} timed out after 30s")
        except Exception as exc:
            logger.warning("ToolUniverse run(%s) failed: %s", tool_name, exc)
            return BrainResult(success=False, error=str(exc))

    async def list_tools(self) -> list[ToolInfo]:
        """Return all loaded tools as ToolInfo list."""
        if self._tu_instance is None:
            return []
        raw_tools = self._tu_instance.return_all_loaded_tools()
        return [
            ToolInfo(
                name=t.get("name", ""),
                description=str(t.get("description", ""))[:200],
                skill="tooluniverse",
                category=t.get("category", ""),
            )
            for t in raw_tools
        ]

    async def health_check(self) -> bool:
        """Return True if ToolUniverse SDK instance is loaded."""
        return self._tu_instance is not None
