"""Event registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from labclaw.api.deps import get_event_registry

router = APIRouter()


@router.get("/")
def list_events(
    registry=Depends(get_event_registry),  # noqa: ANN001
) -> list[str]:
    return registry.list_events()
