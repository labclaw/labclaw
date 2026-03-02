"""BDD test runner for background task queue (L2 Scheduling)."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.task_queue_steps import *  # noqa: F401, F403

scenarios("task_queue.feature")
