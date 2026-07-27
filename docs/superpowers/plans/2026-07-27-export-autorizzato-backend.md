# Export con autorizzazione — Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend del workflow di export con autorizzazione (§7.3): tabella `export.export_request`, `ExportService` a stati (richiesta → approvazione/rifiuto → download), endpoint `/exports` RBAC-gated, generazione JSON on-demand dei profili solo-lavoro, audit di ogni passo.

**Architecture:** Nuovo schema/tabella `export` (migrazione additiva `0006`). `ExportService` incapsula le transizioni di stato (guardate a DB) e l'audit atomico (pattern S5: `append_audit(commit=False)` + un solo commit). Il download **ri-esegue** `ProfileRepository.search(filtri)` (nessun payload memorizzato). Endpoint dietro RBAC: `EXPORT_DATA` (operatore, richiede/lista/scarica), nuovo `APPROVE_EXPORTS` (supervisore, coda/approva/nega). Il gate di download è server-side (solo `approved` + proprietaria).

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, psycopg3, PostgreSQL. Test: pytest (DB reale) + ruff + mypy (strict).

## Global Constraints

- **Solo `backend/`.** `operator-portal/` e `frontend/` NON si toccano. Nessuna nuova dipendenza. Migrazione **additiva** `0006` (non modificare le migrazioni esistenti).
- **TDD** (RED → GREEN), **solo dati sintetici**. Output test pristine.
- **Autorizzazione imposta dal server (§7.3):** il download restituisce dati **solo** se la richiesta è `status='approved'` **ed** è propria del chiamante; altrimenti 409 (non approvata) / 404 (non propria o inesistente). Non aggirabile.
- **Ruoli disgiunti:** richiedente = `Permission.EXPORT_DATA` (operatore, già esistente); approvatore = **nuovo** `Permission.APPROVE_EXPORTS` (solo supervisore). Un operatore ha un solo ruolo → **nessuna auto-approvazione**.
- **Payload = soli `WorkProfile` (§2/§5/§7.3):** il download produce `list[WorkProfile]` via `ProfileRepository(conn, PiiRedactor())` — nessun altro dato, nessuna PII, nessuna mappa pseudonimo↔persona. **Nessun payload memorizzato** (generazione on-demand).
- **Audit di ogni azione (§7.3):** `export_requested` / `export_approved` / `export_denied` / `export_downloaded`, atomici con la transizione; i `details` non contengono PII (nomi-filtro + conteggio, come `profiles_searched`).
- **Transizioni concorrenti guardate:** `UPDATE … WHERE id=%s AND status='pending'`; `rowcount==0` → distinguere 404 vs 409.
- **`reason` obbligatorio, 1..500 char.** `status` vincolato da `CHECK ('pending','approved','denied')`. Niente DELETE per `bussola_app`.
- **DB attivo** per i test: `docker compose up -d db` (i test DB si auto-skippano se Postgres è irraggiungibile — deve essere su).
- **Gate** (da `backend/`, `.venv` attiva): `pytest -q && ruff check . && mypy src`.

---

### Task 1: Migrazione `0006` + permesso `APPROVE_EXPORTS` + isolamento test

**Files:**
- Create: `backend/src/bussola/data/migrations/0006_exports.sql`
- Modify: `backend/src/bussola/auth/rbac.py` (nuovo permesso + mapping supervisore)
- Modify: `backend/tests/conftest.py` (truncate `export.export_request` nel fixture `db`)
- Create: `backend/tests/export/__init__.py`
- Create: `backend/tests/export/test_setup.py`

**Interfaces:**
- Consumes: fixtures `db`/`owner_conn`/`app_conn`/`auditor_conn` (`tests/conftest.py`); `apply_migrations` (auto-applica i `.sql` numerati); `Role`/`Permission`/`has_permission` (`bussola.auth.rbac`).
- Produces (Task 2/3): schema+tabella `export.export_request` (colonne: `id` bigint PK, `requested_by` text, `filters` jsonb, `reason` text, `status` text CHECK, `decided_by` text NULL, `decided_at` timestamptz NULL, `decision_reason` text NULL, `created_at` timestamptz); `Permission.APPROVE_EXPORTS` (solo supervisore).

