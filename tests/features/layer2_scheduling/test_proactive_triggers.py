"""BDD test runner for proactive engine (L2 Scheduling)."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.proactive_steps import *  # noqa: F401, F403

scenarios("proactive_triggers.feature")
