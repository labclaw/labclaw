"""BDD test runner for LiteLLM multi-model routing (L2 Infra)."""

from __future__ import annotations

from pytest_bdd import scenarios

from tests.features.step_definitions.litellm_steps import *  # noqa: F401, F403

scenarios("litellm_routing.feature")
