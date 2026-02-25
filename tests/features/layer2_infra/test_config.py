"""BDD test runner for Configuration (L2 Infrastructure)."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.config_steps import *  # noqa: F401, F403

scenarios("config.feature")
