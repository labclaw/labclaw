"""BDD test runner for scipy/numpy-based pattern mining.

Binds scenarios from test_mining_scipy.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.discovery_steps import *  # noqa: F401, F403
from tests.features.step_definitions.mining_scipy_steps import *  # noqa: F401, F403

scenarios("test_mining_scipy.feature")
