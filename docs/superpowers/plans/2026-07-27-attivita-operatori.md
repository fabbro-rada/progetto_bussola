# Attività operatori (Supervisore) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La vista «attività operatori» per il Supervisore (§6): un endpoint `GET /operator-activity` (`VIEW_OPERATOR_ACTIVITY`, aggregato dall'audit, auditato) + un pannello supervisore sola-lettura con il riepilogo per operatore.

**Architecture:** Fetta verticale come S15. Backend nuovo: `bussola.activity` (`compute_operator_activity` aggrega `audit.audit_log` per `actor` sulle azioni di lavoro) + router `GET /operator-activity` dietro `VIEW_OPERATOR_ACTIVITY` con `append_audit("operator_activity_viewed")`. Frontend: `operatorClient.getOperatorActivity()` fail-closed + `OperatorActivityPanel` (nav «Attività operatori» `built`). Nessuna nuova tabella.

**Tech Stack:** Backend Python 3.12 (FastAPI, Pydantic, psycopg3), pytest/ruff/mypy. Frontend React 18 + Vite 5 + TS + react-i18next, Vitest + @testing-library/react. **Nessuna nuova dipendenza.**

## Global Constraints

- **Backend task** estende `backend/`; **frontend task** estendono `operator-portal/`. `frontend/` (kiosk) NON si tocca. Nessuna nuova dipendenza. **Nessuna nuova tabella/migrazione.**
- **TDD** (RED → GREEN), **solo dati sintetici**. Output test pristine.
- **Aggregato e anonimo (linea rossa §2/§5):** `OperatorActivity` contiene **solo** username dello staff + conteggi + timestamp; **nessuno pseudonimo, nessun dato/inferenza sulla persona detenuta**.
- **Azioni di lavoro contate:** esattamente `profile_viewed`, `profiles_searched`, `matching_run`, `export_requested`, `export_downloaded`. Il `GROUP BY actor` su queste esclude per costruzione kiosk (`interview_section_confirmed`/`actor="kiosk"`), auth (login/logout/password_changed) e le azioni admin/supervisore.
- **`GET /operator-activity` dietro `require_permission(VIEW_OPERATOR_ACTIVITY)`** (solo `supervisor`; server autorità → 403); ogni lettura emette `append_audit(action="operator_activity_viewed", actor=<username>)` (§7.3). **Distinto dall'Auditor:** nessun accesso al log grezzo né alla tamper-verify.
- **Frontend fail-closed**, mai un throw: Bearer via `headers(false)`; `401→'unauthorized'`, `403→'forbidden'`, rete/5xx/JSON-invalido → `'error'`. Degrado: `401`→`useApiError`; `403`→`t('errors.forbidden')`; rete/5xx→`t('errors.generic')`; loading gated `activity === null && !error`.
- **i18n**: ogni stringa via `t(...)`; `nav.activity` = «Attività operatori» esiste già. Nav-label == titolo pagina → i test d'integrazione interrogano per contenuto proprio (header colonna), non per il titolo.
- **DB attivo** per i test: `docker compose up -d db`.
- **Gate backend** (da `backend/`, `.venv`): `pytest -q && ruff check . && mypy src`. **Gate frontend** (da `operator-portal/`): `npm test && npm run typecheck && npm run lint && npm run build`.

---

### Task 1: Backend — servizio `activity` + endpoint `GET /operator-activity`

**Files:**
- Create: `backend/src/bussola/activity/__init__.py`
- Create: `backend/src/bussola/activity/service.py`
- Create: `backend/src/bussola/api/routers/activity.py`
- Modify: `backend/src/bussola/api/app.py`
- Create: `backend/tests/activity/__init__.py`
- Create: `backend/tests/activity/test_service.py`
- Create: `backend/tests/api/test_activity_router.py`

