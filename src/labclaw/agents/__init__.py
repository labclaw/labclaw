"""Agent system — runtime, tools, and built-in agents.

Re-exports the public API for the agents package.
"""

from __future__ import annotations

from labclaw.agents.prompts.experiment_designer import EXPERIMENT_DESIGNER_SYSTEM
from labclaw.agents.prompts.lab_assistant import LAB_ASSISTANT_SYSTEM
from labclaw.agents.runtime import AgentConfig, AgentRuntime, Message
from labclaw.agents.tools import AgentTool, ToolResult, build_builtin_tools

__all__ = [
    "EXPERIMENT_DESIGNER_SYSTEM",
    "LAB_ASSISTANT_SYSTEM",
    "AgentConfig",
    "AgentRuntime",
    "AgentTool",
    "Message",
    "ToolResult",
    "build_builtin_tools",
    "create_experiment_designer",
    "create_lab_assistant",
]


def create_lab_assistant(
    llm: object,
    *,
    memory_root: object | None = None,
    device_registry: object | None = None,
    evolution_engine: object | None = None,
) -> AgentRuntime:
    """Factory: create a Lab Assistant agent with all built-in tools."""
    tools = build_builtin_tools(
        memory_root=memory_root,
        device_registry=device_registry,
        evolution_engine=evolution_engine,
    )
    return AgentRuntime(llm_provider=llm, tools=tools)


def create_experiment_designer(
    llm: object,
    *,
    memory_root: object | None = None,
    device_registry: object | None = None,
    evolution_engine: object | None = None,
) -> AgentRuntime:
    """Factory: create an Experiment Designer agent with all built-in tools."""
    tools = build_builtin_tools(
        memory_root=memory_root,
        device_registry=device_registry,
        evolution_engine=evolution_engine,
    )
    return AgentRuntime(llm_provider=llm, tools=tools)
