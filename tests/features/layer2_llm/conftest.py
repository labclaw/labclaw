"""Conftest for LiteLLM BDD tests — mock litellm module if not installed."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _mock_litellm_module() -> None:
    """Inject a mock litellm module so tests work without litellm installed."""
    if "litellm" not in sys.modules:
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock()
        sys.modules["litellm"] = mock_litellm
