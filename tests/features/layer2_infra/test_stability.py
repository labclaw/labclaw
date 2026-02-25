"""BDD test runner for Production Stability (v0.0.9)."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.stability_steps import *  # noqa: F401, F403

scenarios("stability.feature")
