"""BDD test runner for Full Scientific Pipeline (end-to-end).

Binds scenarios from full_pipeline.feature to step definitions in pipeline_steps.py.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.pipeline_steps import *  # noqa: F401, F403

scenarios("full_pipeline.feature")
