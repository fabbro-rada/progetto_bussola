"""Quality metrics: aggregate + anonymous (§7.2). No per-person data (§2)."""

from __future__ import annotations

from typing import Any

import psycopg
from pydantic import BaseModel, ConfigDict

from bussola.data.profiles import is_contentless
from bussola.profile.models import WorkProfile

# The 4 list-valued key sections; `aspiration` is the 5th (an object).
_ARRAY_SECTIONS = ("languages", "skills", "experiences", "desired_training")
_TOTAL_SECTIONS = len(_ARRAY_SECTIONS) + 1  # the 4 arrays + aspiration


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_profiles: int
    completed_profiles: int
    average_completeness: float
    total_job_requests: int
    matching_runs: int


def _profile_completeness(profile: dict[str, Any]) -> float:
    populated = sum(1 for key in _ARRAY_SECTIONS if profile.get(key))
    asp = profile.get("aspiration")
    if isinstance(asp, dict) and (
        asp.get("fields_of_interest") or asp.get("availability") or asp.get("constraints")
    ):
        populated += 1
    return populated / _TOTAL_SECTIONS


def compute_metrics(conn: psycopg.Connection) -> Metrics:
    with conn.cursor() as cur:
        cur.execute("SELECT profile FROM profiles.work_profile")
        # Exclude just-provisioned empty profiles (§7.2): they are not completed
        # interviews, would dilute average_completeness with zeros, and inflate
        # total_profiles into a matricola<->pseudonym correlation channel
        # (consistent with ProfileRepository.search/list_all, which also drop
        # them). See bussola.data.profiles.is_contentless.
        profiles: list[dict[str, Any]] = [
            row[0]
            for row in cur.fetchall()
            if not is_contentless(WorkProfile.model_validate(row[0]))
        ]
        cur.execute("SELECT COUNT(*) FROM matching.job_request")
        jr_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM audit.audit_log WHERE action = %s", ("matching_run",))
        mr_row = cur.fetchone()
    total = len(profiles)
    scores = [_profile_completeness(p) for p in profiles]
    return Metrics(
        total_profiles=total,
        completed_profiles=sum(1 for s in scores if s >= 1.0),
        average_completeness=(sum(scores) / total if total else 0.0),
        total_job_requests=int(jr_row[0]) if jr_row else 0,
        matching_runs=int(mr_row[0]) if mr_row else 0,
    )
