"""Root test configuration — shared fixtures for all test suites.

Disables all security controls by default so that unit and BDD tests can
exercise API behavior without needing real tokens, governance setup, or
rate-limiting.  Individual security tests override these values explicitly
via monkeypatch before calling reset_all().
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_security_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable auth, governance, and rate-limiting for every test by default.

    Security-focused tests that need these enabled set the env vars explicitly
    (via monkeypatch) and call deps.reset_all() themselves, which is the
    existing pattern in tests/unit/test_api_security.py and the BDD step
    definitions in tests/features/step_definitions/api_security_steps.py.
    """
    monkeypatch.setenv("LABCLAW_API_AUTH_REQUIRED", "0")
    monkeypatch.setenv("LABCLAW_GOVERNANCE_ENFORCE", "0")
    monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "0")
