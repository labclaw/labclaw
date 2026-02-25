"""BDD test runner for Self-Evolution Cycles (C2: EVOLVE).

Binds scenarios from evolution_cycles.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.evolution_runner_steps import *  # noqa: F401, F403

# Bind all scenarios in the feature file to test functions
scenarios("evolution_cycles.feature")