**Interfaces:**
- Consumes: `require_permission`, `get_conn` (`bussola.api.deps`); `Permission.VIEW_OPERATOR_ACTIVITY` (`bussola.auth.rbac`, già dichiarato + mappato al supervisore); `append_audit` (`bussola.data.audit`); `Operator` (`bussola.auth.models`); fixtures test `client`/`make_operator` (`tests/api/conftest.py`), `db`/`app_conn` (`tests/conftest.py`).
- Produces (frontend, Task 2): contratto `GET /operator-activity` → `200 OperatorActivity[]`, `OperatorActivity = {actor, profiles_viewed, profiles_searched, matchings_run, exports_requested, exports_downloaded, last_active}` | 401 | 403.

- [ ] **Step 1: Avvia il DB di test**

Run: `cd backend && docker compose up -d db` (idempotente).

- [ ] **Step 2: Scrivi i test del servizio (`tests/activity/test_service.py`)**

Crea `backend/tests/activity/__init__.py` (vuoto) e:
```python
import psycopg
import pytest

from bussola.activity.service import compute_operator_activity
from bussola.data.audit import append_audit

pytestmark = pytest.mark.usefixtures("db")


def test_no_events_gives_empty_list(app_conn: psycopg.Connection):
    assert compute_operator_activity(app_conn) == []


def test_counts_work_actions_per_actor_and_excludes_non_work(app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-2")
    append_audit(app_conn, action="matching_run", actor="op1")
    append_audit(app_conn, action="profiles_searched", actor="op2")
    # non-work / other-role / kiosk events must NOT create rows or counts
    append_audit(app_conn, action="login_succeeded", actor="op1")
    append_audit(app_conn, action="operator_created", actor="admin")
    append_audit(app_conn, action="interview_section_confirmed", actor="kiosk", target_pseudonym="P-1")

    rows = {a.actor: a for a in compute_operator_activity(app_conn)}
    assert set(rows) == {"op1", "op2"}  # admin/kiosk absent (no work actions)
    assert rows["op1"].profiles_viewed == 2
    assert rows["op1"].matchings_run == 1
    assert rows["op1"].profiles_searched == 0
    assert rows["op1"].exports_requested == 0 and rows["op1"].exports_downloaded == 0
    assert rows["op2"].profiles_searched == 1
    assert rows["op1"].last_active is not None


def test_context_exports_counted(app_conn: psycopg.Connection):
    append_audit(app_conn, action="export_requested", actor="op3")
    append_audit(app_conn, action="export_downloaded", actor="op3")
    a = compute_operator_activity(app_conn)[0]
    assert a.actor == "op3"
    assert a.exports_requested == 1 and a.exports_downloaded == 1
```

- [ ] **Step 3: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/activity/test_service.py`
Expected: FAIL (`bussola.activity` non esiste).

- [ ] **Step 4: Implementa il servizio (`activity/service.py`)**

Crea `backend/src/bussola/activity/__init__.py` (vuoto) e `backend/src/bussola/activity/service.py`:
```python
"""Operator-activity summary for the supervisor (§6): aggregate work-action
counts per actor from the audit log. Aggregate + staff-only, no PII (§2)."""

from __future__ import annotations

from datetime import datetime

import psycopg
from pydantic import BaseModel, ConfigDict

_WORK_ACTIONS = ("profile_viewed", "profiles_searched", "matching_run", "export_requested", "export_downloaded")


class OperatorActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str
    profiles_viewed: int
    profiles_searched: int
    matchings_run: int
    exports_requested: int
    exports_downloaded: int
    last_active: datetime


def compute_operator_activity(conn: psycopg.Connection) -> list[OperatorActivity]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT actor, "
            "COUNT(*) FILTER (WHERE action = 'profile_viewed'), "
            "COUNT(*) FILTER (WHERE action = 'profiles_searched'), "
            "COUNT(*) FILTER (WHERE action = 'matching_run'), "
            "COUNT(*) FILTER (WHERE action = 'export_requested'), "
            "COUNT(*) FILTER (WHERE action = 'export_downloaded'), "
            "MAX(occurred_at) "
            "FROM audit.audit_log "
            "WHERE actor IS NOT NULL AND action = ANY(%s) "
            "GROUP BY actor "
            "ORDER BY MAX(occurred_at) DESC",
            (list(_WORK_ACTIONS),),
        )
        rows = cur.fetchall()
    return [
        OperatorActivity(
            actor=r[0],
            profiles_viewed=int(r[1]),
            profiles_searched=int(r[2]),
            matchings_run=int(r[3]),
            exports_requested=int(r[4]),
            exports_downloaded=int(r[5]),
            last_active=r[6],
        )
        for r in rows
    ]
