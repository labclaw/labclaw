"""BDD test runner for Predictive Modeling.

Binds scenarios from predictive_modeling.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.modeling_steps import *  # noqa: F401, F403

scenarios("predictive_modeling.feature")
