"""BDD test runner for Miscellaneous Infrastructure Hardening."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.misc_hardening_steps import *  # noqa: F401, F403

scenarios("misc_hardening.feature")
