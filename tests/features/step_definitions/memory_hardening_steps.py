"""Step definitions for Memory Layer Hardening BDD scenarios."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pytest_bdd import given, parsers, then, when

from labclaw.memory.markdown import MarkdownDoc, TierABackend

# ---------------------------------------------------------------------------
# entity_id validation
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I attempt to create a SOUL for entity "{entity_id}"'),
    target_fixture="validation_error",
)
def _when_attempt_create_soul(tier_a: TierABackend, entity_id: str) -> Exception | None:
    try:
        doc = MarkdownDoc(
            path=tier_a.root / "tmp" / "SOUL.md",
            frontmatter={"name": "test", "type": "entity"},
            content="# test",
        )
        tier_a.write_soul(entity_id, doc)
        return None
    except ValueError as exc:
        return exc


@when(
    "I attempt to create a SOUL with an empty entity id",
    target_fixture="validation_error",
)
def _when_attempt_create_soul_empty(tier_a: TierABackend) -> Exception | None:
    try:
        doc = MarkdownDoc(
            path=tier_a.root / "tmp" / "SOUL.md",
            frontmatter={"name": "test", "type": "entity"},
            content="# test",
        )
        tier_a.write_soul("", doc)
        return None
    except ValueError as exc:
        return exc


@then("no error is raised")
def _then_no_error_raised(validation_error: Exception | None) -> None:
    assert validation_error is None


@then(parsers.parse('a ValueError is raised with "{message}"'))
def _then_valueerror_with_message(validation_error: Exception | None, message: str) -> None:
    assert validation_error is not None, "Expected a ValueError but none was raised"
    assert isinstance(validation_error, ValueError), (
        f"Expected ValueError, got {type(validation_error)}"
    )
    assert message in str(validation_error), (
        f"Expected {message!r} in error message, got: {validation_error!r}"
    )


# ---------------------------------------------------------------------------
# SessionMemoryManager.close()
# ---------------------------------------------------------------------------


@given("a session memory manager with no Tier B backend", target_fixture="session_mgr_ctx")
def _given_session_mgr_no_tier_b(tmp_path: Path) -> dict[str, Any]:
    from labclaw.memory.session_memory import SessionMemoryManager

    mgr = SessionMemoryManager(memory_root=tmp_path, db_path=None)
    return {"mgr": mgr, "tier_b_mock": None}


@given("a session memory manager with a mock Tier B backend", target_fixture="session_mgr_ctx")
def _given_session_mgr_with_tier_b(tmp_path: Path) -> dict[str, Any]:
    from labclaw.memory.session_memory import SessionMemoryManager

    mgr = SessionMemoryManager(memory_root=tmp_path, db_path=None)
    mock_tier_b = MagicMock()
    mock_tier_b.close = AsyncMock()
    mgr._tier_b = mock_tier_b
    return {"mgr": mgr, "tier_b_mock": mock_tier_b}


@when("I close the session memory manager")
def _when_close_session_mgr(session_mgr_ctx: dict[str, Any]) -> None:
    asyncio.run(session_mgr_ctx["mgr"].close())


@then("close completes without error")
def _then_close_no_error(session_mgr_ctx: dict[str, Any]) -> None:
    # close() completed without exception; verify the manager is still accessible
    mgr = session_mgr_ctx["mgr"]
    assert mgr is not None, "Session memory manager must remain accessible after close"


@then("the Tier B backend close method was called")
def _then_tier_b_close_called(session_mgr_ctx: dict[str, Any]) -> None:
    mock_tier_b = session_mgr_ctx["tier_b_mock"]
    assert mock_tier_b is not None
    mock_tier_b.close.assert_called_once()
