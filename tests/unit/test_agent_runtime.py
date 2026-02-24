"""Tests for src/labclaw/agents/runtime.py — AgentRuntime, message parsing, tool dispatch."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from labclaw.agents.runtime import AgentRuntime, Message
from labclaw.agents.tools import AgentTool, ToolResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(name: str = "my_tool", result: Any = "ok") -> AgentTool:
    """Create a simple AgentTool that returns a fixed result."""

    async def fn(**kwargs: Any) -> ToolResult:
        return ToolResult(success=True, data=result)

    return AgentTool(
        name=name,
        description=f"Test tool {name}",
        fn=fn,
        parameters_schema={"arg": {"type": "string"}},
    )


def _make_llm(*responses: str) -> MagicMock:
    """Create a mock LLM provider returning fixed responses in sequence."""
    mock = MagicMock()
    mock.complete = AsyncMock(side_effect=list(responses))
    return mock


# ---------------------------------------------------------------------------
# AgentRuntime creation
# ---------------------------------------------------------------------------


class TestAgentRuntimeCreation:
    def test_creation_without_tools(self) -> None:
        llm = _make_llm()
        rt = AgentRuntime(llm_provider=llm)
        assert rt.tools == {}
        assert rt.message_history == []

    def test_creation_with_tools(self) -> None:
        llm = _make_llm()
        t1 = _make_tool("t1")
        t2 = _make_tool("t2")
        rt = AgentRuntime(llm_provider=llm, tools=[t1, t2])
        assert "t1" in rt.tools
        assert "t2" in rt.tools


# ---------------------------------------------------------------------------
# register_tool
# ---------------------------------------------------------------------------


class TestRegisterTool:
    def test_adds_tool(self) -> None:
        llm = _make_llm()
        rt = AgentRuntime(llm_provider=llm)
        tool = _make_tool("new_tool")
        rt.register_tool(tool)
        assert "new_tool" in rt.tools


# ---------------------------------------------------------------------------
# Properties return copies
# ---------------------------------------------------------------------------


class TestProperties:
    def test_tools_returns_copy(self) -> None:
        llm = _make_llm()
        rt = AgentRuntime(llm_provider=llm, tools=[_make_tool("a")])
        copy = rt.tools
        copy["injected"] = "bad"
        assert "injected" not in rt.tools

    def test_message_history_returns_copy(self) -> None:
        llm = _make_llm()
        rt = AgentRuntime(llm_provider=llm)
        history = rt.message_history
        history.append({"role": "user", "content": "injected"})
        assert len(rt.message_history) == 0


# ---------------------------------------------------------------------------
# chat() — plain text response
# ---------------------------------------------------------------------------


class TestChatPlainText:
    @pytest.mark.asyncio
    async def test_plain_text_response(self) -> None:
        llm = _make_llm("Hello, world!")
        rt = AgentRuntime(llm_provider=llm)
        response = await rt.chat("Hi")
        assert response == "Hello, world!"
        assert len(rt.message_history) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_history_recorded(self) -> None:
        llm = _make_llm("response")
        rt = AgentRuntime(llm_provider=llm)
        await rt.chat("question")
        assert rt.message_history[0]["role"] == "user"
        assert rt.message_history[0]["content"] == "question"
        assert rt.message_history[1]["role"] == "assistant"
        assert rt.message_history[1]["content"] == "response"


# ---------------------------------------------------------------------------
# chat() — tool call then plain text
# ---------------------------------------------------------------------------


class TestChatWithToolCall:
    @pytest.mark.asyncio
    async def test_tool_call_then_plain_text(self) -> None:
        tool_call_json = json.dumps({"tool": "my_tool", "arguments": {"arg": "val"}})
        llm = _make_llm(tool_call_json, "Final answer")
        rt = AgentRuntime(llm_provider=llm, tools=[_make_tool("my_tool")])
        response = await rt.chat("Run the tool")
        assert response == "Final answer"
        # History: user, assistant(tool_call), tool_result, assistant(final)
        assert len(rt.message_history) == 4
        assert rt.message_history[2]["role"] == "tool"
        assert rt.message_history[2]["tool_name"] == "my_tool"


# ---------------------------------------------------------------------------
# chat() — max turns reached
# ---------------------------------------------------------------------------


class TestChatMaxTurns:
    @pytest.mark.asyncio
    async def test_max_turns_reached(self) -> None:
        # Always respond with a tool call, never plain text
        tool_call_json = json.dumps({"tool": "my_tool", "arguments": {}})
        responses = [tool_call_json] * 15  # more than max_turns=10
        llm = _make_llm(*responses)
        rt = AgentRuntime(llm_provider=llm, tools=[_make_tool("my_tool")])
        response = await rt.chat("Go")
        assert "maximum number of steps" in response.lower()


# ---------------------------------------------------------------------------
# _parse_tool_calls
# ---------------------------------------------------------------------------


class TestParseToolCalls:
    def _rt(self) -> AgentRuntime:
        return AgentRuntime(llm_provider=_make_llm())

    def test_valid_json(self) -> None:
        rt = self._rt()
        text = json.dumps({"tool": "foo", "arguments": {"x": 1}})
        calls = rt._parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0] == ("foo", {"x": 1})

    def test_embedded_json_flat(self) -> None:
        """Embedded JSON without nested braces is found by the regex fallback."""
        rt = self._rt()
        text = 'Let me call the tool: {"tool": "bar", "arg": "val"} and here is more text.'
        calls = rt._parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0][0] == "bar"

    def test_embedded_json_nested_not_matched(self) -> None:
        """Nested braces in arguments aren't matched by the simple regex fallback."""
        rt = self._rt()
        text = 'Text: {"tool": "bar", "arguments": {"y": 2}} end.'
        calls = rt._parse_tool_calls(text)
        # The simple regex [^{}]* can't match nested braces, so no match from fallback.
        # But the whole string isn't valid JSON either (has surrounding text).
        assert calls == []

    def test_no_tool_calls(self) -> None:
        rt = self._rt()
        calls = rt._parse_tool_calls("Just plain text, no JSON here.")
        assert calls == []

    def test_malformed_json(self) -> None:
        rt = self._rt()
        calls = rt._parse_tool_calls('{"tool": "foo", broken}')
        assert calls == []

    def test_json_without_tool_key(self) -> None:
        rt = self._rt()
        calls = rt._parse_tool_calls('{"action": "foo"}')
        assert calls == []

    def test_no_arguments_key(self) -> None:
        rt = self._rt()
        text = json.dumps({"tool": "baz"})
        calls = rt._parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0] == ("baz", {})


