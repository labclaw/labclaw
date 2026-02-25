"""BDD test runner for Plugin Security (L2 Infrastructure).

Binds scenarios from test_plugin_security.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.plugin_security_steps import *  # noqa: F401, F403

scenarios("test_plugin_security.feature")
