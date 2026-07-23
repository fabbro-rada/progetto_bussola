"""Profile persistence. Applies the outbound PII filter on save (§7.3)."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from bussola.data.pseudonym import generate_pseudonym
from bussola.guardrails.pii import PiiRedactor, sanitize_profile
from bussola.profile.enums import Availability, OperationalNoteCategory
from bussola.profile.models import WorkProfile


class ProfileRepository:
    """Reads and writes work profiles.

    `save` redacts PII before persisting and may raise
    ``pydantic.ValidationError`` if redaction would violate the schema
    (fail-closed) — callers must be prepared to handle it.
    """

    def __init__(
        self, conn: psycopg.Connection, redactor: PiiRedactor, language: str = "it"
    ) -> None:
        self._conn = conn
        self._redactor = redactor
        self._language = language

    def create_new(self) -> str:
        """Create an empty profile under a fresh pseudonym; return the pseudonym."""
        pseudonym = generate_pseudonym()
        self._upsert(WorkProfile(pseudonym_id=pseudonym))
        return pseudonym

    def save(self, profile: WorkProfile) -> WorkProfile:
        """Redact PII (§7.3), persist, and return the sanitized profile."""
        clean = sanitize_profile(profile, self._redactor, self._language)
        self._upsert(clean)
        return clean

    def get(self, pseudonym_id: str) -> WorkProfile | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT profile FROM profiles.work_profile WHERE pseudonym_id = %s",
                (pseudonym_id,),
            )
            row = cur.fetchone()
        return WorkProfile.model_validate(row[0]) if row is not None else None

    def list_all(self) -> list[WorkProfile]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT profile FROM profiles.work_profile ORDER BY pseudonym_id")
            rows = cur.fetchall()
        return [WorkProfile.model_validate(r[0]) for r in rows]

    def search(
        self,
        *,
        availability: Availability | None = None,
        language: str | None = None,
        note: OperationalNoteCategory | None = None,
        skill_query: str | None = None,
    ) -> list[WorkProfile]:
        clauses: list[str] = []
        params: list[object] = []
        if availability is not None:
            clauses.append("profile->'aspiration'->>'availability' = %s")
            params.append(availability.value)
        if language is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(profile->'languages') AS l "
                "WHERE lower(l->>'language') = lower(%s))"
            )
            params.append(language)
        if note is not None:
            clauses.append("profile->'operational_notes' ? %s")
            params.append(note.value)
        if skill_query is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(profile->'skills') AS s "
                "WHERE s->>'name' ILIKE %s)"
            )
            params.append(f"%{skill_query}%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT profile FROM profiles.work_profile" + where + " ORDER BY pseudonym_id",
                params,
            )
            rows = cur.fetchall()
        return [WorkProfile.model_validate(r[0]) for r in rows]

    def _upsert(self, profile: WorkProfile) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO profiles.work_profile (pseudonym_id, profile) "
                "VALUES (%s, %s) "
                "ON CONFLICT (pseudonym_id) DO UPDATE "
                "SET profile = EXCLUDED.profile, updated_at = now()",
                (profile.pseudonym_id, Jsonb(profile.model_dump(mode="json"))),
            )
        self._conn.commit()
