"""Auth DTOs. `Operator` is the safe public view (no password hash). The
internal `OperatorRecord` carries the fields login needs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from bussola.auth.rbac import Role

_STRICT = ConfigDict(extra="forbid")


class Operator(BaseModel):
    model_config = _STRICT
    id: int
    username: str
    display_name: str
    role: Role
    is_active: bool
    must_change_password: bool


@dataclass(frozen=True)
class OperatorRecord:
    """Internal login view (never leaves the auth layer)."""

    id: int
    username: str
    display_name: str
    role: Role
    is_active: bool
    must_change_password: bool
    password_hash: str
    failed_attempts: int
    locked_until: datetime | None


class LoginRequest(BaseModel):
    model_config = _STRICT
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    model_config = _STRICT
    old_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class CreateOperatorRequest(BaseModel):
    model_config = _STRICT
    username: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    role: Role
