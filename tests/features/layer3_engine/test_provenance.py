"""BDD tests for provenance.feature."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.provenance_steps import *  # noqa: F401,F403

scenarios("provenance.feature")
