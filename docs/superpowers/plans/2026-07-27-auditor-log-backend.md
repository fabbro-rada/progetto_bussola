# Vista del log di audit (Auditor) — Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Endpoint di **sola lettura** del log di audit per il ruolo Auditor (§6): `GET /audit` (paginato a cursore, con filtri chi/cosa/quando) e `GET /audit/verify` (tamper-evidence §7.3), dietro `READ_AUDIT`.

**Architecture:** Estende `data/audit.py` con `AuditEntry` + `list_audit` (query di sola lettura su `audit.audit_log`, cursore per `id DESC`, filtri, `limit` cap-ato); riusa `verify_audit_chain` (S2). Nuovo router `api/routers/audit.py` dietro `require_permission(READ_AUDIT)` (solo auditor; server autorità). Letture **pure** — nessun evento appeso (§6 «non modifica nulla»). Nessuna nuova tabella/migrazione.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, psycopg3, PostgreSQL. Test: pytest (DB reale) + ruff + mypy (strict).

## Global Constraints

- **Solo `backend/`.** `operator-portal/` e `frontend/` NON si toccano. Nessuna nuova dipendenza. **Nessuna nuova tabella/migrazione** (si legge da `audit.audit_log`).
- **TDD** (RED → GREEN), **solo dati sintetici**. Output test pristine.
- **RBAC (§6, server autorità):** `GET /audit` e `GET /audit/verify` dietro `require_permission(READ_AUDIT)` → **solo ruolo `auditor`**; ogni altro ruolo → **403**.
- **Letture pure (§6 «non modifica nulla»):** né `/audit` né `/audit/verify` appendono un evento di audit; il numero di righe del log resta invariato dopo una lettura.
- **Cursore per `id DESC`:** `GET /audit?before=<id>&limit=<n>` → voci con `id < before` (o le ultime), più recenti prima; `limit` ha **default 50** e **cap 200**.
- **Filtri opzionali** combinabili: `actor` (match esatto), `action` (match esatto), `from`/`to` (intervallo su `occurred_at`).
- **Voce = `{id, occurred_at, actor, action, target_pseudonym, details}`**; gli hash interni (`prev_hash`/`record_hash`) **non** sono esposti.
- **Nessun rischio §2:** il log traccia azioni degli operatori + pseudonimi opachi; nessun dato/inferenza sulla persona.
- **DB attivo** per i test: `docker compose up -d db`.
- **Gate** (da `backend/`, `.venv` attiva): `pytest -q && ruff check . && mypy src`.

---

### Task 1: `AuditEntry` + `list_audit` (lettura con cursore/filtri) in `data/audit.py`

**Files:**
- Modify: `backend/src/bussola/data/audit.py` (append `AuditEntry` + `list_audit`)
- Create: `backend/tests/data/test_audit_read.py`

**Interfaces:**
- Consumes: tabella `audit.audit_log` (colonne `id, occurred_at, actor, action, target_pseudonym, details, prev_hash, record_hash`); `append_audit` (per seedare); `verify_audit_chain` (già in `data/audit.py`); fixtures `db`/`app_conn`.
- Produces (Task 2): `AuditEntry` (pydantic: `id:int, occurred_at:datetime, actor:str|None, action:str, target_pseudonym:str|None, details:dict`); `list_audit(conn, *, before:int|None=None, limit:int=50, actor:str|None=None, action:str|None=None, from_ts:datetime|None=None, to_ts:datetime|None=None) -> list[AuditEntry]` (id DESC, `id<before`, filtri esatti/intervallo, `limit` cap 1..200).

- [ ] **Step 1: Avvia il DB di test**

Run: `cd backend && docker compose up -d db` (idempotente).

- [ ] **Step 2: Scrivi i test (`tests/data/test_audit_read.py`)**

```python
from datetime import datetime, timezone

import psycopg
import pytest

from bussola.data.audit import append_audit, list_audit, verify_audit_chain

pytestmark = pytest.mark.usefixtures("db")


def _seed(conn: psycopg.Connection) -> None:
    append_audit(conn, action="login_succeeded", actor="op1")
    append_audit(conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    append_audit(conn, action="metrics_viewed", actor="sup1")


def test_lists_newest_first(app_conn: psycopg.Connection):
    _seed(app_conn)
    entries = list_audit(app_conn)
    assert [e.action for e in entries] == ["metrics_viewed", "profile_viewed", "login_succeeded"]
    # entry exposes who/what/when/details, not the hashes
    top = entries[0]
    assert top.actor == "sup1" and top.target_pseudonym is None
    assert set(top.model_dump()) == {"id", "occurred_at", "actor", "action", "target_pseudonym", "details"}


def test_cursor_before_and_limit_cap(app_conn: psycopg.Connection):
    _seed(app_conn)
    all_entries = list_audit(app_conn)
    second_id = all_entries[1].id
    older = list_audit(app_conn, before=all_entries[0].id)
    assert older[0].id == second_id  # excludes the newest
    assert len(list_audit(app_conn, limit=1)) == 1
    assert len(list_audit(app_conn, limit=9999)) <= 200  # cap enforced


def test_filters_actor_action_and_time(app_conn: psycopg.Connection):
    _seed(app_conn)
    assert all(e.actor == "op1" for e in list_audit(app_conn, actor="op1"))
    assert [e.action for e in list_audit(app_conn, action="metrics_viewed")] == ["metrics_viewed"]
    future = datetime(2999, 1, 1, tzinfo=timezone.utc)
    assert list_audit(app_conn, from_ts=future) == []


def test_verify_ok_on_intact_chain(app_conn: psycopg.Connection):
    _seed(app_conn)
    result = verify_audit_chain(app_conn)
    assert result.ok is True


def test_verify_detects_a_tampered_row(app_conn: psycopg.Connection):
    _seed(app_conn)
    # INSERT is permitted (only UPDATE/DELETE are trigger-blocked); a row with a
    # bogus prev_hash breaks the chain without touching existing rows.
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit.audit_log "
            "(occurred_at, actor, action, target_pseudonym, details, prev_hash, record_hash) "
            "VALUES (now(), 'x', 'tampered', NULL, '{}'::jsonb, 'wrongprev', 'wronghash') RETURNING id"
        )
        row = cur.fetchone()
    app_conn.commit()
    assert row is not None
    result = verify_audit_chain(app_conn)
    assert result.ok is False
    assert result.broken_at == row[0]
```

