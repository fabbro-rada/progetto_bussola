"""Matching orchestration: deterministic hard-constraint gate first, then the
grounded semantic judgment on the survivors, then transparent scoring + gaps.
Computed on-demand (not persisted); each run is audited."""

from __future__ import annotations

from typing import Callable

import psycopg

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.llm.client import LlmClient
from bussola.matching import gaps as gaps_mod
from bussola.matching import hard_constraints, scoring, semantic
from bussola.matching.errors import JobRequestNotFound
from bussola.matching.models import MatchResult
from bussola.matching.requests import JobRequestRepository

AuditFn = Callable[..., None]


class MatchingService:
    def __init__(
        self,
        conn: psycopg.Connection,
        client: LlmClient,
        redactor: PiiRedactor,
        *,
        language: str = "it",
        audit: AuditFn | None = None,
    ) -> None:
        self._conn = conn
        self._client = client
        self._profiles = ProfileRepository(conn, redactor, language)
        self._jobs = JobRequestRepository(conn)
        self._language = language
        self._audit = audit

    def match(self, job_id: int, *, actor: str) -> list[MatchResult]:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobRequestNotFound(str(job_id))
        results: list[MatchResult] = []
        for profile in self._profiles.list_all():
            outcome = hard_constraints.evaluate(profile, job)
            if not outcome.compatible:
                continue  # excluded by a hard constraint (privacy-minimal: not surfaced)
            verdicts = semantic.judge_requirements(self._client, profile, job, self._language)
            results.append(
                MatchResult(
                    pseudonym_id=profile.pseudonym_id,
                    score=scoring.score(verdicts),
                    requirements=verdicts,
                    constraint=outcome,
                    gaps=gaps_mod.compute(verdicts, profile),
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        if self._audit is not None:
            self._audit(
                action="matching_run",
                actor=actor,
                details={"job_request_id": str(job_id), "candidates": str(len(results))},
            )
            self._conn.commit()
        return results