```

- [ ] **Step 5: Esegui i test del servizio — devono passare**

Run: `cd backend && pytest -q tests/activity/test_service.py`
Expected: PASS (3 test).

- [ ] **Step 6: Scrivi i test dell'endpoint (`tests/api/test_activity_router.py`)**

```python
import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.audit import append_audit

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_supervisor_gets_operator_activity(client, make_operator, app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    r = client.get("/operator-activity", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert any(row["actor"] == "op1" and row["profiles_viewed"] == 1 for row in body)
    # aggregate only — no per-person data
    assert all("pseudonym_id" not in row for row in body)


def test_operator_and_auditor_are_forbidden(client, make_operator):
    for name, role in [("op1", Role.OPERATOR), ("aud1", Role.AUDITOR)]:
        user, temp = make_operator(name, role)
        token = _login(client, user, temp)
        assert client.get("/operator-activity", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_view_is_audited(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    client.get("/operator-activity", headers={"Authorization": f"Bearer {token}"})
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor FROM audit.audit_log WHERE action = 'operator_activity_viewed' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None and row[0] == user
```

- [ ] **Step 7: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/api/test_activity_router.py`
Expected: FAIL (rotta inesistente → 404).

- [ ] **Step 8: Implementa il router (`api/routers/activity.py`) e registralo**

Crea `backend/src/bussola/api/routers/activity.py`:
```python
"""Operator-activity endpoint (supervisor role). Aggregate + staff-only (§2/§6)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.activity.service import OperatorActivity, compute_operator_activity
from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit

router = APIRouter(prefix="/operator-activity", tags=["activity"])
_view = require_permission(Permission.VIEW_OPERATOR_ACTIVITY)


@router.get("", response_model=list[OperatorActivity])
def get_operator_activity(
    operator: Operator = Depends(_view),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[OperatorActivity]:
    activity = compute_operator_activity(conn)
    append_audit(conn, action="operator_activity_viewed", actor=operator.username, target_pseudonym=None)
    return activity
```
In `backend/src/bussola/api/app.py`: aggiungi `from bussola.api.routers import activity as activity_router` (in ordine alfabetico, prima di `audit`) e `app.include_router(activity_router.router)`.

- [ ] **Step 9: Esegui i test dell'endpoint — devono passare**

Run: `cd backend && pytest -q tests/api/test_activity_router.py`
Expected: PASS (3 test).

- [ ] **Step 10: Gate backend completo**

Run: `cd backend && pytest -q && ruff check . && mypy src`
Expected: tutto verde.

- [ ] **Step 11: Commit**

```bash
git add backend/src/bussola/activity backend/src/bussola/api/routers/activity.py backend/src/bussola/api/app.py backend/tests/activity backend/tests/api/test_activity_router.py
git commit -m "feat(activity): operator-activity summary service + GET /operator-activity (VIEW_OPERATOR_ACTIVITY, audited)"
```

---

### Task 2: Frontend — client `getOperatorActivity` + tipi + i18n + fake

**Files:**
- Modify: `operator-portal/src/types.ts` (append)
- Modify: `operator-portal/src/api/operatorClient.ts` (metodo + export)
- Modify: `operator-portal/src/test/fakeClient.ts` (fixture + opt + counter + metodo)
- Modify: `operator-portal/src/i18n/locales/it.ts` (gruppo `activity`)
- Modify: `operator-portal/src/api/operatorClient.test.ts` (append)

**Interfaces:**
- Consumes: `headers`/`BASE` (`operatorClient.ts`); pattern fake S15.
- Produces (Task 3/4): `OperatorActivity {actor:string, profiles_viewed:number, profiles_searched:number, matchings_run:number, exports_requested:number, exports_downloaded:number, last_active:string}`; `OperatorActivityResult` (`ok{activity}` | unauthorized | forbidden | error); `OperatorClient.getOperatorActivity()`; fake `ACTIVITY` fixture, opt `activity`, counter `calls.activity`; i18n gruppo `activity.*`.

- [ ] **Step 1: Scrivi il test del client (append a `operatorClient.test.ts`)**

```ts
test('getOperatorActivity: 200→ok with Bearer; 403→forbidden; network→error', async () => {
  setToken('tok')
  const A = [{ actor: 'op1', profiles_viewed: 2, profiles_searched: 1, matchings_run: 0, exports_requested: 0, exports_downloaded: 0, last_active: '2026-07-27T10:00:00Z' }]
  const f = vi.fn().mockResolvedValue(res(200, A))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.getOperatorActivity()).toEqual({ status: 'ok', activity: A })
  expect(String(f.mock.calls[0][0])).toMatch(/\/operator-activity$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.getOperatorActivity()).toEqual({ status: 'forbidden' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.getOperatorActivity()).toEqual({ status: 'error' })
})
```

- [ ] **Step 2: Esegui — deve fallire**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: FAIL (`getOperatorActivity` non esiste).

- [ ] **Step 3: Aggiungi i tipi (`types.ts`)**

Append:
```ts
export interface OperatorActivity {
  actor: string
  profiles_viewed: number
  profiles_searched: number
  matchings_run: number
  exports_requested: number
  exports_downloaded: number
  last_active: string
}
export type OperatorActivityResult =
  | { status: 'ok'; activity: OperatorActivity[] }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
```
Estendi `OperatorClient` (dopo `verifyAudit`):
```ts
  getOperatorActivity(): Promise<OperatorActivityResult>
```

- [ ] **Step 4: Implementa `getOperatorActivity` (`operatorClient.ts`)**

Aggiungi ai tipi importati: `OperatorActivity, OperatorActivityResult`. Prima dell'export `operatorClient`:
```ts
async function getOperatorActivity(): Promise<OperatorActivityResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operator-activity`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', activity: (await res.json()) as OperatorActivity[] }
  } catch {
    return { status: 'error' }
  }
}
```
Aggiungi `getOperatorActivity` al literal `export const operatorClient`.

- [ ] **Step 5: Esegui il test del client — deve passare**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: PASS.

- [ ] **Step 6: Estendi il fake (`test/fakeClient.ts`)**

Importa i tipi: `OperatorActivity, OperatorActivityResult`. Aggiungi la fixture (dopo `AUDIT_ENTRY`):
```ts
export const ACTIVITY: OperatorActivity[] = [
  { actor: 'm.rossi', profiles_viewed: 4, profiles_searched: 2, matchings_run: 1, exports_requested: 1, exports_downloaded: 0, last_active: '2026-07-27T10:00:00Z' },
]
```
Nella firma `opts` aggiungi `activity?: OperatorActivityResult`; nei `calls` aggiungi `activity: number` (init 0); aggiungi il metodo:
```ts
    async getOperatorActivity() {
      calls.activity++
      return opts.activity ?? { status: 'ok', activity: ACTIVITY }
    },
```

- [ ] **Step 7: Aggiungi le stringhe i18n (`i18n/locales/it.ts`)**

Nuovo gruppo `activity` (dopo `audit`):
```ts
  activity: {
    title: 'Attività operatori',
    empty: 'Nessuna attività registrata.',
    colOperator: 'Operatore',
    colProfilesViewed: 'Profili consultati',
    colSearches: 'Ricerche',
    colMatchings: 'Matching',
    colExports: 'Export (rich./scar.)',
    colLastActive: 'Ultima attività',
  },
```
(`nav.activity` = «Attività operatori» esiste già.)

- [ ] **Step 8: Gate + commit**

Run: `cd operator-portal && npm test && npm run typecheck && npm run lint`
```bash
git add operator-portal/src/types.ts operator-portal/src/api/operatorClient.ts operator-portal/src/api/operatorClient.test.ts operator-portal/src/test/fakeClient.ts operator-portal/src/i18n/locales/it.ts
git commit -m "feat(operator-portal): operator-activity client + types + i18n"
```

---

### Task 3: Frontend — `OperatorActivityPanel`

**Files:**
- Create: `operator-portal/src/screens/activity/OperatorActivityPanel.tsx`
- Create: `operator-portal/src/screens/activity/OperatorActivityPanel.test.tsx`

**Interfaces:**
- Consumes: `useAuth().client.getOperatorActivity()`, `useApiError`, i18n `activity.*` + `errors.*` + `common.loading`; `OperatorActivity`.
- Produces (Task 4): `OperatorActivityPanel` (default della rotta `/activity`).

- [ ] **Step 1: Scrivi i test (`OperatorActivityPanel.test.tsx`)**

```tsx
import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { OperatorActivityPanel } from './OperatorActivityPanel'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/activity" element={<OperatorActivityPanel />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function supervisor(activity: unknown) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, activity: activity as never })
}

test('renders a row per operator with the work-action counts', async () => {
  setToken('tok')
  const client = supervisor({ status: 'ok', activity: [
    { actor: 'm.rossi', profiles_viewed: 4, profiles_searched: 2, matchings_run: 1, exports_requested: 1, exports_downloaded: 0, last_active: '2026-07-27T10:00:00Z' },
  ] })
  renderWithProviders(harness(), { client, route: '/activity' })
  expect(await screen.findByText('m.rossi')).toBeInTheDocument()
  expect(screen.getByText('4')).toBeInTheDocument()   // profiles_viewed
  expect(screen.getByText('Profili consultati')).toBeInTheDocument()
})

test('empty state when there is no activity', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'ok', activity: [] }), route: '/activity' })
  expect(await screen.findByText('Nessuna attività registrata.')).toBeInTheDocument()
})

