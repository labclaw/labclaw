"""BDD test runner for Device Registry (L1 Hardware).

Binds scenarios from device_registry.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403

# Import step definitions so pytest-bdd can find them
from tests.features.step_definitions.hardware_steps import *  # noqa: F401, F403

# Bind all scenarios in the feature file to test functions
scenarios("device_registry.feature")
