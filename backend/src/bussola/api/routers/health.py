"""Public liveness endpoint (no auth, no DB). Used by run-stack.sh readiness
and scripts/smoke-full-stack.sh to know when the backend accepts requests."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok")