test('403 shows the forbidden error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'forbidden' }), route: '/activity' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'unauthorized' }), route: '/activity' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})

test('network error shows the retryable message', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'error' }), route: '/activity' })
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/screens/activity/OperatorActivityPanel.test.tsx`
Expected: FAIL (modulo inesistente).

- [ ] **Step 3: Implementa `OperatorActivityPanel.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { OperatorActivity } from '../../types'

export function OperatorActivityPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [activity, setActivity] = useState<OperatorActivity[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void client.getOperatorActivity().then((r) => {
      if (!active) return
      if (r.status === 'ok') setActivity(r.activity)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    })
    return () => {
      active = false
    }
  }, [client, handleError, t])

  return (
    <div className="activity">
      <h1>{t('activity.title')}</h1>
      {error && <p className="error" role="alert">{error}</p>}
      {activity === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        activity &&
        (activity.length === 0 ? (
          <p>{t('activity.empty')}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t('activity.colOperator')}</th>
                <th>{t('activity.colProfilesViewed')}</th>
                <th>{t('activity.colSearches')}</th>
                <th>{t('activity.colMatchings')}</th>
                <th>{t('activity.colExports')}</th>
                <th>{t('activity.colLastActive')}</th>
              </tr>
            </thead>
            <tbody>
              {activity.map((a) => (
                <tr key={a.actor}>
                  <td>{a.actor}</td>
                  <td>{a.profiles_viewed}</td>
                  <td>{a.profiles_searched}</td>
                  <td>{a.matchings_run}</td>
                  <td>{a.exports_requested}/{a.exports_downloaded}</td>
                  <td>{a.last_active.replace('T', ' ').slice(0, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))
      )}
    </div>
  )
}
```

- [ ] **Step 4: Esegui i test + gate**

Run: `cd operator-portal && npx vitest run src/screens/activity/OperatorActivityPanel.test.tsx && npm run typecheck && npm run lint`
Expected: PASS, pristine.

- [ ] **Step 5: Commit**

```bash
git add operator-portal/src/screens/activity/OperatorActivityPanel.tsx operator-portal/src/screens/activity/OperatorActivityPanel.test.tsx
git commit -m "feat(operator-portal): supervisor operator-activity panel (read-only)"
```

---

### Task 4: Nav «Attività operatori» reale + rotta `/activity` + integrazione

**Files:**
- Modify: `operator-portal/src/rbac/nav.ts`
- Modify: `operator-portal/src/App.tsx`
- Modify: `operator-portal/src/shell/Nav.test.tsx`
- Modify: `operator-portal/src/App.test.tsx`

**Interfaces:**
- Consumes: `OperatorActivityPanel` (Task 3); `NAV_BY_ROLE`.
- Produces: rotta `/activity` funzionante per il supervisore.

- [ ] **Step 1: Aggiorna il test della Nav (`Nav.test.tsx`)**

Il test supervisore esistente (S15) asserisce che «Metriche» è un link reale e «Attività operatori» è **disabilitato**: quella seconda asserzione ora è falsa (activity diventa `built`). Aggiorna quel test perché entrambe siano link reali:
```tsx
test('supervisor sees «Metriche» and «Attività operatori» as real links', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Metriche/ })).toHaveAttribute('href', '/metrics')
  expect(await screen.findByRole('link', { name: /Attività operatori/ })).toHaveAttribute('href', '/activity')
})
```
(Se il test S15 originale aveva un nome diverso, sostituiscilo con questo; mantieni intatti gli altri test.)

- [ ] **Step 2: Aggiungi il test d'integrazione (`App.test.tsx`)**

Append (query per contenuto proprio della schermata, non per il titolo == label nav):
```tsx
test('an authenticated supervisor can reach the operator-activity section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  renderApp(client, '/activity')
  // «Profili consultati» is a column rendered only by OperatorActivityPanel → proves the route mounted
  expect(await screen.findByText('Profili consultati')).toBeInTheDocument()
})
```

- [ ] **Step 3: Esegui — i test devono fallire**

Run: `cd operator-portal && npx vitest run src/App.test.tsx src/shell/Nav.test.tsx`
Expected: FAIL (rotta `/activity` assente; «Attività operatori» non ancora link).

- [ ] **Step 4: Marca la voce di nav `built` (`rbac/nav.ts`)**

Nel blocco `supervisor`, cambia la riga `activity`:
```ts
    { path: '/activity', labelKey: 'nav.activity', built: true },
