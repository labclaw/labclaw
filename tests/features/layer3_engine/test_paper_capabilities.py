"""BDD test runner for Paper Capabilities (v0.1.0).

Binds scenarios from paper_capabilities.feature to step definitions in
paper_capabilities_steps.py.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.paper_capabilities_steps import *  # noqa: F401, F403

scenarios("paper_capabilities.feature")
