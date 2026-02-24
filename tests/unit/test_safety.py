"""Safety-focused tests — governance blocking, input validation, path traversal,
evolution rollback, plugin safety rules, audit log integrity, device approval."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all, set_memory_root
from labclaw.core.governance import GovernanceEngine, SafetyRule
from labclaw.core.schemas import EvolutionStage, EvolutionTarget, SafetyLevel
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.schemas import EvolutionCandidate, FitnessScore
from labclaw.memory.markdown import TierABackend

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def governance() -> GovernanceEngine:
    return GovernanceEngine()


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    set_memory_root(tmp_path / "lab")
    try:
        yield TestClient(app)
    finally:
        reset_all()


@pytest.fixture()
def tier_a(tmp_path: Path) -> TierABackend:
    return TierABackend(root=tmp_path / "lab")


# ---------------------------------------------------------------------------
# 1. Governance blocks unauthorized hardware commands
# ---------------------------------------------------------------------------


class TestGovernanceBlocksUnauthorized:
    def test_undergraduate_cannot_execute(self, governance: GovernanceEngine) -> None:
        decision = governance.check(
            action="execute", actor="student", role="undergraduate",
        )
        assert decision.allowed is False
        assert decision.safety_level == SafetyLevel.BLOCKED

    def test_digital_intern_cannot_write(self, governance: GovernanceEngine) -> None:
        decision = governance.check(
            action="write", actor="bot", role="digital_intern",
        )
        assert decision.allowed is False

    def test_unknown_role_blocked(self, governance: GovernanceEngine) -> None:
        decision = governance.check(
            action="read", actor="unknown", role="random_role",
        )
        assert decision.allowed is False

    def test_deny_rule_blocks_even_pi(self, governance: GovernanceEngine) -> None:
        rule = SafetyRule(
            name="no_laser_night",
            description="Laser blocked after hours",
            check="deny_if",
            condition={"action": "execute", "device": "laser"},
        )
        governance.register_rule(rule)
        decision = governance.check(
            action="execute", actor="pi_user", role="pi",
            context={"device": "laser"},
        )
        assert decision.allowed is False
        assert decision.safety_level == SafetyLevel.BLOCKED


# ---------------------------------------------------------------------------
# 2. API input validation — no injection via entity_id
# ---------------------------------------------------------------------------


class TestAPIInputValidation:
    def test_entity_id_rejects_path_traversal(self, client: TestClient) -> None:
        resp = client.get("/api/memory/../../../etc/passwd/soul")
        assert resp.status_code in (400, 404, 422)

    def test_entity_id_rejects_dot_dot(self, client: TestClient) -> None:
        resp = client.get("/api/memory/..%2F..%2Fetc/soul")
        assert resp.status_code in (400, 404, 422)

    def test_entity_id_rejects_special_chars(self, client: TestClient) -> None:
        resp = client.get("/api/memory/foo;rm -rf/soul")
        assert resp.status_code in (400, 404, 422)

    def test_entity_id_rejects_null_byte(self, client: TestClient) -> None:
        resp = client.get("/api/memory/foo%00bar/soul")
        assert resp.status_code in (400, 404, 422)

    def test_entity_id_accepts_valid(self, client: TestClient) -> None:
        # Valid entity_id format but no file — should be 404, not 400
        resp = client.get("/api/memory/valid-entity.123/soul")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Path traversal protection in Tier A memory
# ---------------------------------------------------------------------------


class TestPathTraversalProtection:
    def test_entity_dir_rejects_traversal(self, tier_a: TierABackend) -> None:
        with pytest.raises(ValueError, match="entity_id must match"):
            tier_a._entity_dir("../../../etc/passwd")

    def test_entity_dir_rejects_slash(self, tier_a: TierABackend) -> None:
        with pytest.raises(ValueError, match="entity_id must match"):
            tier_a._entity_dir("foo/bar")

    def test_entity_dir_rejects_empty(self, tier_a: TierABackend) -> None:
        with pytest.raises(ValueError, match="entity_id must be non-empty"):
            tier_a._entity_dir("")

    def test_entity_dir_rejects_dot_only(self, tier_a: TierABackend) -> None:
        with pytest.raises(ValueError, match="entity_id must match"):
            tier_a._entity_dir(".")

    def test_entity_dir_rejects_dotdot(self, tier_a: TierABackend) -> None:
        with pytest.raises(ValueError, match="entity_id must match"):
            tier_a._entity_dir("..")

    def test_entity_dir_accepts_valid(self, tier_a: TierABackend) -> None:
        result = tier_a._entity_dir("valid-entity.123")
        assert result.name == "valid-entity.123"

    def test_entity_id_regex_pattern(self) -> None:
        pattern = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
        # These should NOT match (fullmatch)
        assert pattern.fullmatch("../etc") is None
        assert pattern.fullmatch("") is None
        assert pattern.fullmatch(".hidden") is None
        assert pattern.fullmatch("-starts-with-dash") is None
        assert pattern.fullmatch("a" * 200) is None  # too long
        # These should match
        assert pattern.fullmatch("device01") is not None
        assert pattern.fullmatch("scope-1.v2") is not None


# ---------------------------------------------------------------------------
# 4. Evolution engine rollback on regression
# ---------------------------------------------------------------------------


class TestEvolutionRollback:
    def test_auto_rollback_on_metric_regression(self) -> None:
        engine = EvolutionEngine()
        candidate = EvolutionCandidate(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            description="Test candidate",
            config_diff={"threshold": 0.5},
            proposed_by="test",
        )
        baseline = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={"accuracy": 0.9, "coverage": 0.8},
            data_points=100,
        )
        cycle = engine.start_cycle(candidate, baseline)
        assert cycle.stage == EvolutionStage.BACKTEST

        # Simulate major regression
        bad_fitness = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={"accuracy": 0.3, "coverage": 0.2},
            data_points=100,
        )
        result = engine.advance_stage(cycle.cycle_id, bad_fitness)
        assert result.stage == EvolutionStage.ROLLED_BACK
        assert result.rollback_reason is not None

    def test_no_rollback_on_improvement(self) -> None:
        engine = EvolutionEngine()
        candidate = EvolutionCandidate(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            description="Good candidate",
            config_diff={"threshold": 0.4},
            proposed_by="test",
        )
        baseline = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={"accuracy": 0.5},
            data_points=100,
        )
        cycle = engine.start_cycle(candidate, baseline)

        better_fitness = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={"accuracy": 0.7},
            data_points=100,
        )
        result = engine.advance_stage(cycle.cycle_id, better_fitness)
        assert result.stage == EvolutionStage.SHADOW  # Advanced, not rolled back


# ---------------------------------------------------------------------------
# 5. Plugin safety rules are enforced
# ---------------------------------------------------------------------------


class TestPluginSafetyRules:
    def test_plugin_deny_rule_enforced(self, governance: GovernanceEngine) -> None:
        rule = SafetyRule(
            name="plugin_high_temp",
            description="Block heating above 80C",
            check="deny_if",
            condition={"action": "execute", "temperature_c": "above_80"},
            source="neuro-plugin",
        )
        governance.register_rule(rule)
        decision = governance.check(
            action="execute", actor="pi", role="pi",
            context={"temperature_c": "above_80"},
        )
        assert decision.allowed is False
        assert decision.safety_level == SafetyLevel.BLOCKED

    def test_plugin_approval_rule_enforced(self, governance: GovernanceEngine) -> None:
        rule = SafetyRule(
            name="plugin_chemical",
            description="Chemical dispensing requires PI approval",
            check="require_approval_if",
            condition={"action": "execute", "chemical": True},
            source="chem-plugin",
        )
        governance.register_rule(rule)
        decision = governance.check(
            action="execute", actor="grad_student", role="graduate",
            context={"chemical": True},
        )
        assert decision.allowed is True
        assert decision.safety_level == SafetyLevel.REQUIRES_APPROVAL
        assert "pi" in decision.required_approvals

    def test_multiple_rules_first_deny_wins(self, governance: GovernanceEngine) -> None:
        deny_rule = SafetyRule(
            name="deny_first",
            description="Deny this action",
            check="deny_if",
            condition={"action": "execute"},
        )
        approval_rule = SafetyRule(
            name="approve_second",
            description="Require approval",
            check="require_approval_if",
            condition={"action": "execute"},
        )
        governance.register_rule(deny_rule)
        governance.register_rule(approval_rule)
        decision = governance.check(
            action="execute", actor="alice", role="pi",
        )
        assert decision.allowed is False  # Deny rule fires first


# ---------------------------------------------------------------------------
# 6. Audit log is append-only (no deletion API)
# ---------------------------------------------------------------------------


class TestAuditLogIntegrity:
    def test_audit_log_has_no_delete_method(self) -> None:
        from labclaw.core.governance import AuditLog
        log = AuditLog()
        assert not hasattr(log, "delete")
        assert not hasattr(log, "remove")
        assert not hasattr(log, "clear")
        assert not hasattr(log, "truncate")

    def test_audit_entries_accumulate(self, governance: GovernanceEngine) -> None:
        governance.check(action="read", actor="alice", role="pi")
        governance.check(action="write", actor="bob", role="postdoc")
        governance.check(action="execute", actor="carol", role="undergraduate")

        entries = governance.audit_log.query()
        assert len(entries) == 3
        # Entries are in insertion order
        assert entries[0].actor == "alice"
        assert entries[1].actor == "bob"
        assert entries[2].actor == "carol"

    def test_audit_log_persistence_is_append_only(self, tmp_path: Path) -> None:
        from labclaw.core.governance import AuditEntry, AuditLog, GovernanceDecision

        log_path = tmp_path / "audit.jsonl"
        log = AuditLog(path=log_path)

        entry1 = AuditEntry(
            actor="alice", action="read", target="device1",
            decision=GovernanceDecision(allowed=True),
        )
        entry2 = AuditEntry(
            actor="bob", action="write", target="device2",
            decision=GovernanceDecision(allowed=False, reason="denied"),
        )
        log.append(entry1)
        log.append(entry2)

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2

        # Append more — file grows, doesn't reset
        entry3 = AuditEntry(
            actor="carol", action="execute", target="device3",
            decision=GovernanceDecision(allowed=True),
        )
        log.append(entry3)
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# 7. Device write commands require approval for safety levels
# ---------------------------------------------------------------------------


class TestDeviceWriteApproval:
    def test_write_action_requires_approval_blocked_without_role(
        self, governance: GovernanceEngine,
    ) -> None:
        rule = SafetyRule(
            name="high_voltage_approval",
            description="High voltage requires PI approval",
            check="require_approval_if",
            condition={"action": "write", "voltage": "high"},
        )
        governance.register_rule(rule)
        decision = governance.check(
            action="write", actor="student", role="graduate",
            context={"voltage": "high"},
        )
        assert decision.safety_level == SafetyLevel.REQUIRES_APPROVAL

    def test_calibrate_denied_for_undergraduate(
        self, governance: GovernanceEngine,
    ) -> None:
        decision = governance.check(
            action="calibrate", actor="student", role="undergraduate",
        )
        assert decision.allowed is False

    def test_calibrate_allowed_for_technician(
        self, governance: GovernanceEngine,
    ) -> None:
        decision = governance.check(
            action="calibrate", actor="tech", role="technician",
        )
        assert decision.allowed is True
