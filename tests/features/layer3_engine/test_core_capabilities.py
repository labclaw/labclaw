"""BDD test runner for Core Capabilities.

Binds scenarios from core_capabilities.feature to step definitions in
core_capabilities_steps.py.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.core_capabilities_steps import *  # noqa: F401, F403

scenarios("core_capabilities.feature")
