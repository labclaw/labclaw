"""BDD step definitions for L2 Governance.

Spec: docs/specs/cross-foundations.md
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, parsers, then, when

from labclaw.core.governance import (
    AuditLog,
    GovernanceDecision,
    GovernanceEngine,
    SafetyRule,
)

# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    "a governance engine with default role permissions",
    target_fixture="gov_engine",
)
def governance_default() -> GovernanceEngine:
    return GovernanceEngine()


@given(
    parsers.parse('a governance engine with a deny_if rule for "{action}"'),
    target_fixture="gov_engine",
)
def governance_with_deny_rule(action: str) -> GovernanceEngine:
    engine = GovernanceEngine()
    rule = SafetyRule(
        name=f"block_{action}",
        description=f"Action '{action}' is blocked by safety rule",
        check="deny_if",
        condition={"action": action},
    )
    engine.register_rule(rule)
    return engine


@given(
    "a governance engine with audit logging to a file",
    target_fixture="gov_engine_with_file",
)
def governance_with_file(tmp_path: Path) -> tuple[GovernanceEngine, Path]:
    audit_path = tmp_path / "audit.jsonl"
    engine = GovernanceEngine(audit_path=audit_path)
    return engine, audit_path


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('the PI requests to "{action}" an action'),
    target_fixture="gov_decision",
)
def pi_requests(gov_engine: GovernanceEngine, action: str) -> GovernanceDecision:
    return gov_engine.check(
        action=action, actor="dr_smith", role="pi",
    )


@when(
    parsers.parse('an undergraduate requests to "{action}" an action'),
    target_fixture="gov_decision",
)
def undergrad_requests(gov_engine: GovernanceEngine, action: str) -> GovernanceDecision:
    return gov_engine.check(
        action=action, actor="student_a", role="undergraduate",
    )


@when(
    parsers.parse('any user requests "{action}"'),
    target_fixture="gov_decision",
)
def any_user_requests(gov_engine: GovernanceEngine, action: str) -> GovernanceDecision:
    return gov_engine.check(
        action=action, actor="some_user", role="pi",
    )


@when(
    "3 actions are checked",
    target_fixture="gov_decisions_3",
)
def three_actions_checked(
    gov_engine_with_file: tuple[GovernanceEngine, Path],
) -> list[GovernanceDecision]:
    engine, _ = gov_engine_with_file
    decisions: list[GovernanceDecision] = []
    for i in range(3):
        d = engine.check(
            action=f"action_{i}", actor=f"actor_{i}", role="pi",
        )
        decisions.append(d)
    return decisions


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("the decision should be allowed")
def check_allowed(gov_decision: GovernanceDecision) -> None:
    assert gov_decision.allowed is True, (
        f"Expected allowed=True, got reason={gov_decision.reason!r}"
    )


@then("the decision should be denied")
def check_denied(gov_decision: GovernanceDecision) -> None:
    assert gov_decision.allowed is False, (
        f"Expected allowed=False, got allowed={gov_decision.allowed}"
    )


@then("the reason should mention lacking permission")
def check_reason_lacking(gov_decision: GovernanceDecision) -> None:
    reason_lower = gov_decision.reason.lower()
    has_permission = (
        "lacks permission" in reason_lower
        or "permission" in reason_lower
    )
    assert has_permission, (
        f"Expected reason to mention permission, got {gov_decision.reason!r}"
    )


@then("the audit log should record the denial")
def check_audit_denial(gov_engine: GovernanceEngine) -> None:
    entries = gov_engine.audit_log.query()
    assert len(entries) >= 1, "Expected at least 1 audit entry"
    denied = [e for e in entries if not e.decision.allowed]
    assert len(denied) >= 1, "Expected at least 1 denied entry in audit log"


@then(parsers.parse("the audit log should contain {count:d} entries"))
def check_audit_count(
    gov_engine_with_file: tuple[GovernanceEngine, Path], count: int,
) -> None:
    engine, _ = gov_engine_with_file
    entries = engine.audit_log.query()
    assert len(entries) == count, (
        f"Expected {count} audit entries, got {len(entries)}"
    )


@then("the file should be readable after reload")
def check_file_readable(
    gov_engine_with_file: tuple[GovernanceEngine, Path],
) -> None:
    _, audit_path = gov_engine_with_file
    assert audit_path.exists(), f"Audit file not found: {audit_path}"

    # Reload and verify
    reloaded = AuditLog(audit_path)
    reloaded.load()
    entries = reloaded.query()
    assert len(entries) >= 1, "Expected entries after reload"
