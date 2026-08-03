"""Profile persistence. Applies the outbound PII filter on save (§7.3)."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from bussola.data.pseudonym import generate_pseudonym
from bussola.guardrails.pii import PiiRedactor, sanitize_profile
from bussola.profile.enums import Availability, OperationalNoteCategory
from bussola.profile.models import WorkProfile


def create_empty_profile(conn: psycopg.Connection) -> str:
    """Create an empty work profile under a fresh pseudonym; return the pseudonym.

    Redactor-free (the operator provisioning path must not load NLP models).
    No commit here — the caller owns the transaction.
    """
    pseudonym = generate_pseudonym()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles.work_profile (pseudonym_id, profile) VALUES (%s, %s) "
            "ON CONFLICT (pseudonym_id) DO NOTHING",
            (pseudonym, WorkProfile(pseudonym_id=pseudonym).model_dump_json()),
        )
    return pseudonym


def is_contentless(profile: WorkProfile) -> bool:
    """True for a just-provisioned empty profile (exactly `create_empty_profile`'s
    output: no skills/languages/experiences/desired_training/operational_notes,
    no digital_literacy, and no aspiration with any field set).

    Excluded from `ProfileRepository.search`/`list_all` and from the quality
    metrics (§7.2/§7.3/§11): an empty profile has nothing to match on or search
    for, and surfacing it would let an operator set-diff the profile list (or
    the counts) around a provisioning call to see a new empty profile appear and
    self-map matricola -> pseudonym, bypassing the supervisor-only
    de-anonymization. It would also dilute `average_completeness` with a run of
    zeros that reflect provisioning, not interview quality.
    """
    aspiration_empty = profile.aspiration is None or (
        not profile.aspiration.fields_of_interest
        and profile.aspiration.availability is None
        and not profile.aspiration.constraints
    )
    return (
        not profile.skills
        and not profile.languages
        and not profile.experiences
        and aspiration_empty
        and not profile.desired_training
        and not profile.operational_notes
        and profile.digital_literacy is None
    )


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
        """Create an empty profile under a fresh pseudonym; return the pseudonym.

        Delegates to the module-level `create_empty_profile` (DRY) but keeps
        this method's existing commit-internally behavior.

        TEST-ONLY (re-identification, §5/§6): its sole caller is
        `Interview.start()`, which is itself test-only. In production a first
        interview is provisioned by an operator (`create_empty_profile` +
        `IdentityService.link` in one transaction) and started via
        `Interview.start_on(pseudonym)`. Do NOT call this (or `start()`) from
        any endpoint or production path: it would mint a pseudonym with no
        entry in the segregated identity register — an unlinkable profile that
        the supervisor could never resolve back to a person.
        """
        pseudonym = create_empty_profile(self._conn)
        self._conn.commit()
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
        profiles = [WorkProfile.model_validate(r[0]) for r in rows]
        return [p for p in profiles if not is_contentless(p)]

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
        profiles = [WorkProfile.model_validate(r[0]) for r in rows]
        return [p for p in profiles if not is_contentless(p)]

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
