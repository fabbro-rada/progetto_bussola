"""Job request persistence (matching.job_request). No internal commit."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from bussola.matching.models import JobRequest, JobRequestCreate, RequiredLanguage
from bussola.profile.enums import Availability

_COLS = (
    "id, title, sector, description, required_skills, required_languages, "
    "required_availability, involves_night_shifts, training_prerequisites, created_by"
)


def _to_job_request(row: tuple[Any, ...]) -> JobRequest:
    return JobRequest(
        id=row[0],
        title=row[1],
        sector=row[2],
        description=row[3],
        required_skills=list(row[4]),
        required_languages=[RequiredLanguage.model_validate(item) for item in row[5]],
        required_availability=Availability(row[6]) if row[6] is not None else None,
        involves_night_shifts=row[7],
        training_prerequisites=list(row[8]),
        created_by=row[9],
    )


class JobRequestRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, req: JobRequestCreate, *, created_by: str) -> JobRequest:
        languages = [lang.model_dump(mode="json") for lang in req.required_languages]
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO matching.job_request "
                "(title, sector, description, required_skills, required_languages, "
                "required_availability, involves_night_shifts, training_prerequisites, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING " + _COLS,
                (
                    req.title,
                    req.sector,
                    req.description,
                    req.required_skills,
                    Jsonb(languages),
                    req.required_availability.value if req.required_availability else None,
                    req.involves_night_shifts,
                    req.training_prerequisites,
                    created_by,
                ),
            )
            row = cur.fetchone()
        assert row is not None
        return _to_job_request(row)

    def get(self, job_id: int) -> JobRequest | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT " + _COLS + " FROM matching.job_request WHERE id = %s", (job_id,))
            row = cur.fetchone()
        return _to_job_request(row) if row is not None else None

    def list_all(self) -> list[JobRequest]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT " + _COLS + " FROM matching.job_request ORDER BY id")
            rows = cur.fetchall()
        return [_to_job_request(r) for r in rows]
