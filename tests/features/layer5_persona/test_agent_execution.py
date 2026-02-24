"""BDD test runner for Agent Execution (L5 Persona).

Binds scenarios from test_agent_execution.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403

# Import step definitions so pytest-bdd can find them
from tests.features.step_definitions.test_agent_execution_steps import *  # noqa: F401, F403

# Bind all scenarios in the feature file to test functions
scenarios("test_agent_execution.feature")
