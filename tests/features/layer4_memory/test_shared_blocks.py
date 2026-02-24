"""BDD test runner for Shared Blocks (Tier C) — stub.

Binds scenarios from shared_blocks.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.memory_steps import *  # noqa: F401, F403

scenarios("shared_blocks.feature")
