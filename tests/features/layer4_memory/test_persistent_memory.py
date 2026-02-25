"""BDD test runner for Persistent Memory (C3: REMEMBER)."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.persistent_memory_steps import *  # noqa: F401, F403

scenarios("persistent_memory.feature")
