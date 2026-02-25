"""BDD test runner for API Security (L2 Infrastructure).

Binds scenarios from api_security.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.api_security_steps import *  # noqa: F401, F403

scenarios("api_security.feature")