- [ ] **Step 1: Avvia il DB di test**

Run: `cd backend && docker compose up -d db` (idempotente).

- [ ] **Step 2: Scrivi i test di setup (`tests/export/test_setup.py`)**

Crea `backend/tests/export/__init__.py` (vuoto) e:
```python
import psycopg
import pytest

from bussola.auth.rbac import Permission, Role, has_permission

pytestmark = pytest.mark.usefixtures("db")


def test_export_schema_and_table_exist(owner_conn: psycopg.Connection):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT to_regclass('export.export_request')")
        assert cur.fetchone()[0] is not None


def test_status_check_rejects_unknown_value(app_conn: psycopg.Connection):
    with app_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO export.export_request (requested_by, reason, status) "
                "VALUES ('op1', 'why', 'bogus')"
            )
    app_conn.rollback()


def test_app_can_write_but_not_delete_and_auditor_has_no_access(
    app_conn: psycopg.Connection, auditor_conn: psycopg.Connection
):
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO export.export_request (requested_by, reason) VALUES ('op1', 'why')"
        )
    app_conn.commit()
    with app_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM export.export_request")
    app_conn.rollback()
    with auditor_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT count(*) FROM export.export_request")
    auditor_conn.rollback()


def test_supervisor_approves_exports_operator_does_not():
    assert has_permission(Role.SUPERVISOR, Permission.APPROVE_EXPORTS) is True
    assert has_permission(Role.OPERATOR, Permission.APPROVE_EXPORTS) is False
    # the requester permission stays with the operator
    assert has_permission(Role.OPERATOR, Permission.EXPORT_DATA) is True
    assert has_permission(Role.SUPERVISOR, Permission.EXPORT_DATA) is False
```

- [ ] **Step 3: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/export/test_setup.py`
Expected: FAIL (schema/tabella inesistenti; `APPROVE_EXPORTS` non esiste). Nota: se `db` fallisce perché la tabella non esiste ancora nel truncate, procedi allo Step 4-5 (il fixture guarda con `to_regclass`).

- [ ] **Step 4: Crea la migrazione (`0006_exports.sql`)**

```sql
-- Export requests (authorized data egress, §7.3). Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS export AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA export TO bussola_app;
-- auditor gets NO access to the export schema (absence of grant).

CREATE TABLE export.export_request (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    requested_by    text NOT NULL,
    filters         jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason          text NOT NULL,
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'denied')),
    decided_by      text,
    decided_at      timestamptz,
    decision_reason text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- No DELETE: export requests remain traceable (§7.3).
GRANT SELECT, INSERT, UPDATE ON export.export_request TO bussola_app;
```

- [ ] **Step 5: Aggiungi il permesso (`auth/rbac.py`)**

Nell'enum `Permission`, dopo `EXPORT_DATA = "export_data"`, aggiungi:
```python
    APPROVE_EXPORTS = "approve_exports"
```
Nel dizionario `ROLE_PERMISSIONS`, al `frozenset` di `Role.SUPERVISOR` aggiungi `Permission.APPROVE_EXPORTS` (accanto a `VIEW_METRICS`, `VIEW_OPERATOR_ACTIVITY`).

- [ ] **Step 6: Isola i test (`tests/conftest.py`)**

Nel fixture `db`, insieme agli altri `to_regclass`/`TRUNCATE`, aggiungi (guardato, perché la tabella non esiste finché la migrazione non è applicata):
```python
            cur.execute("SELECT to_regclass('export.export_request')")
            export_tbl = cur.fetchone()[0]
            if export_tbl is not None:
                cur.execute("TRUNCATE export.export_request RESTART IDENTITY")
