"""BDD test runner for Agent Tools (L5 Persona).

Binds scenarios from agent_tools.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.agent_tool_steps import *  # noqa: F401, F403
from tests.features.step_definitions.common_steps import *  # noqa: F401, F403

scenarios("agent_tools.feature")
