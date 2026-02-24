"""Tests for labclaw.core.governance — governance engine, audit log, safety rules."""

from __future__ import annotations

from pathlib import Path

from labclaw.core.events import event_registry
from labclaw.core.governance import (
    AuditEntry,
    AuditLog,
    GovernanceDecision,
    GovernanceEngine,
    SafetyRule,
)
from labclaw.core.schemas import SafetyLevel

# ---------------------------------------------------------------------------
# GovernanceEngine.check()
# ---------------------------------------------------------------------------


class TestGovernanceCheck:
    def test_pi_allowed_for_any_action(self):
        engine = GovernanceEngine()
        decision = engine.check(action="execute", actor="alice", role="pi")
        assert decision.allowed is True

    def test_pi_allowed_for_custom_action(self):
        engine = GovernanceEngine()
        decision = engine.check(action="delete_all", actor="alice", role="pi")
        assert decision.allowed is True

    def test_undergraduate_denied_execute(self):
        engine = GovernanceEngine()
        decision = engine.check(action="execute", actor="bob", role="undergraduate")
        assert decision.allowed is False
        assert "lacks permission" in decision.reason

    def test_graduate_allowed_execute(self):
        engine = GovernanceEngine()
        decision = engine.check(action="execute", actor="carol", role="graduate")
        assert decision.allowed is True

    def test_unknown_role_denied(self):
        engine = GovernanceEngine()
        decision = engine.check(action="read", actor="nobody", role="visitor")
        assert decision.allowed is False
        assert "lacks permission" in decision.reason

    def test_graduate_denied_approve(self):
        engine = GovernanceEngine()
        decision = engine.check(action="approve", actor="carol", role="graduate")
        assert decision.allowed is False

    def test_postdoc_allowed_approve(self):
        engine = GovernanceEngine()
        decision = engine.check(action="approve", actor="dave", role="postdoc")
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# Safety rules
# ---------------------------------------------------------------------------


class TestSafetyRules:
    def test_register_and_deny_rule(self):
        engine = GovernanceEngine()
        rule = SafetyRule(
            name="no_laser",
            description="Laser operations blocked after hours",
            check="deny_if",
            condition={"action": "execute", "device": "laser"},
        )
        engine.register_rule(rule)
        decision = engine.check(
            action="execute", actor="alice", role="pi",
            context={"device": "laser"},
        )
        assert decision.allowed is False
        assert decision.safety_level == SafetyLevel.BLOCKED

    def test_require_approval_rule(self):
        engine = GovernanceEngine()
        rule = SafetyRule(
            name="high_voltage_approval",
            description="High voltage requires PI approval",
            check="require_approval_if",
            condition={"action": "execute", "voltage": "high"},
        )
        engine.register_rule(rule)
        decision = engine.check(
            action="execute", actor="carol", role="graduate",
            context={"voltage": "high"},
        )
        assert decision.allowed is True
        assert decision.safety_level == SafetyLevel.REQUIRES_APPROVAL
        assert "pi" in decision.required_approvals

    def test_rule_not_matching(self):
        engine = GovernanceEngine()
        rule = SafetyRule(
            name="no_laser",
            description="Block laser",
            check="deny_if",
            condition={"action": "execute", "device": "laser"},
        )
        engine.register_rule(rule)
        # Different device, rule should not match
        decision = engine.check(
            action="execute", actor="alice", role="pi",
            context={"device": "microscope"},
        )
        assert decision.allowed is True
        assert decision.safety_level == SafetyLevel.SAFE