- [ ] **Step 3: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/data/test_audit_read.py`
Expected: FAIL (`list_audit` non esiste).

- [ ] **Step 4: Implementa `AuditEntry` + `list_audit` (`data/audit.py`)**

Aggiungi in cima agli import (se mancanti): `from datetime import datetime` (già presente `datetime, timezone`), `from pydantic import BaseModel, ConfigDict`. Poi, dopo `VerificationResult` / `verify_audit_chain`, aggiungi:
```python
class AuditEntry(BaseModel):
    """Read-only view of one audit row (hashes are internal, not exposed)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    occurred_at: datetime
    actor: str | None
    action: str
    target_pseudonym: str | None
    details: dict[str, Any]


def list_audit(
    conn: psycopg.Connection,
    *,
    before: int | None = None,
    limit: int = 50,
    actor: str | None = None,
    action: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> list[AuditEntry]:
    """Read audit entries, newest first, id-cursor paginated. Read-only."""
    capped = max(1, min(limit, 200))
    clauses: list[str] = []
    params: list[object] = []
    if before is not None:
        clauses.append("id < %s")
        params.append(before)
    if actor is not None:
        clauses.append("actor = %s")
        params.append(actor)
    if action is not None:
        clauses.append("action = %s")
        params.append(action)
    if from_ts is not None:
        clauses.append("occurred_at >= %s")
        params.append(from_ts)
    if to_ts is not None:
        clauses.append("occurred_at <= %s")
        params.append(to_ts)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(capped)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, occurred_at, actor, action, target_pseudonym, details "
            "FROM audit.audit_log" + where + " ORDER BY id DESC LIMIT %s",
            params,
        )
        rows = cur.fetchall()
    return [
        AuditEntry(
            id=r[0], occurred_at=r[1], actor=r[2], action=r[3], target_pseudonym=r[4], details=r[5]
        )
        for r in rows
    ]
```
(`Any` è già importato in `data/audit.py`. Se non lo fosse, aggiungi `from typing import Any`.)

- [ ] **Step 5: Esegui i test — devono passare**

Run: `cd backend && pytest -q tests/data/test_audit_read.py`
Expected: PASS (5 test).

- [ ] **Step 6: Gate + commit**

Run: `cd backend && pytest -q && ruff check . && mypy src`
```bash
git add backend/src/bussola/data/audit.py backend/tests/data/test_audit_read.py
git commit -m "feat(audit): AuditEntry + list_audit (cursor + filters, read-only)"
```

---

### Task 2: Router `GET /audit` + `GET /audit/verify` (READ_AUDIT)

**Files:**
- Create: `backend/src/bussola/api/routers/audit.py`
- Modify: `backend/src/bussola/api/app.py`
- Create: `backend/tests/api/test_audit_router.py`

**Interfaces:**
- Consumes: `AuditEntry`/`list_audit`/`verify_audit_chain`/`VerificationResult` (`data/audit.py`, Task 1 + S2); `require_permission`/`get_conn` (`api/deps`); `Permission.READ_AUDIT` (`auth/rbac`); `Operator` (`auth/models`); fixtures `client`/`make_operator`/`app_conn`/`db`.
- Produces: contratto HTTP `/audit` e `/audit/verify` (spec §5).

- [ ] **Step 1: Scrivi i test dell'endpoint (`tests/api/test_audit_router.py`)**

```python
import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.audit import append_audit

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auditor_reads_entries_newest_first(client, make_operator, app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    append_audit(app_conn, action="metrics_viewed", actor="sup1")
    user, temp = make_operator("aud1", Role.AUDITOR)
    tok = _login(client, user, temp)
    r = client.get("/audit", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    # newest first; entries expose no internal hashes
    assert body[0]["action"] == "metrics_viewed"
    assert "record_hash" not in body[0] and "prev_hash" not in body[0]


def test_non_auditor_roles_are_forbidden(client, make_operator):
    for name, role in [("op1", Role.OPERATOR), ("sup1", Role.SUPERVISOR), ("adm1", Role.ADMIN)]:
        user, temp = make_operator(name, role)
        tok = _login(client, user, temp)
        assert client.get("/audit", headers=_auth(tok)).status_code == 403
        assert client.get("/audit/verify", headers=_auth(tok)).status_code == 403


def test_filters_and_cursor_are_applied(client, make_operator, app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1")
    append_audit(app_conn, action="metrics_viewed", actor="sup1")
    user, temp = make_operator("aud1", Role.AUDITOR)
    tok = _login(client, user, temp)
    only = client.get("/audit?action=metrics_viewed", headers=_auth(tok)).json()
    assert [e["action"] for e in only] == ["metrics_viewed"]
    assert all(e["actor"] == "op1" for e in client.get("/audit?actor=op1", headers=_auth(tok)).json())
    one = client.get("/audit?limit=1", headers=_auth(tok)).json()
    assert len(one) == 1


def test_reading_the_log_does_not_write_to_it(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("aud1", Role.AUDITOR)
    tok = _login(client, user, temp)  # login writes an audit row; count AFTER it
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log")
        before = cur.fetchone()[0]
    client.get("/audit", headers=_auth(tok))
    client.get("/audit/verify", headers=_auth(tok))
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log")
        after = cur.fetchone()[0]
    assert after == before  # §6: the auditor's reads modify nothing


def test_verify_reports_intact_chain(client, make_operator, app_conn: psycopg.Connection):
    append_audit(app_conn, action="login_succeeded", actor="op1")
    user, temp = make_operator("aud1", Role.AUDITOR)
    tok = _login(client, user, temp)
    r = client.get("/audit/verify", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/api/test_audit_router.py`
Expected: FAIL (rotta `/audit` inesistente → 404/401).

- [ ] **Step 3: Implementa il router (`api/routers/audit.py`)**

```python
"""Audit-log read endpoints (Auditor role, READ_AUDIT). Read-only: these
endpoints never append to the log (§6 — the auditor modifies nothing)."""

from __future__ import annotations

from datetime import datetime

import psycopg
from fastapi import APIRouter, Depends, Query

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import AuditEntry, VerificationResult, list_audit, verify_audit_chain

router = APIRouter(prefix="/audit", tags=["audit"])
_read = require_permission(Permission.READ_AUDIT)


@router.get("", response_model=list[AuditEntry])
def read_audit(
    before: int | None = None,
    limit: int = 50,
    actor: str | None = None,
    action: str | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    operator: Operator = Depends(_read),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[AuditEntry]:
    return list_audit(
        conn, before=before, limit=limit, actor=actor, action=action, from_ts=from_, to_ts=to
    )


@router.get("/verify", response_model=VerificationResult)
def verify(
    operator: Operator = Depends(_read),
    conn: psycopg.Connection = Depends(get_conn),
) -> VerificationResult:
    return verify_audit_chain(conn)
```
In `backend/src/bussola/api/app.py`: aggiungi `from bussola.api.routers import audit as audit_router` (in ordine alfabetico tra gli import dei router) e `app.include_router(audit_router.router)` (dopo `auth_router` / `profiles_router` — l'ordine non conta funzionalmente).

- [ ] **Step 4: Esegui i test dell'endpoint — devono passare**

Run: `cd backend && pytest -q tests/api/test_audit_router.py`
Expected: PASS (5 test). Nota: `VerificationResult` è un dataclass; FastAPI lo serializza come `{ok, broken_at, reason}` (verificato dal test `ok is True`).

- [ ] **Step 5: Gate completo + commit**

Run: `cd backend && pytest -q && ruff check . && mypy src`
```bash
git add backend/src/bussola/api/routers/audit.py backend/src/bussola/api/app.py backend/tests/api/test_audit_router.py
git commit -m "feat(audit): GET /audit + /audit/verify (READ_AUDIT, read-only)"
```

---

## Self-Review

- **Spec coverage:** §2 obiettivi → `AuditEntry`+`list_audit` (T1), `/audit`+`/audit/verify` router (T2). Cursore per id + limit-cap, filtri actor/action/from-to, verify esposto, letture pure (test conteggio invariato), RBAC solo-auditor (403 altri), voce senza hash. Tutti coperti.
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto.
- **Type consistency:** `AuditEntry` (T1) è il `response_model` di `/audit` (T2); `list_audit(conn, *, before, limit, actor, action, from_ts, to_ts)` firma identica in T1 e nella chiamata T2 (il router mappa `from`→`from_ts`, `to`→`to_ts`); `VerificationResult` (S2) riusato come `response_model` di `/verify`; `Permission.READ_AUDIT` (auth/rbac, già mappato al solo auditor) consumato da T2; colonne SQL ↔ costruzione `AuditEntry`.
- **Rossa/§6:** RBAC server-side (403 non-auditor); letture pure (nessun append — test lo verifica); nessun hash esposto; log = azioni operatori + pseudonimi opachi (no dati/inferenze sulla persona §2).
