"""BDD test runner for LLM Providers (L5 Persona).

Binds scenarios from llm_providers.feature to step definitions.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.common_steps import *  # noqa: F401, F403
from tests.features.step_definitions.llm_provider_steps import *  # noqa: F401, F403

scenarios("llm_providers.feature")
