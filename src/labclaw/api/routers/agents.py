"""Agent endpoints — chat with Lab Assistant and Experiment Designer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from labclaw.agents import (
    EXPERIMENT_DESIGNER_SYSTEM,
    LAB_ASSISTANT_SYSTEM,
    AgentRuntime,
    build_builtin_tools,
)
from labclaw.api.deps import (
    get_device_registry,
    get_evolution_engine,
    get_llm_provider,
    get_tier_a_backend,
)
from labclaw.llm.provider import LLMProvider

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(max_length=10_000)


class ChatResponse(BaseModel):
    response: str
    agent: str


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_llm(llm: LLMProvider | None) -> LLMProvider:
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="LLM provider not configured. Set the API key environment variable.",
        )
    return llm


def _build_runtime(llm: LLMProvider) -> AgentRuntime:
    """Build an AgentRuntime with all built-in tools wired to singletons."""
    backend = get_tier_a_backend()
    tools = build_builtin_tools(
        memory_root=backend.root,
        device_registry=get_device_registry(),
        evolution_engine=get_evolution_engine(),
    )
    return AgentRuntime(llm_provider=llm, tools=tools)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def lab_assistant_chat(
    body: ChatRequest,
    llm: LLMProvider | None = Depends(get_llm_provider),
) -> ChatResponse:
    """Send a message to the Lab Assistant agent."""
    provider = _require_llm(llm)
    runtime = _build_runtime(provider)
    response = await runtime.chat(body.message, system_prompt=LAB_ASSISTANT_SYSTEM)
    return ChatResponse(response=response, agent="lab-assistant")


@router.post("/designer/chat", response_model=ChatResponse)
async def experiment_designer_chat(
    body: ChatRequest,
    llm: LLMProvider | None = Depends(get_llm_provider),
) -> ChatResponse:
    """Send a message to the Experiment Designer agent."""
    provider = _require_llm(llm)
    runtime = _build_runtime(provider)
    response = await runtime.chat(body.message, system_prompt=EXPERIMENT_DESIGNER_SYSTEM)
    return ChatResponse(response=response, agent="experiment-designer")


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools() -> list[ToolInfo]:
    """List all available agent tools."""
    tools = build_builtin_tools()
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            parameters=t.parameters_schema,
        )
        for t in tools
    ]
