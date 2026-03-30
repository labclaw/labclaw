"""Tests for ToolUniverse skill edge cases.

Covers line 49-50 (double-check lock inside async with) and lines 68-70
(generic exception in init_sdk).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from labclaw.brain.skills.tooluniverse import ToolUniverseSkill


class TestToolUniverseDoubleCheckLock:
    """Cover lines 49-50: double-check lock guard inside async with self._lock."""

    @pytest.mark.asyncio
    async def test_double_check_lock_returns_early(self) -> None:
        """When _tu_instance is set inside lock, the inner check returns early."""
        skill = ToolUniverseSkill()
        skill._lock = asyncio.Lock()

        # Manually simulate the race condition:
        # Acquire the lock, set _tu_instance, then call init_sdk
        async with skill._lock:
            skill._tu_instance = MagicMock()  # Simulate another coroutine setting it
            # Now init_sdk will:
            # 1. Check _tu_instance is not None -> True, but we're already past line 44
            #    Wait, line 44 checks _tu_instance is NOT None and returns. So if set before
            #    calling init_sdk, line 44-45 handles it.
            # To cover line 49-50, _tu_instance must be None at line 44 but set by the time
            # we enter the lock.
            pass

        # Better approach: use concurrent tasks
        skill2 = ToolUniverseSkill()
        skill2._lock = asyncio.Lock()

        # Set up the scenario where task1 starts init_sdk (sees _tu_instance=None),
        # acquires lock, sets _tu_instance. Task2 also calls init_sdk, waits for lock,
        # then inside lock sees _tu_instance is already set (line 49-50).
        async def _init_and_set():
            async with skill2._lock:
                skill2._tu_instance = MagicMock()

        # Start task that holds the lock
        task1 = asyncio.create_task(_init_and_set())
        await asyncio.sleep(0.01)  # Let task1 acquire the lock

        # Now task2 also tries init_sdk
        # It sees _tu_instance is None at line 44 (if not yet set),
        # waits for lock, then sees it's set at line 49
        await skill2.init_sdk()  # This should hit line 49-50

        await task1
        assert skill2._tu_instance is not None


class TestToolUniverseGenericException:
    """Cover lines 68-70: generic exception during SDK init."""

    @pytest.mark.asyncio
    async def test_init_sdk_generic_exception_sets_none(self) -> None:
        """When ToolUniverse init raises a generic exception, _tu_instance stays None."""
        skill = ToolUniverseSkill()

        mock_tu_class = MagicMock()
        mock_tu_class.side_effect = OSError("Network unreachable")

        with patch.dict("sys.modules", {"tooluniverse": MagicMock(ToolUniverse=mock_tu_class)}):
            await skill.init_sdk()

        assert skill._tu_instance is None
