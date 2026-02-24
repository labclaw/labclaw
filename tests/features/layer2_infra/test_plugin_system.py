"""BDD test runner for Plugin System (L2 Infrastructure).

Binds scenarios from test_plugin_system.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403

# Import step definitions so pytest-bdd can find them
from tests.features.step_definitions.test_plugin_steps import *  # noqa: F401, F403

# Bind all scenarios in the feature file to test functions
scenarios("test_plugin_system.feature")