# ---------------------------------------------------------------------------
# _execute_tool
# ---------------------------------------------------------------------------


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_known_tool(self) -> None:
        rt = AgentRuntime(llm_provider=_make_llm(), tools=[_make_tool("t1")])
        result = await rt._execute_tool("t1", {})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_unknown_tool(self) -> None:
        rt = AgentRuntime(llm_provider=_make_llm())
        result = await rt._execute_tool("nonexistent", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]
        assert "available" in result


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_includes_tool_descriptions(self) -> None:
        tool = _make_tool("search", "results")
        rt = AgentRuntime(llm_provider=_make_llm(), tools=[tool])
        prompt = rt._build_prompt()
        assert "search" in prompt
        assert "Available tools" in prompt

    def test_includes_history(self) -> None:
        rt = AgentRuntime(llm_provider=_make_llm())
        rt._message_history.append({"role": "user", "content": "hello"})
        rt._message_history.append({"role": "assistant", "content": "hi"})
        prompt = rt._build_prompt()
        assert "User: hello" in prompt
        assert "Assistant: hi" in prompt

    def test_includes_tool_results_in_history(self) -> None:
        rt = AgentRuntime(llm_provider=_make_llm())
        rt._message_history.append(
            {"role": "tool", "tool_name": "search", "content": "result data"}
        )
        prompt = rt._build_prompt()
        assert "Tool result (search)" in prompt

    def test_empty_prompt_no_tools_no_history(self) -> None:
        rt = AgentRuntime(llm_provider=_make_llm())
        prompt = rt._build_prompt()
        assert prompt == ""


# ---------------------------------------------------------------------------
# clear_history
# ---------------------------------------------------------------------------


class TestClearHistory:
    def test_clears_history(self) -> None:
        rt = AgentRuntime(llm_provider=_make_llm())
        rt._message_history.append({"role": "user", "content": "hi"})
        rt.clear_history()
        assert rt.message_history == []


# ---------------------------------------------------------------------------
# Events emitted
# ---------------------------------------------------------------------------


class TestEvents:
    @pytest.mark.asyncio
    async def test_message_received_event(self) -> None:
        from labclaw.core.events import event_registry

        received: list[Any] = []
        event_registry.subscribe(
            "persona.agent.message_received", lambda e: received.append(e)
        )

        llm = _make_llm("response")
        rt = AgentRuntime(llm_provider=llm)
        await rt.chat("test message")
        assert len(received) >= 1

    @pytest.mark.asyncio
    async def test_response_generated_event(self) -> None:
        from labclaw.core.events import event_registry

        generated: list[Any] = []
        event_registry.subscribe(
            "persona.agent.response_generated", lambda e: generated.append(e)
        )

        llm = _make_llm("response")
        rt = AgentRuntime(llm_provider=llm)
        await rt.chat("test")
        assert len(generated) >= 1

    @pytest.mark.asyncio
    async def test_tool_called_event(self) -> None:
        from labclaw.core.events import event_registry

        called: list[Any] = []
        event_registry.subscribe(
            "persona.agent.tool_called", lambda e: called.append(e)
        )

        tool_json = json.dumps({"tool": "my_tool", "arguments": {}})
        llm = _make_llm(tool_json, "done")
        rt = AgentRuntime(llm_provider=llm, tools=[_make_tool("my_tool")])
        await rt.chat("call tool")
        assert len(called) >= 1


# ---------------------------------------------------------------------------
# Message model
# ---------------------------------------------------------------------------


class TestMessage:
    def test_message_creation(self) -> None:
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_name is None
        assert msg.tool_call_id is None
        assert msg.timestamp is not None
