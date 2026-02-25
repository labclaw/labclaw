"""BDD test runner for Hybrid Memory Search (L4 Memory).

Binds scenarios from memory_search.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.memory_steps import *  # noqa: F401, F403

scenarios("memory_search.feature")
