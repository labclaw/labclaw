"""BDD test runner for Hardware Manager (L1 Hardware)."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.hardware_steps import *  # noqa: F401, F403

scenarios("hardware_manager.feature")
