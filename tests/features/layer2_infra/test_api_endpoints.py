"""BDD test runner for REST API Endpoints (L2 Infrastructure).

Binds scenarios from api_endpoints.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Import step definitions so pytest-bdd can find them
from tests.features.step_definitions.api_steps import *  # noqa: F401, F403

# Bind all scenarios in the feature file to test functions
scenarios("api_endpoints.feature")
