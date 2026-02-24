"""Agent runtime — manages agent lifecycle, tool dispatch, and message history.

Agents are LLM-backed assistants that can call registered tools to interact
with the LabClaw system (memory, mining, devices, optimization, etc.).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_AGENT_EVENTS = [
    "persona.agent.message_received",
    "persona.agent.tool_called",
    "persona.agent.response_generated",
]

for _evt in _AGENT_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Message(BaseModel):
    """A single message in the agent conversation."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_name: str | None = None
    tool_call_id: str | None = None
    timestamp: datetime = Field(default_factory=_now)


class AgentConfig(BaseModel):
    """Configuration for an agent instance."""

    agent_id: str = Field(default_factory=_uuid)
    name: str
    system_prompt: str
    max_turns: int = 10
    max_history: int = 50


# ---------------------------------------------------------------------------
# AgentRuntime
# ---------------------------------------------------------------------------


class AgentRuntime:
    """Manages agent execution with tools and memory.

    Usage::

        runtime = AgentRuntime(llm_provider=provider)
        runtime.register_tool(my_tool)
        response = await runtime.chat("What patterns have we found?", system_prompt="...")
    """

    def __init__(
        self,
        llm_provider: Any,
        tools: list[Any] | None = None,
    ) -> None:
        from labclaw.agents.tools import AgentTool

        self._llm = llm_provider
        self._tools: dict[str, AgentTool] = {}
        self._message_history: list[dict[str, Any]] = []

        for tool in tools or []:
            self.register_tool(tool)

    @property
    def tools(self) -> dict[str, Any]:
        return dict(self._tools)

    @property
    def message_history(self) -> list[dict[str, Any]]:
        return list(self._message_history)

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tool(self, tool: Any) -> None:
        """Register an AgentTool instance."""
        self._tools[tool.name] = tool

    # ------------------------------------------------------------------
    # Core chat loop
    # ------------------------------------------------------------------

    async def chat(self, user_message: str, system_prompt: str = "") -> str:
        """Process a user message through the agent.

        Uses LLM with tool calling in a ReAct-style loop:
        1. Send message + tool descriptions to LLM
        2. If LLM wants to call a tool, execute it, feed result back
        3. Repeat until LLM gives final text response or max_turns reached
        """
        event_registry.emit(
            "persona.agent.message_received",
            payload={"message": user_message[:200]},
        )

        self._message_history.append({"role": "user", "content": user_message})

        max_turns = 10
        for _turn in range(max_turns):
            prompt = self._build_prompt()

            llm_response = await self._llm.complete(
                prompt,
                system=system_prompt,
                temperature=0.3,
                max_tokens=2048,
            )

            # Check if response contains tool calls
            tool_calls = self._parse_tool_calls(llm_response)

            if not tool_calls:
                # Plain text response — done
                self._message_history.append(
                    {"role": "assistant", "content": llm_response}
                )
                event_registry.emit(
                    "persona.agent.response_generated",
                    payload={"response_length": len(llm_response)},
                )
                return llm_response

            # Execute tool calls and feed results back
            self._message_history.append(
                {"role": "assistant", "content": llm_response}
            )
            for tc_name, tc_args in tool_calls:
                result = await self._execute_tool(tc_name, tc_args)
                self._message_history.append(
                    {
                        "role": "tool",
                        "tool_name": tc_name,
                        "content": json.dumps(result, default=str),
                    }
                )

        return "I've reached the maximum number of steps for this request."

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._message_history.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self) -> str:
        """Build a prompt string from tool specs and message history."""
        parts: list[str] = []

        # Include tool descriptions
        if self._tools:
            tool_block = "Available tools:\n"
            for tool in self._tools.values():
                params_str = ", ".join(
                    f"{k}: {v.get('type', 'any')}"
                    for k, v in tool.parameters_schema.items()
                )
                tool_block += f"- {tool.name}({params_str}): {tool.description}\n"
            tool_block += (
                "\nTo call a tool, respond with a JSON block: "
                '{"tool": "<name>", "arguments": {...}}\n'
            )
            parts.append(tool_block)

        # Add conversation history
        for msg in self._message_history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            elif role == "tool":
                parts.append(f"Tool result ({msg.get('tool_name', '?')}): {content}")

        return "\n\n".join(parts)

    def _parse_tool_calls(self, response: str) -> list[tuple[str, dict[str, Any]]]:
        """Extract tool calls from LLM response.

        Returns list of (tool_name, arguments) tuples.
        """
        calls: list[tuple[str, dict[str, Any]]] = []
        try:
            data = json.loads(response.strip())
            if isinstance(data, dict) and "tool" in data:
                calls.append((data["tool"], data.get("arguments", {})))
                return calls
        except (json.JSONDecodeError, KeyError):
            pass

        # Try finding JSON blocks within response
        for match in re.finditer(r'\{[^{}]*"tool"\s*:\s*"[^"]+?"[^{}]*\}', response):
            try:
                data = json.loads(match.group())
                if "tool" in data:
                    calls.append((data["tool"], data.get("arguments", {})))
            except (json.JSONDecodeError, KeyError):
                continue

        return calls

    async def _execute_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool call, returning the result as a dict."""
        event_registry.emit(
            "persona.agent.tool_called",
            payload={"tool_name": tool_name},
        )

        tool = self._tools.get(tool_name)
        if tool is None:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available": list(self._tools),
            }

        result = await tool.execute(**arguments)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if isinstance(result, dict):
            return result
        return {"success": True, "data": str(result)}
