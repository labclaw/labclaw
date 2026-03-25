"""Core Pydantic types shared across all brain modules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class BrainResult(BaseModel):
    """Return type for all brain operations."""

    success: bool
    data: Any = None
    error: str | None = None


class ToolInfo(BaseModel):
    """Metadata for a registered tool."""

    name: str
    description: str
    skill: str
    category: str = ""
    parameters: dict[str, Any] = {}


class HealthStatus(BaseModel):
    """Cloud Brain health report."""

    status: str
    skills: dict[str, bool]
    tool_count: int
    version: str
