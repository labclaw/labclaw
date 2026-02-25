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


class SystemPromptCaptureLLMProvider:
    """Captures the system prompt passed to complete()."""

    def __init__(self) -> None:
        self.captured_system: str = ""

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        self.captured_system = system
        return "Response with custom system prompt."


# ---------------------------------------------------------------------------
# Mock tools
# ---------------------------------------------------------------------------


async def _mock_tool_fn(**kwargs: Any) -> ToolResult:
    return ToolResult(success=True, data={"mock": True})


async def _echo_tool_fn(**kwargs: Any) -> ToolResult:
    return ToolResult(success=True, data={"echo": "tool executed"})


async def _failing_tool_fn(**kwargs: Any) -> ToolResult:
    raise RuntimeError("Simulated tool failure")


async def _data_tool_fn(**kwargs: Any) -> ToolResult:
    return ToolResult(
        success=True,
        data={
            "records": [{"id": 1, "value": 42.0}, {"id": 2, "value": 99.5}],
            "total": 2,
            "metadata": {"source": "mock"},
        },
    )


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


def _run_async(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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


@given(
    parsers.parse('an agent runtime that calls "{tool_name}" once then responds'),
    target_fixture="agent_runtime",
)
def agent_that_calls_tool(tool_name: str) -> AgentRuntime:
    return AgentRuntime(llm_provider=ToolCallLLMProvider(tool_name))


@given(
    parsers.parse('the "{tool_name}" is registered'),
    target_fixture="agent_runtime",
)
def register_echo_tool(agent_runtime: AgentRuntime, tool_name: str) -> AgentRuntime:
    tool = AgentTool(
        name=tool_name,
        description=f"The {tool_name} tool",
        fn=_echo_tool_fn,
        parameters_schema={},
    )
    agent_runtime.register_tool(tool)
    return agent_runtime


@given(
    parsers.parse('the "{tool_name}" is registered and raises an exception'),
    target_fixture="agent_runtime",
)
def register_failing_tool(agent_runtime: AgentRuntime, tool_name: str) -> AgentRuntime:
    tool = AgentTool(
        name=tool_name,
        description=f"The failing {tool_name} tool",
        fn=_failing_tool_fn,
        parameters_schema={},
    )
    agent_runtime.register_tool(tool)
    return agent_runtime


@given(
    parsers.parse('the "{tool_name}" is registered and returns structured data'),
    target_fixture="agent_runtime",
)
def register_data_tool(agent_runtime: AgentRuntime, tool_name: str) -> AgentRuntime:
    tool = AgentTool(
        name=tool_name,
        description=f"The {tool_name} tool that returns structured data",
        fn=_data_tool_fn,
        parameters_schema={},
    )
    agent_runtime.register_tool(tool)
    return agent_runtime


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('the user asks "{question}"'),
    target_fixture="agent_response",
)
def user_asks(agent_runtime: AgentRuntime, question: str) -> str:
    return _run_async(agent_runtime.chat(question))


@when("the user sends an empty message", target_fixture="agent_response")
def user_sends_empty_message(agent_runtime: AgentRuntime) -> str:
    return _run_async(agent_runtime.chat(""))


@when(
    parsers.parse('the user asks "{question}" with system prompt "{system}"'),
    target_fixture="agent_response",
)
def user_asks_with_system(agent_runtime: AgentRuntime, question: str, system: str) -> str:
    return _run_async(agent_runtime.chat(question, system_prompt=system))


@when(
    parsers.parse("the LLM returns a tool call for \"{tool_name}\""),
    target_fixture="tool_call_result",
)
def llm_returns_tool_call(
    agent_runtime_no_tools: AgentRuntime, tool_name: str,
) -> dict[str, Any]:
    _run_async(agent_runtime_no_tools.chat("test question"))
    # The tool result is recorded in message history
    history = agent_runtime_no_tools.message_history
    tool_msgs = [m for m in history if m.get("role") == "tool"]
    if tool_msgs:
        return json.loads(tool_msgs[0]["content"])
    return {"success": False, "error": "No tool result found"}


@when(
    parsers.parse("I register {n:d} tools on the agent"),
    target_fixture="agent_runtime",
)
def register_n_tools(agent_runtime: AgentRuntime, n: int) -> AgentRuntime:
    for tool in _make_mock_tools(n):
        agent_runtime.register_tool(tool)
    return agent_runtime


@when(
    parsers.parse('I register a tool named "{name}" with description "{description}"'),
    target_fixture="agent_runtime",
)
def register_named_tool(agent_runtime: AgentRuntime, name: str, description: str) -> AgentRuntime:
    tool = AgentTool(
        name=name,
        description=description,
        fn=_mock_tool_fn,
        parameters_schema={},
    )
    agent_runtime.register_tool(tool)
    return agent_runtime


@when("I clear the agent history", target_fixture="agent_runtime")
def clear_agent_history(agent_runtime: AgentRuntime) -> AgentRuntime:
    agent_runtime.clear_history()
    return agent_runtime


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("the agent should return a text response")
def check_text_response(agent_response: str) -> None:
    assert isinstance(agent_response, str), "Expected string response"


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


@then(parsers.parse("the agent has {n:d} tools registered"))
def check_agent_tool_count(agent_runtime: AgentRuntime, n: int) -> None:
    assert len(agent_runtime.tools) == n, (
        f"Expected {n} tools, got {len(agent_runtime.tools)}"
    )


@then("the message history contains a tool result entry")
def check_history_has_tool_result(agent_runtime: AgentRuntime) -> None:
    history = agent_runtime.message_history
    tool_msgs = [m for m in history if m.get("role") == "tool"]
    assert tool_msgs, f"Expected at least one tool result in history, got {history}"


@then("the tool result in history shows failure")
def check_tool_failure_in_history(agent_runtime: AgentRuntime) -> None:
    history = agent_runtime.message_history
    tool_msgs = [m for m in history if m.get("role") == "tool"]
    assert tool_msgs, "Expected a tool result entry in history"
    result = json.loads(tool_msgs[0]["content"])
    assert result.get("success") is False, f"Expected success=False in tool result, got {result}"


@then(parsers.parse('the message history contains role "{role}"'))
def check_history_contains_role(agent_runtime: AgentRuntime, role: str) -> None:
    history = agent_runtime.message_history
    roles = [m["role"] for m in history]
    assert role in roles, f"Expected role {role!r} in history, got {roles}"


@then("the tool result in history contains structured data")
def check_tool_result_structured(agent_runtime: AgentRuntime) -> None:
    history = agent_runtime.message_history
    tool_msgs = [m for m in history if m.get("role") == "tool"]
    assert tool_msgs, "Expected tool result in history"
    result = json.loads(tool_msgs[0]["content"])
    assert result.get("success") is True
    data = result.get("data", {})
    assert "records" in data, f"Expected 'records' in structured data, got {data}"


@then(parsers.parse('the "{tool_name}" description is "{description}"'))
def check_tool_description(agent_runtime: AgentRuntime, tool_name: str, description: str) -> None:
    tools = agent_runtime.tools
    assert tool_name in tools, f"Tool {tool_name!r} not registered"
    assert tools[tool_name].description == description, (
        f"Expected description {description!r}, got {tools[tool_name].description!r}"
    )


@then("the message history is empty")
def check_message_history_empty(agent_runtime: AgentRuntime) -> None:
    history = agent_runtime.message_history
    assert len(history) == 0, f"Expected empty history, got {history}"
