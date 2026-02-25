"""BDD test runner for Pipeline CLI (L2 Infrastructure).

Binds scenarios from pipeline_cli.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.pipeline_cli_steps import *  # noqa: F401, F403

scenarios("pipeline_cli.feature")
