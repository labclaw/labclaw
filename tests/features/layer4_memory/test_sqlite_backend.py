"""BDD test runner for SQLite Tier B Backend (L4 Memory).

Binds scenarios from sqlite_backend.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.memory_steps import *  # noqa: F401, F403

scenarios("sqlite_backend.feature")
