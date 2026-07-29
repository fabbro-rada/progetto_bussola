"""DTOs for the export-request workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bussola.profile.enums import Availability, OperationalNoteCategory

ExportStatus = Literal["pending", "approved", "denied"]


class ExportFilters(BaseModel):
    """Same profile filters as the consultation section (S13)."""

    model_config = ConfigDict(extra="forbid")

    availability: Availability | None = None
    language: str | None = Field(default=None, max_length=64)
    note: OperationalNoteCategory | None = None
    skill_query: str | None = Field(default=None, max_length=200)


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    requested_by: str
    filters: ExportFilters
    reason: str
    status: ExportStatus
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    created_at: datetime
    kind: str = "profiles"
