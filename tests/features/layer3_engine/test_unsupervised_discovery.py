"""BDD test runner for Unsupervised Discovery.

Binds scenarios from unsupervised_discovery.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.unsupervised_steps import *  # noqa: F401, F403

scenarios("unsupervised_discovery.feature")
