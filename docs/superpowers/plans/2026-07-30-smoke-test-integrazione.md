# Smoke test di integrazione — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dare fiducia che il progetto, spostato su un PC nuovo da zero, si accenda e funzioni insieme — via un endpoint `/health`, un harness full-stack e uno smoke di integrazione in-process che esercita il cablaggio reale auth/DB/audit/RBAC.

**Architecture:** Un piccolo endpoint pubblico `GET /health` (liveness) abilita l'attesa di prontezza. `run-stack.sh` lo usa per non dichiarare "up" prima del tempo. Un test pytest in-process usa la gestione connessione REALE dell'app (fresh conn per richiesta, chiusa senza commit) puntata al DB di test, così cattura i "commit dimenticati" che i test a connessione condivisa nascondono. Uno script `smoke-full-stack.sh` avvia l'intero stack via run-stack e sonda i percorsi critici.

**Tech Stack:** Python 3.12 / FastAPI / psycopg3 / pytest; Bash; curl + il Python del venv per il parsing JSON.

## Global Constraints

- **§9 TDD, solo dati sintetici**: username/password di test sintetici; nessun dato reale.
- **§3 open source, locale, budget nullo**: nessuna dipendenza nuova; il parsing JSON nell'harness usa il Python del venv (`backend/.venv/bin/python`).
- **§11 codice e commenti in inglese**; documenti in italiano.
- **§2/§5**: `/health` non espone alcun dato (solo `{"status":"ok"}`); nessun rischio linee rosse.
- Gate backend: `pytest -q && ruff check . && mypy src` (da `backend/`, venv attivo).
- Non introdurre altre modifiche al prodotto oltre a `GET /health`.

---

### Task 1: Endpoint `GET /health`

**Files:**
- Create: `backend/src/bussola/api/routers/health.py`
- Modify: `backend/src/bussola/api/app.py` (registra il router)
- Test: `backend/tests/api/test_health.py`

**Interfaces:**
- Produces: rotta pubblica `GET /health` → `200 {"status": "ok"}`, senza auth né DB. Consumata da run-stack.sh (Task 2) e smoke-full-stack.sh (Task 4).

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_health.py`:
```python
from fastapi.testclient import TestClient

from bussola.api.app import create_app


