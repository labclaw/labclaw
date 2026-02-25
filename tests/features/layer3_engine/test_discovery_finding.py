"""BDD test runner for First Discovery (C1: DISCOVER).

Binds scenarios from discovery_finding.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.discovery_finding_steps import *  # noqa: F401, F403

scenarios("discovery_finding.feature")