```

- [ ] **Step 7: Esegui i test — devono passare**

Run: `cd backend && pytest -q tests/export/test_setup.py`
Expected: PASS (4 test).

- [ ] **Step 8: Gate + commit**

Run: `cd backend && pytest -q && ruff check . && mypy src`
```bash
git add backend/src/bussola/data/migrations/0006_exports.sql backend/src/bussola/auth/rbac.py backend/tests/conftest.py backend/tests/export
git commit -m "feat(export): 0006 export_request schema + APPROVE_EXPORTS permission"
```

---

### Task 2: `ExportService` (workflow a stati + generazione on-demand + audit)

**Files:**
- Create: `backend/src/bussola/export/__init__.py`
- Create: `backend/src/bussola/export/models.py`
- Create: `backend/src/bussola/export/errors.py`
- Create: `backend/src/bussola/export/service.py`
- Create: `backend/tests/export/test_service.py`

**Interfaces:**
- Consumes: tabella `export.export_request` (Task 1); `append_audit` (`bussola.data.audit`); `ProfileRepository` + `PiiRedactor` (`bussola.data.profiles` / `bussola.guardrails.pii`); `Availability`/`OperationalNoteCategory` (`bussola.profile.enums`); `WorkProfile` (`bussola.profile.models`); fixtures `db`/`app_conn`.
- Produces (Task 3): 
  - `export/models.py`: `ExportFilters` (availability/language/note/skill_query, `extra="forbid"`), `ExportStatus` (Literal), `ExportRequest` (DTO con tutte le colonne).
  - `export/errors.py`: `ExportNotFound`, `ExportNotPending`, `ExportNotApproved` (sottoclassi di `ExportError`).
  - `export/service.py`: `ExportService(conn)` con `create_request(*, actor, filters, reason) -> ExportRequest`, `list_own(*, actor) -> list[ExportRequest]`, `list_pending() -> list[ExportRequest]`, `approve(*, actor, request_id) -> None`, `deny(*, actor, request_id, reason) -> None`, `generate_payload(*, actor, request_id) -> list[WorkProfile]`.

- [ ] **Step 1: Scrivi i modelli (`export/models.py`) e gli errori (`export/errors.py`)**

`export/models.py`:
```python
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
```

`export/errors.py`:
```python
"""Export workflow errors (mapped to HTTP status by the router)."""

from __future__ import annotations


class ExportError(Exception):
    """Base class for export workflow errors."""


class ExportNotFound(ExportError):
    """No such request, or not owned by the caller."""


class ExportNotPending(ExportError):
    """The request has already been decided."""


class ExportNotApproved(ExportError):
    """The request is not in the approved state (cannot download)."""