def test_health_is_public_and_ok():
    # No auth, no DB: liveness only. Must work even with Postgres down.
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/api/test_health.py -v`
Expected: FAIL (404 — route not yet registered).

- [ ] **Step 3: Create the router**

`backend/src/bussola/api/routers/health.py`:
```python
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
```

- [ ] **Step 4: Register it in the app factory**

In `backend/src/bussola/api/app.py`, add the import alongside the other router imports:
```python
from bussola.api.routers import health as health_router
```
and register it as the first router inside `create_app()` (right after `register_error_handlers(app)`):
```python
    app.include_router(health_router.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/api/test_health.py -v`
Expected: PASS.

- [ ] **Step 6: Gate + commit**

Run: `cd backend && pytest -q && ruff check . && mypy src`
```bash
git add backend/src/bussola/api/routers/health.py backend/src/bussola/api/app.py backend/tests/api/test_health.py
git commit -m "feat(api): public GET /health liveness endpoint"
```

---

### Task 2: `run-stack.sh` attende la prontezza del backend

**Files:**
- Modify: `scripts/run-stack.sh` (dopo l'avvio del backend, prima o insieme all'avvio dei frontend)

**Interfaces:**
- Consumes: `GET /health` (Task 1).
- Produces: run-stack non stampa "Stack up" prima che il backend risponda `200` su `/health`.

- [ ] **Step 1: Add a readiness wait after starting the backend**

In `scripts/run-stack.sh`, immediately AFTER the backend `start_bg` call (the block that prints `==> Backend API -> http://127.0.0.1:8000` and calls `start_bg backend ...`), insert:
```bash
printf "    waiting for backend"
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then printf " ready\n"; break; fi
  printf "."; sleep 1
  if [ "$i" = 30 ]; then printf " TIMEOUT (see %s)\n" "$RUN_DIR/backend.log"; fi
done
```
This mirrors the existing `pg_isready` wait loop. On timeout it warns and continues (the frontends can still start; the log explains why).

- [ ] **Step 2: Static check**

Run: `shellcheck scripts/run-stack.sh`
Expected: no new warnings.

- [ ] **Step 3: Commit**

```bash
git add scripts/run-stack.sh
git commit -m "chore(dev): run-stack.sh waits for backend /health before declaring up"
```

---

### Task 3: Smoke di integrazione in-process

**Files:**
- Create: `backend/tests/test_smoke_integration.py`

**Interfaces:**
- Consumes: `create_app()`, `bussola.auth.bootstrap.main`, `deps.get_conn` (real), fixtures `db` + `auditor_conn`, `config._DBNAME`, `Role`.
- Note: the `db`/`auditor_conn` fixtures already skip cleanly when Postgres is unreachable (see `backend/tests/conftest.py` docstring) — no `requires_db` marker needed.

- [ ] **Step 1: Write the smoke test**

`backend/tests/test_smoke_integration.py`:
```python
"""End-to-end integration smoke.

Unlike the per-router unit tests (which inject one shared connection via a
get_conn override, so writes are visible without a commit), this exercises the
REAL wiring: deps.get_conn opens a fresh connection per request as the app role
and closes it WITHOUT committing. A service that forgot to commit fails here.

Path: bootstrap (real CLI) -> admin login -> forced password change -> admin
creates an operator -> operator authenticated write (committed, re-read on a
fresh request) -> RBAC deny -> audit rows persisted (read directly).
"""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

from bussola.api.app import create_app
from bussola.auth import bootstrap
from bussola.auth.rbac import Role
from bussola.data import config


def test_full_stack_wiring_smoke(
    db: None, auditor_conn: psycopg.Connection, monkeypatch
) -> None:
    # Point the app's real get_conn (config.dsn("app"), no dbname) at the
    # migrated test DB, so we exercise real per-request connection management
    # instead of the shared app_conn override used by router unit tests.
    monkeypatch.setattr(config, "_DBNAME", "bussola_test")

    # 1. Bootstrap the first admin via the REAL CLI entrypoint (what a new PC runs).
    monkeypatch.setenv("BUSSOLA_ADMIN_USERNAME", "smoke_admin")
    monkeypatch.setenv("BUSSOLA_ADMIN_PASSWORD", "bootstrap-temp-pw-1")
    assert bootstrap.main() == 0

    client = TestClient(create_app())  # NO get_conn override: real wiring.

    # 2. Admin logs in with the temp password -> must change it.
    r = client.post(
        "/auth/login",
        json={"username": "smoke_admin", "password": "bootstrap-temp-pw-1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is True
    admin_token = r.json()["token"]

    # 3. Change the password.
    r = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"old_password": "bootstrap-temp-pw-1", "new_password": "admin-new-pw-123"},
    )
    assert r.status_code == 204, r.text

    # 4. Re-login with the new password.
    r = client.post(
        "/auth/login",
        json={"username": "smoke_admin", "password": "admin-new-pw-123"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is False
    admin_auth = {"Authorization": f"Bearer {r.json()['token']}"}

    # 5. Admin creates an operator; receives that operator's temp password.
    r = client.post(
        "/operators",
        headers=admin_auth,
        json={"username": "smoke_op", "display_name": "Smoke Op", "role": Role.OPERATOR.value},
    )
    assert r.status_code == 201, r.text
    op_temp = r.json()["temp_password"]

    # 6. Operator logs in and changes password.
    r = client.post("/auth/login", json={"username": "smoke_op", "password": op_temp})
    assert r.status_code == 200, r.text
    op_token = r.json()["token"]
    r = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {op_token}"},
        json={"old_password": op_temp, "new_password": "op-new-pw-123"},
    )
    assert r.status_code == 204, r.text
    r = client.post("/auth/login", json={"username": "smoke_op", "password": "op-new-pw-123"})
    op_auth = {"Authorization": f"Bearer {r.json()['token']}"}

    # 7. Operator performs an authenticated write that COMMITS.
    r = client.post(
        "/job-requests",
        headers=op_auth,
        json={"title": "Aiuto cuoco", "sector": "ristorazione"},
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    # 8. A separate request (fresh connection) sees the committed row -> proves
    #    the write was really committed, not just visible inside one transaction.
    r = client.get(f"/job-requests/{job_id}", headers=op_auth)
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Aiuto cuoco"

    # 9. RBAC: the operator cannot perform an admin-only action.
    r = client.post(
        "/operators",
        headers=op_auth,
        json={"username": "nope", "display_name": "Nope", "role": Role.OPERATOR.value},
    )
    assert r.status_code == 403, r.text

    # 10. Audit: the HTTP actions persisted immutable rows (read directly as auditor).
    auditor_conn.rollback()  # fresh snapshot: see everything committed above
    with auditor_conn.cursor() as cur:
        cur.execute("SELECT action FROM audit.audit_log")
        actions = {row[0] for row in cur.fetchall()}
    assert {"operator_created", "login_succeeded", "password_changed"} <= actions
```

- [ ] **Step 2: Run it (requires Postgres up)**

Run: `cd backend && docker compose up -d db >/dev/null 2>&1; pytest tests/test_smoke_integration.py -v`
Expected: PASS (or a clean SKIP if Postgres is genuinely unavailable). If it FAILS on a commit/visibility assertion (step 8) or an audit assertion (step 10), that is a real wiring defect to report, not a test bug.

- [ ] **Step 3: Full gate + commit**

Run: `cd backend && pytest -q && ruff check . && mypy src`
```bash
git add backend/tests/test_smoke_integration.py
git commit -m "test(backend): end-to-end integration smoke over real get_conn wiring"
```

---

### Task 4: Harness full-stack `scripts/smoke-full-stack.sh`

**Files:**
- Create: `scripts/smoke-full-stack.sh` (eseguibile)

**Interfaces:**
- Consumes: `scripts/run-stack.sh` (avvio/stop), `GET /health`, `POST /auth/login`, `GET /me`, `backend/.venv/bin/python` (JSON).
- Produces: uno script one-shot che avvia lo stack, sonda i percorsi critici, lo ferma, ed esce `0` solo se tutto passa.

- [ ] **Step 1: Write the harness**

`scripts/smoke-full-stack.sh`:
```bash
#!/usr/bin/env bash
# Full-stack smoke: the "fresh PC works" check (STATO_TECNICO §11). Brings the
# whole stack up via run-stack.sh (NO LLM: the interview is out of scope), then
# actively probes the critical paths — backend liveness, both frontends serve,
# and a real login + authenticated call — and stops the stack on exit.
#
# Expects the bootstrap default admin (a fresh/dev stack): it does NOT change
# any password, so it is safe to re-run. Override creds/ports via env if needed.
#
#   scripts/smoke-full-stack.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${SMOKE_BACKEND_PORT:-8000}"
KIOSK_PORT="${SMOKE_KIOSK_PORT:-5173}"
PORTAL_PORT="${SMOKE_PORTAL_PORT:-5174}"
ADMIN_USER="${BUSSOLA_ADMIN_USERNAME:-admin}"
ADMIN_PW="${BUSSOLA_ADMIN_PASSWORD:-admin_dev_change_me}"
BACKEND="http://127.0.0.1:$BACKEND_PORT"
PYTHON="$ROOT/backend/.venv/bin/python"

pass() { printf '  OK   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; exit 1; }

# Poll an URL until it returns HTTP 200, up to N seconds.
wait_http() {
  local url="$1" what="$2" tries="${3:-40}"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then pass "$what"; return 0; fi
    sleep 1
  done
  fail "$what (timeout on $url)"
}

echo "==> Bringing up the stack (run-stack.sh, no LLM)"
bash scripts/run-stack.sh
trap 'echo "==> Stopping the stack"; bash scripts/run-stack.sh stop >/dev/null 2>&1 || true' EXIT

echo "==> Probing"
# 1. Backend liveness.
wait_http "$BACKEND/health" "backend /health"
# 2. Frontends serve (vite dev may take a few seconds to be ready).
wait_http "http://127.0.0.1:$KIOSK_PORT" "kiosk serves ($KIOSK_PORT)"
wait_http "http://127.0.0.1:$PORTAL_PORT" "operator portal serves ($PORTAL_PORT)"

# 3. Functional auth probe: real login (does NOT change the password) + one
#    authenticated call. Proves app + DB + auth are wired end to end.
LOGIN="$(curl -fsS -X POST "$BACKEND/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PW\"}")" \
  || fail "login request"
TOKEN="$(printf '%s' "$LOGIN" | "$PYTHON" -c 'import sys, json; print(json.load(sys.stdin)["token"])')" \
  || fail "login returned no token (is this a fresh stack with the default admin?)"
pass "login as $ADMIN_USER"
curl -fsS -o /dev/null "$BACKEND/me" -H "Authorization: Bearer $TOKEN" \
  || fail "authenticated GET /me"
pass "authenticated GET /me"

echo "==> SMOKE OK — stack comes up and the critical paths work."
```

- [ ] **Step 2: Make it executable + static check**

```bash
chmod +x scripts/smoke-full-stack.sh
shellcheck scripts/smoke-full-stack.sh
```
Expected: no warnings.

- [ ] **Step 3: Verify the probe logic against a real backend on a free port**

A full run is blocked in-session (a foreign process holds :8000). Instead prove the auth-probe logic against a real server on a FREE port, using the already-migrated test DB:
```bash
cd backend && docker compose up -d db >/dev/null 2>&1
# Bootstrap an admin in the test DB if none (idempotent-ish; ignore "exists").
BUSSOLA_DB_NAME=bussola_test BUSSOLA_ADMIN_USERNAME=smoke BUSSOLA_ADMIN_PASSWORD=smoke_dev_pw \
  .venv/bin/python -m bussola.auth.bootstrap || true
# Start a real backend on a free port against the test DB.
BUSSOLA_DB_NAME=bussola_test .venv/bin/uvicorn bussola.api.app:create_app --factory \
  --host 127.0.0.1 --port 8123 &
UV=$!; sleep 2
# Run the exact probe commands (health, login, /me) against :8123.
curl -fsS http://127.0.0.1:8123/health
TOKEN=$(curl -fsS -X POST http://127.0.0.1:8123/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"smoke","password":"smoke_dev_pw"}' | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8123/me -H "Authorization: Bearer $TOKEN"
kill "$UV"
```
Expected: `/health` returns `{"status":"ok"}`, login yields a token, `/me` returns `200`. This proves the harness's probe logic on a real server; the full run-stack orchestration is the operator's on a PC with :8000 free.

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke-full-stack.sh
git commit -m "test(dev): full-stack smoke harness (health + frontends + real login probe)"
```

---

## Self-Review

- **Spec coverage:** `/health` (Task 1), run-stack readiness (Task 2), in-process smoke (Task 3), full-stack harness (Task 4) — all spec deliverables covered.
- **Placeholders:** none; all code is concrete.
- **Type/interface consistency:** login response uses `token` + `must_change_password`; create-operator body is `{username, display_name, role}` with `role=Role.OPERATOR.value`; job request body is `{title, sector}`; audit actions are `operator_created` / `login_succeeded` / `password_changed`; all match the current source.