```

- [ ] **Step 5: Aggancia la rotta (`App.tsx`)**

Import: `import { OperatorActivityPanel } from './screens/activity/OperatorActivityPanel'`. Dentro il blocco `<Route path="/" …>`, dopo `audit` (o `metrics`), aggiungi:
```tsx
        <Route path="activity" element={<OperatorActivityPanel />} />
```

- [ ] **Step 6: Esegui i test — devono passare**

Run: `cd operator-portal && npx vitest run src/App.test.tsx src/shell/Nav.test.tsx`
Expected: PASS.

- [ ] **Step 7: Gate completo + build**

Run: `cd operator-portal && npm test && npm run typecheck && npm run lint && npm run build`
Expected: tutto verde, pristine.

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/rbac/nav.ts operator-portal/src/App.tsx operator-portal/src/shell/Nav.test.tsx operator-portal/src/App.test.tsx
git commit -m "feat(operator-portal): wire operator-activity route + real nav link"
```

---

## Self-Review

- **Spec coverage:** §2 obiettivi → servizio+endpoint (T1), tipi+client+i18n (T2), pannello (T3), nav+rotta (T4). Aggregato per attore sulle 5 azioni di lavoro (esclude kiosk/auth/admin/supervisore — test); VIEW_OPERATOR_ACTIVITY + 403 + `operator_activity_viewed` (T1); nessun dato per-persona (test asserisce no `pseudonym_id`). Tutti coperti.
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto.
- **Type consistency:** `OperatorActivity` ha gli stessi 7 campi in backend (`service.py`), contratto HTTP, `types.ts`, fake e pannello; `OperatorActivityResult.activity` usato client→fake→pannello; `compute_operator_activity(conn)` consumato solo dal router; `Permission.VIEW_OPERATOR_ACTIVITY` (già mappato al supervisore) consumato da T1.
- **Rossa/§6:** endpoint distinto (no riuso `/audit`); aggregato staff-only (no pseudonimi/PII); accesso auditato; loading gated `!error`; nav==titolo → test integrazione per contenuto proprio.