```

- [ ] **Step 2: Scrivi i test del servizio (`tests/export/test_service.py`)**

```python
import psycopg
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.export.errors import ExportNotApproved, ExportNotFound, ExportNotPending
from bussola.export.models import ExportFilters
from bussola.export.service import ExportService
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def _seed_profile(conn: psycopg.Connection, pid: str, skill: str) -> None:
    ProfileRepository(conn, PiiRedactor()).save(
        WorkProfile(
            pseudonym_id=pid,
            skills=[Skill(name=skill, kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        )
    )


def test_create_starts_pending_and_lists_for_owner(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(skill_query="cucina"), reason="Azienda X")
    assert req.status == "pending"
    assert req.requested_by == "op1"
    assert svc.list_own(actor="op1")[0].id == req.id
    assert svc.list_own(actor="op2") == []  # not visible to another operator


def test_approve_then_download_returns_matching_work_profiles(app_conn: psycopg.Connection):
    _seed_profile(app_conn, "P-1", "Cucina")
    _seed_profile(app_conn, "P-2", "Muratura")
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(skill_query="cucina"), reason="Azienda X")
    svc.approve(actor="sup1", request_id=req.id)
    payload = svc.generate_payload(actor="op1", request_id=req.id)
    assert [p.pseudonym_id for p in payload] == ["P-1"]
    # payload is WorkProfile-only (no extra/PII fields) by construction
    assert all(isinstance(p, WorkProfile) for p in payload)


def test_download_before_approval_is_blocked(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    with pytest.raises(ExportNotApproved):
        svc.generate_payload(actor="op1", request_id=req.id)


def test_download_of_another_operators_request_is_not_found(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    svc.approve(actor="sup1", request_id=req.id)
    with pytest.raises(ExportNotFound):
        svc.generate_payload(actor="op2", request_id=req.id)


def test_deciding_twice_conflicts(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    svc.approve(actor="sup1", request_id=req.id)
    with pytest.raises(ExportNotPending):
        svc.deny(actor="sup1", request_id=req.id, reason="late")


def test_approve_missing_request_is_not_found(app_conn: psycopg.Connection):
    with pytest.raises(ExportNotFound):
        ExportService(app_conn).approve(actor="sup1", request_id=999)


def test_deny_records_reason_and_blocks_download(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    svc.deny(actor="sup1", request_id=req.id, reason="fuori scopo")
    own = svc.list_own(actor="op1")[0]
    assert own.status == "denied"
    assert own.decision_reason == "fuori scopo"
    with pytest.raises(ExportNotApproved):
        svc.generate_payload(actor="op1", request_id=req.id)


def test_download_is_audited_with_count_no_pii(app_conn: psycopg.Connection):
    _seed_profile(app_conn, "P-1", "Cucina")
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(skill_query="cucina"), reason="r")
    svc.approve(actor="sup1", request_id=req.id)
    svc.generate_payload(actor="op1", request_id=req.id)
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym, details FROM audit.audit_log "
            "WHERE action = 'export_downloaded' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    actor, target, details = row
    assert actor == "op1"
    assert target is None
    assert set(details) <= {"request_id", "filters", "count"}
    assert details.get("count") == "1"
```

- [ ] **Step 3: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/export/test_service.py`
Expected: FAIL (`bussola.export.service` inesistente).

- [ ] **Step 4: Implementa il servizio (`export/service.py`)**

```python
"""Export-request workflow: create → approve/deny → download (on-demand).

State transitions and their audit records commit in ONE transaction
(pattern S5). The download re-runs the profile search — no payload is ever
stored (minimization, §5/§7.3)."""

from __future__ import annotations

from typing import Any

import psycopg

from bussola.data.audit import append_audit
from bussola.data.profiles import ProfileRepository
from bussola.export.errors import ExportNotApproved, ExportNotFound, ExportNotPending
from bussola.export.models import ExportFilters, ExportRequest
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.models import WorkProfile

_COLUMNS = (
    "id, requested_by, filters, reason, status, "
    "decided_by, decided_at, decision_reason, created_at"
)


def _row_to_request(row: tuple[Any, ...]) -> ExportRequest:
    return ExportRequest(
        id=row[0],
        requested_by=row[1],
        filters=ExportFilters.model_validate(row[2]),
        reason=row[3],
        status=row[4],
        decided_by=row[5],
        decided_at=row[6],
        decision_reason=row[7],
        created_at=row[8],
    )


def _applied_filter_names(filters: ExportFilters) -> str:
    return ",".join(
        name
        for name, value in (
            ("availability", filters.availability),
            ("language", filters.language),
            ("note", filters.note),
            ("skill_query", filters.skill_query),
        )
        if value is not None
    )


class ExportService:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create_request(self, *, actor: str, filters: ExportFilters, reason: str) -> ExportRequest:
        from psycopg.types.json import Jsonb

        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO export.export_request (requested_by, filters, reason) "
                "VALUES (%s, %s, %s) RETURNING " + _COLUMNS,
                (actor, Jsonb(filters.model_dump(mode="json", exclude_none=True)), reason),
            )
            row = cur.fetchone()
        assert row is not None
        append_audit(
            self._conn,
            action="export_requested",
            actor=actor,
            details={"filters": _applied_filter_names(filters)},
            commit=False,
        )
        self._conn.commit()
        return _row_to_request(row)

    def list_own(self, *, actor: str) -> list[ExportRequest]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _COLUMNS + " FROM export.export_request "
                "WHERE requested_by = %s ORDER BY created_at DESC, id DESC",
                (actor,),
            )
            rows = cur.fetchall()
        return [_row_to_request(r) for r in rows]

    def list_pending(self) -> list[ExportRequest]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _COLUMNS + " FROM export.export_request "
                "WHERE status = 'pending' ORDER BY created_at ASC, id ASC"
            )
            rows = cur.fetchall()
        return [_row_to_request(r) for r in rows]

    def approve(self, *, actor: str, request_id: int) -> None:
        self._decide(actor=actor, request_id=request_id, status="approved", reason=None)

    def deny(self, *, actor: str, request_id: int, reason: str) -> None:
        self._decide(actor=actor, request_id=request_id, status="denied", reason=reason)

    def _decide(self, *, actor: str, request_id: int, status: str, reason: str | None) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE export.export_request "
                "SET status = %s, decided_by = %s, decided_at = now(), decision_reason = %s "
                "WHERE id = %s AND status = 'pending'",
                (status, actor, reason, request_id),
            )
            if cur.rowcount == 0:
                cur.execute("SELECT 1 FROM export.export_request WHERE id = %s", (request_id,))
                if cur.fetchone() is None:
                    raise ExportNotFound(str(request_id))
                raise ExportNotPending(str(request_id))
        append_audit(
            self._conn,
            action=("export_approved" if status == "approved" else "export_denied"),
            actor=actor,
            details={"request_id": str(request_id)},
            commit=False,
        )
        self._conn.commit()

    def generate_payload(self, *, actor: str, request_id: int) -> list[WorkProfile]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT requested_by, filters, status FROM export.export_request WHERE id = %s",
                (request_id,),
            )
            row = cur.fetchone()
        if row is None or row[0] != actor:
            raise ExportNotFound(str(request_id))
        if row[2] != "approved":
            raise ExportNotApproved(str(request_id))
        filters = ExportFilters.model_validate(row[1])
        profiles = ProfileRepository(self._conn, PiiRedactor()).search(
            availability=filters.availability,
            language=filters.language,
            note=filters.note,
            skill_query=filters.skill_query,
        )
        append_audit(
            self._conn,
            action="export_downloaded",
            actor=actor,
            details={
                "request_id": str(request_id),
                "filters": _applied_filter_names(filters),
                "count": str(len(profiles)),
            },
        )
        return profiles
```

- [ ] **Step 5: Esegui i test del servizio — devono passare**

Run: `cd backend && pytest -q tests/export/test_service.py`
Expected: PASS (8 test).

- [ ] **Step 6: Gate + commit**

Run: `cd backend && pytest -q && ruff check . && mypy src`
```bash
git add backend/src/bussola/export backend/tests/export/test_service.py
git commit -m "feat(export): ExportService state workflow + on-demand payload + audit"
```

---

### Task 3: Endpoint `/exports` (RBAC + download gate)

**Files:**
- Create: `backend/src/bussola/api/routers/exports.py`
- Modify: `backend/src/bussola/api/app.py`
- Create: `backend/tests/api/test_exports_router.py`

**Interfaces:**
- Consumes: `ExportService` + `ExportFilters`/`ExportRequest` + errori (Task 2); `require_permission`/`get_conn` (`bussola.api.deps`); `Permission.EXPORT_DATA`/`APPROVE_EXPORTS` (Task 1); `Operator` (`bussola.auth.models`); `WorkProfile` (`bussola.profile.models`); fixtures `client`/`make_operator`/`app_conn`/`db`.
- Produces: contratto HTTP `/exports` (vedi spec §5).

- [ ] **Step 1: Scrivi i test dell'endpoint (`tests/api/test_exports_router.py`)**

```python
import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_operator_creates_and_lists_own_pending_request(client, make_operator):
    user, temp = make_operator("op1", Role.OPERATOR)
    tok = _login(client, user, temp)
    r = client.post("/exports", json={"filters": {"skill_query": "cucina"}, "reason": "Azienda X"}, headers=_auth(tok))
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    lst = client.get("/exports", headers=_auth(tok))
    assert [x["id"] for x in lst.json()] == [r.json()["id"]]


def test_operator_cannot_approve_or_see_pending(client, make_operator):
    user, temp = make_operator("op1", Role.OPERATOR)
    tok = _login(client, user, temp)
    assert client.get("/exports/pending", headers=_auth(tok)).status_code == 403
    assert client.post("/exports/1/approve", headers=_auth(tok)).status_code == 403


def test_supervisor_cannot_create_or_download(client, make_operator):
    sup, temp = make_operator("sup1", Role.SUPERVISOR)
    tok = _login(client, sup, temp)
    assert client.post("/exports", json={"filters": {}, "reason": "r"}, headers=_auth(tok)).status_code == 403
    assert client.get("/exports/1/download", headers=_auth(tok)).status_code == 403


def test_full_flow_request_approve_download(client, make_operator, app_conn: psycopg.Connection):
    ProfileRepository(app_conn, PiiRedactor()).save(
        WorkProfile(pseudonym_id="P-1", skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)])
    )
    op, otemp = make_operator("op1", Role.OPERATOR)
    sup, stemp = make_operator("sup1", Role.SUPERVISOR)
    otok = _login(client, op, otemp)
    stok = _login(client, sup, stemp)
    rid = client.post("/exports", json={"filters": {"skill_query": "cucina"}, "reason": "Azienda X"}, headers=_auth(otok)).json()["id"]
    # not approved yet → 409
    assert client.get(f"/exports/{rid}/download", headers=_auth(otok)).status_code == 409
    # supervisor sees it pending and approves
    assert rid in [x["id"] for x in client.get("/exports/pending", headers=_auth(stok)).json()]
    assert client.post(f"/exports/{rid}/approve", headers=_auth(stok)).status_code == 204
    # operator downloads → work-only profiles
    dl = client.get(f"/exports/{rid}/download", headers=_auth(otok))
    assert dl.status_code == 200
    body = dl.json()
    assert [p["pseudonym_id"] for p in body] == ["P-1"]
    assert all(set(p) <= set(WorkProfile.model_fields) for p in body)  # WorkProfile-only


def test_download_of_other_operators_request_is_404(client, make_operator):
    op1, t1 = make_operator("op1", Role.OPERATOR)
    op2, t2 = make_operator("op2", Role.OPERATOR)
    sup, st = make_operator("sup1", Role.SUPERVISOR)
    tok1, tok2, stok = _login(client, op1, t1), _login(client, op2, t2), _login(client, sup, st)
    rid = client.post("/exports", json={"filters": {}, "reason": "r"}, headers=_auth(tok1)).json()["id"]
    client.post(f"/exports/{rid}/approve", headers=_auth(stok))
    assert client.get(f"/exports/{rid}/download", headers=_auth(tok2)).status_code == 404


def test_approve_twice_conflicts(client, make_operator):
    op, ot = make_operator("op1", Role.OPERATOR)
    sup, st = make_operator("sup1", Role.SUPERVISOR)
    otok, stok = _login(client, op, ot), _login(client, sup, st)
    rid = client.post("/exports", json={"filters": {}, "reason": "r"}, headers=_auth(otok)).json()["id"]
    assert client.post(f"/exports/{rid}/approve", headers=_auth(stok)).status_code == 204
    assert client.post(f"/exports/{rid}/approve", headers=_auth(stok)).status_code == 409
    assert client.post("/exports/999/approve", headers=_auth(stok)).status_code == 404
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/api/test_exports_router.py`
Expected: FAIL (rotta `/exports` inesistente → 404/401).

- [ ] **Step 3: Implementa il router (`api/routers/exports.py`)**

```python
"""Export-request endpoints. Requester = operator (EXPORT_DATA); approver =
supervisor (APPROVE_EXPORTS). Download is server-gated on approval + ownership (§7.3)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.export.errors import ExportNotApproved, ExportNotFound, ExportNotPending
from bussola.export.models import ExportFilters, ExportRequest
from bussola.export.service import ExportService
from bussola.profile.models import WorkProfile

router = APIRouter(prefix="/exports", tags=["exports"])
_request = require_permission(Permission.EXPORT_DATA)
_approve = require_permission(Permission.APPROVE_EXPORTS)


class CreateExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: ExportFilters
    reason: str = Field(min_length=1, max_length=500)


class DenyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=500)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ExportRequest)
def create_export(
    body: CreateExportBody,
    operator: Operator = Depends(_request),
    conn: psycopg.Connection = Depends(get_conn),
) -> ExportRequest:
    return ExportService(conn).create_request(actor=operator.username, filters=body.filters, reason=body.reason)


@router.get("", response_model=list[ExportRequest])
def list_my_exports(
    operator: Operator = Depends(_request),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[ExportRequest]:
    return ExportService(conn).list_own(actor=operator.username)


@router.get("/pending", response_model=list[ExportRequest])
def list_pending_exports(
    operator: Operator = Depends(_approve),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[ExportRequest]:
    return ExportService(conn).list_pending()


@router.post("/{request_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
def approve_export(
    request_id: int,
    operator: Operator = Depends(_approve),
    conn: psycopg.Connection = Depends(get_conn),
) -> Response:
    try:
        ExportService(conn).approve(actor=operator.username, request_id=request_id)
    except ExportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export request not found")
    except ExportNotPending:
        raise HTTPException(status.HTTP_409_CONFLICT, "export request already decided")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{request_id}/deny", status_code=status.HTTP_204_NO_CONTENT)
def deny_export(
    request_id: int,
    body: DenyBody,
    operator: Operator = Depends(_approve),
    conn: psycopg.Connection = Depends(get_conn),
) -> Response:
    try:
        ExportService(conn).deny(actor=operator.username, request_id=request_id, reason=body.reason)
    except ExportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export request not found")
    except ExportNotPending:
        raise HTTPException(status.HTTP_409_CONFLICT, "export request already decided")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{request_id}/download", response_model=list[WorkProfile])
def download_export(
    request_id: int,
    operator: Operator = Depends(_request),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[WorkProfile]:
    try:
        return ExportService(conn).generate_payload(actor=operator.username, request_id=request_id)
    except ExportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export request not found")
    except ExportNotApproved:
        raise HTTPException(status.HTTP_409_CONFLICT, "export request not approved")
```

In `backend/src/bussola/api/app.py`: aggiungi `from bussola.api.routers import exports as exports_router` (in ordine alfabetico) e `app.include_router(exports_router.router)` (dopo `profiles_router`).

- [ ] **Step 4: Esegui i test dell'endpoint — devono passare**

Run: `cd backend && pytest -q tests/api/test_exports_router.py`
Expected: PASS (6 test).

- [ ] **Step 5: Gate completo + commit**

Run: `cd backend && pytest -q && ruff check . && mypy src`
```bash
git add backend/src/bussola/api/routers/exports.py backend/src/bussola/api/app.py backend/tests/api/test_exports_router.py
git commit -m "feat(export): /exports endpoints (RBAC + server-gated download)"
```

---

## Self-Review

- **Spec coverage:** §2 obiettivi → migrazione+permesso (T1), service a stati+generazione+audit (T2), endpoint RBAC+download gate (T3). Autorizzazione server-side (download 409/404), ruoli disgiunti (EXPORT_DATA vs APPROVE_EXPORTS), payload WorkProfile-only (test assert `set(p) <= WorkProfile.model_fields`), audit di ogni azione, nessun payload memorizzato, concurrency guard (`WHERE status='pending'`→409). Tutti coperti.
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto.
- **Type consistency:** `ExportFilters`/`ExportRequest`/`ExportStatus` (T2) usati da service e router (T3) coerentemente; `create_request(*, actor, filters, reason)`, `approve/deny(*, actor, request_id[, reason])`, `generate_payload(*, actor, request_id)` con le stesse firme in T2 e T3; errori `ExportNotFound/NotPending/NotApproved` mappati 404/409/409 nel router; `Permission.APPROVE_EXPORTS` (T1) consumato da T3; colonne SQL (T1) ↔ `_COLUMNS`/`_row_to_request` (T2). `ProfileRepository.search` chiamato coi kwargs tipizzati corretti.
- **Rossa/audit:** download gated server-side; payload solo WorkProfile via PiiRedactor; audit senza PII (nomi-filtro+conteggio); `bussola_app` senza DELETE; nessuna auto-approvazione (ruoli disgiunti).