class TestRuleMatches:
    def test_matching_action_and_context(self):
        engine = GovernanceEngine()
        rule = SafetyRule(
            name="test", description="test",
            check="deny_if",
            condition={"action": "write", "target": "config"},
        )
        assert engine._rule_matches(rule, "write", {"target": "config"}) is True

    def test_non_matching_action(self):
        engine = GovernanceEngine()
        rule = SafetyRule(
            name="test", description="test",
            check="deny_if",
            condition={"action": "write"},
        )
        assert engine._rule_matches(rule, "read", {}) is False

    def test_non_matching_context(self):
        engine = GovernanceEngine()
        rule = SafetyRule(
            name="test", description="test",
            check="deny_if",
            condition={"action": "write", "target": "config"},
        )
        assert engine._rule_matches(rule, "write", {"target": "data"}) is False

    def test_empty_condition_matches_all(self):
        engine = GovernanceEngine()
        rule = SafetyRule(
            name="test", description="test",
            check="deny_if",
            condition={},
        )
        assert engine._rule_matches(rule, "anything", {"key": "val"}) is True


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class TestAuditLog:
    def _make_entry(self, actor: str = "alice", action: str = "read") -> AuditEntry:
        return AuditEntry(
            actor=actor,
            action=action,
            target="test",
            decision=GovernanceDecision(allowed=True),
        )

    def test_append_and_query(self):
        log = AuditLog()
        log.append(self._make_entry(actor="alice", action="read"))
        log.append(self._make_entry(actor="bob", action="write"))
        log.append(self._make_entry(actor="alice", action="write"))

        assert len(log.query()) == 3

    def test_query_by_actor(self):
        log = AuditLog()
        log.append(self._make_entry(actor="alice", action="read"))
        log.append(self._make_entry(actor="bob", action="write"))
        results = log.query(actor="alice")
        assert len(results) == 1
        assert results[0].actor == "alice"

    def test_query_by_action(self):
        log = AuditLog()
        log.append(self._make_entry(actor="alice", action="read"))
        log.append(self._make_entry(actor="bob", action="read"))
        log.append(self._make_entry(actor="carol", action="write"))
        results = log.query(action="read")
        assert len(results) == 2

    def test_query_with_limit(self):
        log = AuditLog()
        for i in range(10):
            log.append(self._make_entry(actor=f"user{i}"))
        results = log.query(limit=3)
        assert len(results) == 3

    def test_persistence_write_and_load(self, tmp_path: Path):
        log_path = tmp_path / "audit.jsonl"
        log = AuditLog(path=log_path)
        log.append(self._make_entry(actor="alice", action="read"))
        log.append(self._make_entry(actor="bob", action="write"))

        # Verify file was written
        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2

        # Load into a new log
        log2 = AuditLog(path=log_path)
        log2.load()
        results = log2.query()
        assert len(results) == 2
        assert results[0].actor == "alice"
        assert results[1].actor == "bob"


# ---------------------------------------------------------------------------
# Model creation
# ---------------------------------------------------------------------------


class TestModels:
    def test_audit_entry_creation(self):
        entry = AuditEntry(
            actor="alice",
            action="calibrate",
            target="scope_1",
            decision=GovernanceDecision(allowed=True, reason="PI role"),
        )
        assert entry.actor == "alice"
        assert entry.action == "calibrate"
        assert entry.decision.allowed is True
        assert entry.timestamp is not None

    def test_governance_decision(self):
        gd = GovernanceDecision(
            allowed=False,
            reason="No permission",
            safety_level=SafetyLevel.BLOCKED,
            required_approvals=["pi"],
        )
        assert gd.allowed is False
        assert gd.safety_level == SafetyLevel.BLOCKED
        assert gd.required_approvals == ["pi"]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class TestGovernanceEvents:
    def test_action_approved_event(self):
        events: list[str] = []

        def handler(event):
            events.append(str(event.event_name))

        event_registry.subscribe("infra.governance.action_approved", handler)
        try:
            engine = GovernanceEngine()
            engine.check(action="read", actor="alice", role="pi")
            assert "infra.governance.action_approved" in events
        finally:
            event_registry._handlers.pop("infra.governance.action_approved", None)

    def test_action_denied_event(self):
        events: list[str] = []

        def handler(event):
            events.append(str(event.event_name))

        event_registry.subscribe("infra.governance.action_denied", handler)
        try:
            engine = GovernanceEngine()
            engine.check(action="execute", actor="bob", role="undergraduate")
            assert "infra.governance.action_denied" in events
        finally:
            event_registry._handlers.pop("infra.governance.action_denied", None)

    def test_audit_logged_event(self):
        events: list[str] = []

        def handler(event):
            events.append(str(event.event_name))

        event_registry.subscribe("infra.governance.audit_logged", handler)
        try:
            engine = GovernanceEngine()
            engine.check(action="read", actor="alice", role="pi")
            assert "infra.governance.audit_logged" in events
        finally:
            event_registry._handlers.pop("infra.governance.audit_logged", None)
