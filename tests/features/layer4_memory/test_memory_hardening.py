"""BDD test runner for Memory Layer Hardening."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.memory_hardening_steps import *  # noqa: F401, F403
from tests.features.step_definitions.memory_steps import *  # noqa: F401, F403

scenarios("memory_hardening.feature")
