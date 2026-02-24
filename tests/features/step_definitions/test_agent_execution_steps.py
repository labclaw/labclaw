"""BDD step definitions for L5 Agent Execution.

Tests the AgentRuntime with mock LLM providers.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.agents.runtime import AgentRuntime
from labclaw.agents.tools import AgentTool, ToolResult

# ---------------------------------------------------------------------------
# Mock LLM provider
# ---------------------------------------------------------------------------


class MockLLMProvider:
    """Returns a configurable response from complete()."""

    def __init__(self, response: str = "Here are the patterns found so far.") -> None:
        self._response = response

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        return self._response


class ToolCallLLMProvider:
    """Returns a tool call JSON on first call, then text on second."""

    def __init__(self, tool_name: str) -> None:
        self._tool_name = tool_name
        self._call_count = 0

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        self._call_count += 1
        if self._call_count == 1:
            return json.dumps({"tool": self._tool_name, "arguments": {}})
        return "Tool call completed."


# ---------------------------------------------------------------------------
# Mock tools
# ---------------------------------------------------------------------------


async def _mock_tool_fn(**kwargs: Any) -> ToolResult:
    return ToolResult(success=True, data={"mock": True})


def _make_mock_tools(n: int) -> list[AgentTool]:
    tools: list[AgentTool] = []
    for i in range(n):
        tools.append(
            AgentTool(
                name=f"mock_tool_{i}",
                description=f"Mock tool number {i}",
                fn=_mock_tool_fn,
                parameters_schema={},
            )
        )
    return tools


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    "an agent runtime with a mock LLM provider",
    target_fixture="agent_runtime",
)
def agent_with_mock_llm() -> AgentRuntime:
    return AgentRuntime(llm_provider=MockLLMProvider())


@given(
    "3 built-in tools registered",
    target_fixture="agent_runtime",
)
def register_three_tools(agent_runtime: AgentRuntime) -> AgentRuntime:
    for tool in _make_mock_tools(3):
        agent_runtime.register_tool(tool)
    return agent_runtime


@given(
    "an agent runtime with no tools registered",
    target_fixture="agent_runtime_no_tools",
)
def agent_with_no_tools() -> AgentRuntime:
    return AgentRuntime(llm_provider=ToolCallLLMProvider("nonexistent_tool"))


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('the user asks "{question}"'),
    target_fixture="agent_response",
)
def user_asks(agent_runtime: AgentRuntime, question: str) -> str:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(agent_runtime.chat(question))
    finally:
        loop.close()


@when(
    parsers.parse('the LLM returns a tool call for "{tool_name}"'),
    target_fixture="tool_call_result",
)
def llm_returns_tool_call(
    agent_runtime_no_tools: AgentRuntime, tool_name: str,
) -> dict[str, Any]:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(agent_runtime_no_tools.chat("test question"))
    finally:
        loop.close()
    # The tool result is recorded in message history
    history = agent_runtime_no_tools.message_history
    tool_msgs = [m for m in history if m.get("role") == "tool"]
    if tool_msgs:
        return json.loads(tool_msgs[0]["content"])
    return {"success": False, "error": "No tool result found"}


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("the agent should return a text response")
def check_text_response(agent_response: str) -> None:
    assert isinstance(agent_response, str), "Expected string response"
    assert len(agent_response) > 0, "Expected non-empty response"


@then("the message history should contain the exchange")
def check_message_history(agent_runtime: AgentRuntime) -> None:
    history = agent_runtime.message_history
    roles = [m["role"] for m in history]
    assert "user" in roles, f"Expected 'user' in history roles, got {roles}"
    assert "assistant" in roles, f"Expected 'assistant' in history roles, got {roles}"


@then("the tool result should indicate an error")
def check_tool_error(tool_call_result: dict[str, Any]) -> None:
    assert tool_call_result.get("success") is False, (
        f"Expected success=False, got {tool_call_result}"
    )
    has_error = (
        "error" in tool_call_result
        or "Unknown tool" in str(tool_call_result.get("error", ""))
    )
    assert has_error, (
        f"Expected error message, got {tool_call_result}"
    )


@then("available tools should be listed")
def check_available_tools_listed(tool_call_result: dict[str, Any]) -> None:
    # When no tools registered, the available list should be empty
    available = tool_call_result.get("available", None)
    assert available is not None, f"Expected 'available' key in result, got {tool_call_result}"
    assert isinstance(available, list), f"Expected list, got {type(available)}"
