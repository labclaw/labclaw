"""Tests for Write skill exception handler.

Covers lines 94-96: exception handler in _write_section.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from labclaw.brain.skills.write import WriteSkill
from labclaw.brain.types import BrainResult


class TestWriteSectionException:
    """Cover lines 94-96: exception handler in _write_section."""

    @pytest.mark.asyncio
    async def test_write_section_exception_returns_error(self) -> None:
        """When LLM provider throws, _write_section catches and returns error."""
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = ConnectionError("LLM service unavailable")
        skill = WriteSkill(llm_provider=mock_llm)

        result = await skill.execute("write_section", section="methods", context="Surgery")
        assert isinstance(result, BrainResult)
        assert result.success is False
        assert "LLM service unavailable" in (result.error or "")
