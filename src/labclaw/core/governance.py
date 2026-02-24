"""Governance engine — role-based permissions, safety rules, audit log.

Spec: docs/specs/cross-foundations.md
Design doc: section 8.2 (Two-Layer Safety)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.core.schemas import SafetyLevel

logger = logging.getLogger(__name__)

# Register events
_GOVERNANCE_EVENTS = [
    "infra.governance.action_checked",
    "infra.governance.action_approved",
    "infra.governance.action_denied",
    "infra.governance.audit_logged",
]
for _evt in _GOVERNANCE_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


class GovernanceDecision(BaseModel):
    """Result of a governance check."""

    allowed: bool
    reason: str = ""
    safety_level: SafetyLevel = SafetyLevel.SAFE
    required_approvals: list[str] = Field(default_factory=list)


class AuditEntry(BaseModel):
    """Immutable record of an action."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str
    action: str
    target: str
    decision: GovernanceDecision
    context: dict[str, Any] = Field(default_factory=dict)


class SafetyRule(BaseModel):
    """A registered safety rule."""

    name: str
    description: str
    check: str  # "deny_if", "require_approval_if", "warn_if"
    condition: dict[str, Any]  # Conditions that trigger this rule
    source: str = "core"  # Plugin that registered this rule


class AuditLog:
    """Append-only audit log backed by JSON Lines file."""

    def __init__(self, path: Path | None = None):
        self._path = path
        self._entries: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a") as f:
                f.write(entry.model_dump_json() + "\n")
        event_registry.emit(
            "infra.governance.audit_logged",
            payload={"actor": entry.actor, "action": entry.action},
        )

    def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        results = self._entries
        if actor:
            results = [e for e in results if e.actor == actor]
        if action:
            results = [e for e in results if e.action == action]
        return results[-limit:]

    def load(self) -> None:
        """Load entries from disk if file exists."""
        if self._path and self._path.exists():
            for line in self._path.read_text().strip().split("\n"):
                if line:
                    self._entries.append(AuditEntry.model_validate_json(line))


class GovernanceEngine:
    """Central governance: permissions, safety rules, audit."""

    def __init__(self, audit_path: Path | None = None):
        self._rules: list[SafetyRule] = []
        self._role_permissions: dict[str, set[str]] = {
            "pi": {"*"},  # PI can do anything
            "postdoc": {"read", "write", "execute", "approve"},
            "graduate": {"read", "write", "execute"},
            "undergraduate": {"read", "write"},
            "technician": {"read", "write", "calibrate"},
            "digital_intern": {"read"},
            "digital_analyst": {"read", "analyze"},
            "digital_specialist": {"read", "analyze", "propose"},
        }
        self._audit = AuditLog(audit_path)

    def register_rule(self, rule: SafetyRule) -> None:
        """Register a safety rule (e.g., from a domain plugin)."""
        self._rules.append(rule)

    def check(
        self,
        action: str,
        actor: str,
        role: str,
        context: dict[str, Any] | None = None,
    ) -> GovernanceDecision:
        """Check if an action is allowed."""
        context = context or {}

        # 1. Check role permissions
        allowed_actions = self._role_permissions.get(role, set())
        if "*" not in allowed_actions and action not in allowed_actions:
            decision = GovernanceDecision(
                allowed=False,
                reason=f"Role '{role}' lacks permission for action '{action}'",
                safety_level=SafetyLevel.BLOCKED,
            )
        else:
            # 2. Check safety rules
            decision = self._evaluate_rules(action, context)

        # 3. Audit
        self._audit.append(
            AuditEntry(
                actor=actor,
                action=action,
                target=context.get("target", ""),
                decision=decision,
                context=context,
            )
        )

        event_name = (
            "infra.governance.action_approved"
            if decision.allowed
            else "infra.governance.action_denied"
        )
        event_registry.emit(event_name, payload={"actor": actor, "action": action})

        return decision

    def _evaluate_rules(
        self, action: str, context: dict[str, Any]
    ) -> GovernanceDecision:
        """Evaluate registered safety rules."""
        for rule in self._rules:
            if self._rule_matches(rule, action, context):
                if rule.check == "deny_if":
                    return GovernanceDecision(
                        allowed=False,
                        reason=rule.description,
                        safety_level=SafetyLevel.BLOCKED,
                    )
                elif rule.check == "require_approval_if":
                    return GovernanceDecision(
                        allowed=True,
                        reason=rule.description,
                        safety_level=SafetyLevel.REQUIRES_APPROVAL,
                        required_approvals=["pi"],
                    )
        return GovernanceDecision(allowed=True, safety_level=SafetyLevel.SAFE)

    def _rule_matches(
        self, rule: SafetyRule, action: str, context: dict[str, Any]
    ) -> bool:
        """Check if a rule's conditions match the current action/context."""
        cond = rule.condition
        if "action" in cond and cond["action"] != action:
            return False
        for key, value in cond.items():
            if key == "action":
                continue
            if context.get(key) != value:
                return False
        return True

    @property
    def audit_log(self) -> AuditLog:
        return self._audit
