# Metriche di qualità (portale operatore) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere le **metriche minime di qualità** (§7.2) al portale: un servizio/endpoint backend `GET /metrics` (ruolo supervisore, `VIEW_METRICS`, aggregato e anonimo, auditato) e un pannello supervisore sola-lettura in `operator-portal`.

**Architecture:** Fetta verticale. Backend nuovo: modulo `bussola.metrics` (`compute_metrics(conn) -> Metrics`, letture aggregate da `profiles.work_profile`/`matching.job_request`/`audit.audit_log`; nessuna nuova tabella) + router `GET /metrics` dietro `require_permission(VIEW_METRICS)` con `append_audit("metrics_viewed")`. Frontend: `operatorClient.getMetrics()` fail-closed + pannello `/metrics` (nav supervisore `built`), pattern S12–S14.

**Tech Stack:** Backend Python 3.12 (FastAPI, Pydantic, psycopg3), pytest/ruff/mypy. Frontend React 18 + Vite 5 + TS + react-i18next, Vitest + @testing-library/react. **Nessuna nuova dipendenza.**

## Global Constraints

- **Backend task** estende `backend/`; **frontend task** estendono `operator-portal/`. `frontend/` (kiosk) NON si tocca. Nessuna nuova dipendenza. **Nessuna nuova tabella/migrazione.**
- **TDD** (RED → GREEN), **solo dati sintetici**. Output test pristine.
- **Aggregato e anonimo (linea rossa §2/§5):** `Metrics` contiene **solo** conteggi/medie; **nessuno** pseudonimo, nessun campo o breakdown per-persona. Nessun endpoint per-pseudonimo.
- **`GET /metrics` dietro `require_permission(VIEW_METRICS)`** (solo ruolo `supervisor`); il server è l'autorità (403). Ogni lettura emette `append_audit(action="metrics_viewed", actor=<username>)` (§7.3).
- **Completezza (definizione stabile):** frazione di **5 sezioni-chiave** popolate — `languages`, `skills`, `experiences`, `desired_training` (array non vuoto) + `aspiration` (oggetto con almeno `fields_of_interest`, `availability` o `constraints`). `digital_literacy` e `operational_notes` NON contano. **Profilo completo** = 5/5.
- **Nessuna modifica a S4/S8** (motore colloquio/kiosk): «colloqui completati» = profili completi, derivato dal profilo salvato.
- **Frontend fail-closed**, mai un throw: Bearer via `headers(false)`; `401→'unauthorized'`, `403→'forbidden'`, rete/5xx/JSON-invalido → `'error'`. Degrado UI: `401`→`useApiError`; `403`→`t('errors.forbidden')`; rete/5xx→`t('errors.generic')`; loading gated `metrics === null && !error`.
- **i18n**: ogni stringa via `t(...)`; codice inglese.
- **Gate backend** (da `backend/`, `.venv` attiva, DB su: `docker compose up -d db`): `pytest -q && ruff check . && mypy src`. **Gate frontend** (da `operator-portal/`): `npm test && npm run typecheck && npm run lint && npm run build`.

---

### Task 1: Backend — servizio `metrics` + endpoint `GET /metrics`

**Files:**
- Create: `backend/src/bussola/metrics/__init__.py`
- Create: `backend/src/bussola/metrics/service.py`
- Create: `backend/src/bussola/api/routers/metrics.py`
- Modify: `backend/src/bussola/api/app.py`
- Create: `backend/tests/metrics/__init__.py`
- Create: `backend/tests/metrics/test_service.py`
- Create: `backend/tests/api/test_metrics_router.py`

**Interfaces:**
- Consumes: `require_permission`, `get_conn` (`bussola.api.deps`); `Permission.VIEW_METRICS` (`bussola.auth.rbac`, già dichiarato); `append_audit` (`bussola.data.audit`); `Operator` (`bussola.auth.models`); fixtures test `client`/`make_operator` (`tests/api/conftest.py`), `db`/`app_conn` (`tests/conftest.py`); `ProfileRepository` + `PiiRedactor` per seedare i profili nei test.
- Produces (usati dal frontend, Task 2): il contratto HTTP `GET /metrics` → `200 {total_profiles:int, completed_profiles:int, average_completeness:float, total_job_requests:int, matching_runs:int}` | 401 | 403.

- [ ] **Step 1: Avvia il DB di test**

Run: `cd backend && docker compose up -d db` (i test DB si auto-skippano se Postgres non è raggiungibile — deve essere su perché RED/GREEN siano reali).

- [ ] **Step 2: Scrivi i test del servizio (`tests/metrics/test_service.py`)**

Crea `backend/tests/metrics/__init__.py` (vuoto) e:
```python
import psycopg
import pytest

from bussola.data.audit import append_audit
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.metrics.service import compute_metrics
from bussola.profile.enums import EvidenceGrade, LanguageLevel, SkillKind
from bussola.profile.models import (
    Aspiration,
    DesiredTraining,
    LanguageKnown,
    Skill,
    WorkExperience,
    WorkProfile,
)

pytestmark = pytest.mark.usefixtures("db")


def _complete(pid: str) -> WorkProfile:
    return WorkProfile(
        pseudonym_id=pid,
        languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
        skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        experiences=[WorkExperience(role="Aiuto cuoco", sector="Ristorazione", duration_months=12)],
        aspiration=Aspiration(fields_of_interest=["Ristorazione"]),
        desired_training=[DesiredTraining(topic="HACCP")],
    )


def test_zero_profiles_gives_zeroed_metrics(app_conn: psycopg.Connection):
    m = compute_metrics(app_conn)
    assert (m.total_profiles, m.completed_profiles, m.average_completeness) == (0, 0, 0.0)
    assert (m.total_job_requests, m.matching_runs) == (0, 0)


def test_mixed_profiles_counts_and_average(app_conn: psycopg.Connection):
    repo = ProfileRepository(app_conn, PiiRedactor())
    repo.save(_complete("P-C"))
    repo.save(  # 1 sezione-chiave su 5 → 0.2
        WorkProfile(
            pseudonym_id="P-P",
            skills=[Skill(name="X", kind=SkillKind.SOFT, evidence=EvidenceGrade.STATED)],
        )
    )
    m = compute_metrics(app_conn)
    assert m.total_profiles == 2
    assert m.completed_profiles == 1
    assert m.average_completeness == pytest.approx((1.0 + 0.2) / 2)


def test_context_counts(app_conn: psycopg.Connection):
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matching.job_request (title, sector, created_by) VALUES (%s, %s, %s)",
            ("Aiuto cuoco", "Ristorazione", "op1"),
        )
    append_audit(app_conn, action="matching_run", actor="op1")
    append_audit(app_conn, action="matching_run", actor="op1")
    m = compute_metrics(app_conn)
    assert m.total_job_requests == 1
    assert m.matching_runs == 2
```

- [ ] **Step 3: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/metrics/test_service.py`
Expected: FAIL (`bussola.metrics` non esiste).

- [ ] **Step 4: Implementa il servizio (`metrics/service.py`)**

Crea `backend/src/bussola/metrics/__init__.py` (vuoto) e `backend/src/bussola/metrics/service.py`:
```python
"""Quality metrics: aggregate + anonymous (§7.2). No per-person data (§2)."""

from __future__ import annotations

from typing import Any

import psycopg
from pydantic import BaseModel

# The 4 list-valued key sections; `aspiration` is the 5th (an object).
_ARRAY_SECTIONS = ("languages", "skills", "experiences", "desired_training")
_TOTAL_SECTIONS = 5


class Metrics(BaseModel):
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
        profiles: list[dict[str, Any]] = [row[0] for row in cur.fetchall()]
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
```

- [ ] **Step 5: Esegui i test del servizio — devono passare**

Run: `cd backend && pytest -q tests/metrics/test_service.py`
Expected: PASS (3 test).

- [ ] **Step 6: Scrivi i test dell'endpoint (`tests/api/test_metrics_router.py`)**

```python
import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, LanguageLevel, SkillKind
from bussola.profile.models import (
    Aspiration,
    DesiredTraining,
    LanguageKnown,
    Skill,
    WorkExperience,
    WorkProfile,
)

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_supervisor_gets_aggregate_metrics(client, make_operator, app_conn: psycopg.Connection):
    ProfileRepository(app_conn, PiiRedactor()).save(
        WorkProfile(
            pseudonym_id="P-C",
            languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
            skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
            experiences=[WorkExperience(role="Aiuto cuoco", sector="Ristorazione", duration_months=12)],
            aspiration=Aspiration(fields_of_interest=["Ristorazione"]),
            desired_training=[DesiredTraining(topic="HACCP")],
        )
    )
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    r = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_profiles"] == 1
    assert body["completed_profiles"] == 1
    assert body["average_completeness"] == 1.0
    # §2/§5: aggregate only — no per-person data in the response
    assert "pseudonym_id" not in body and "profiles" not in body


def test_operator_role_is_forbidden(client, make_operator):
    user, temp = make_operator("op1", Role.OPERATOR)
    token = _login(client, user, temp)
    r = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_metrics_view_is_audited(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym FROM audit.audit_log "
            "WHERE action = 'metrics_viewed' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == user
    assert row[1] is None
```

- [ ] **Step 7: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/api/test_metrics_router.py`
Expected: FAIL (rotta `/metrics` inesistente → 404).

- [ ] **Step 8: Implementa il router (`api/routers/metrics.py`) e registralo**

Crea `backend/src/bussola/api/routers/metrics.py`:
```python
"""Quality-metrics endpoint (supervisor role). Aggregate + anonymous (§2/§7.2)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.metrics.service import Metrics, compute_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])
_view = require_permission(Permission.VIEW_METRICS)


@router.get("", response_model=Metrics)
def get_metrics(
    operator: Operator = Depends(_view),
    conn: psycopg.Connection = Depends(get_conn),
) -> Metrics:
    metrics = compute_metrics(conn)
    append_audit(conn, action="metrics_viewed", actor=operator.username, target_pseudonym=None)
    return metrics
```
In `backend/src/bussola/api/app.py`: aggiungi l'import `from bussola.api.routers import metrics as metrics_router` (in ordine alfabetico tra gli import dei router) e `app.include_router(metrics_router.router)` (dopo `profiles_router`).

- [ ] **Step 9: Esegui i test dell'endpoint — devono passare**

Run: `cd backend && pytest -q tests/api/test_metrics_router.py`
Expected: PASS (3 test).

- [ ] **Step 10: Gate backend completo**

Run: `cd backend && pytest -q && ruff check . && mypy src`
Expected: tutto verde.

- [ ] **Step 11: Commit**

```bash
git add backend/src/bussola/metrics backend/src/bussola/api/routers/metrics.py backend/src/bussola/api/app.py backend/tests/metrics backend/tests/api/test_metrics_router.py
git commit -m "feat(metrics): aggregate quality metrics service + GET /metrics (VIEW_METRICS, audited)"
```

---

### Task 2: Frontend — client `getMetrics` + tipi + i18n + fake

**Files:**
- Modify: `operator-portal/src/types.ts` (append)
- Modify: `operator-portal/src/api/operatorClient.ts` (aggiungi `getMetrics` + export)
- Modify: `operator-portal/src/test/fakeClient.ts` (fixture + opts + counter + metodo)
- Modify: `operator-portal/src/i18n/locales/it.ts` (gruppo `metrics`)
- Modify: `operator-portal/src/api/operatorClient.test.ts` (append)

**Interfaces:**
- Consumes: `headers`, `BASE` (`operatorClient.ts`); pattern fake S14.
- Produces (Task 3/4): `Metrics {total_profiles, completed_profiles, average_completeness, total_job_requests, matching_runs}` (numeri); `MetricsResult` (`ok{metrics}` | `unauthorized` | `forbidden` | `error`); `OperatorClient.getMetrics()`; fake `METRICS`, opt `metrics`, counter `calls.metrics`; i18n gruppo `metrics.*`.

- [ ] **Step 1: Scrivi il test del client (append a `operatorClient.test.ts`)**

```ts
test('getMetrics: 200→ok with Bearer; 403→forbidden; network→error', async () => {
  setToken('tok')
  const M = { total_profiles: 1, completed_profiles: 1, average_completeness: 1, total_job_requests: 0, matching_runs: 0 }
  const f = vi.fn().mockResolvedValue(res(200, M))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.getMetrics()).toEqual({ status: 'ok', metrics: M })
  expect(String(f.mock.calls[0][0])).toMatch(/\/metrics$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.getMetrics()).toEqual({ status: 'forbidden' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.getMetrics()).toEqual({ status: 'error' })
})
```

- [ ] **Step 2: Esegui — deve fallire**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: FAIL (`getMetrics` non esiste).

- [ ] **Step 3: Aggiungi i tipi (`types.ts`)**

Append:
```ts
export interface Metrics {
  total_profiles: number
  completed_profiles: number
  average_completeness: number
  total_job_requests: number
  matching_runs: number
}
export type MetricsResult =
  | { status: 'ok'; metrics: Metrics }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
```
Estendi l'interfaccia `OperatorClient` (dopo `resetPassword`):
```ts
  getMetrics(): Promise<MetricsResult>
```

- [ ] **Step 4: Implementa `getMetrics` (`operatorClient.ts`)**

Aggiungi ai tipi importati: `Metrics, MetricsResult`. Prima dell'export `operatorClient`:
```ts
async function getMetrics(): Promise<MetricsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/metrics`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', metrics: (await res.json()) as Metrics }
  } catch {
    return { status: 'error' }
  }
}
```
Aggiungi `getMetrics` al literal `export const operatorClient`.

- [ ] **Step 5: Estendi il fake (`test/fakeClient.ts`)**

Aggiungi il tipo importato `MetricsResult` e `Metrics`. Aggiungi la fixture (dopo `PROFILE`):
```ts
export const METRICS: Metrics = {
  total_profiles: 5, completed_profiles: 3, average_completeness: 0.6, total_job_requests: 2, matching_runs: 4,
}
```
Nella firma `opts` aggiungi `metrics?: MetricsResult`; nei `calls` aggiungi `metrics: number` (inizializza `metrics: 0`); aggiungi il metodo:
```ts
    async getMetrics() {
      calls.metrics++
      return opts.metrics ?? { status: 'ok', metrics: METRICS }
    },
```

- [ ] **Step 6: Aggiungi le stringhe i18n (`i18n/locales/it.ts`)**

Nuovo gruppo `metrics` (dopo `operators`):
```ts
  metrics: {
    title: 'Metriche di qualità',
    totalProfiles: 'Profili totali',
    completedProfiles: 'Colloqui completati',
    averageCompleteness: 'Completezza media',
    totalJobRequests: 'Richieste di lavoro',
    matchingRuns: 'Matching eseguiti',
  },
```

- [ ] **Step 7: Esegui il test del client + gate**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts && npm run typecheck && npm run lint`
Expected: PASS, pristine.

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/types.ts operator-portal/src/api/operatorClient.ts operator-portal/src/api/operatorClient.test.ts operator-portal/src/test/fakeClient.ts operator-portal/src/i18n/locales/it.ts
git commit -m "feat(operator-portal): metrics client (getMetrics) + types + i18n"
```

---

### Task 3: Frontend — `MetricsPanel`

**Files:**
- Create: `operator-portal/src/screens/metrics/MetricsPanel.tsx`
- Create: `operator-portal/src/screens/metrics/MetricsPanel.test.tsx`
- Modify: `operator-portal/src/styles/theme.css` (append)

**Interfaces:**
- Consumes: `useAuth().client.getMetrics()`, `useApiError`, i18n `metrics.*` + `errors.*` + `common.loading` (Task 2).
- Produces (Task 4): `MetricsPanel` (default della rotta `/metrics`).

- [ ] **Step 1: Scrivi i test (`MetricsPanel.test.tsx`)**

```tsx
import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { MetricsPanel } from './MetricsPanel'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/metrics" element={<MetricsPanel />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function supervisor(metrics: unknown) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, metrics: metrics as never })
}

test('renders the five metrics, completeness as a percentage', async () => {
  setToken('tok')
  const client = supervisor({ status: 'ok', metrics: { total_profiles: 5, completed_profiles: 3, average_completeness: 0.6, total_job_requests: 2, matching_runs: 4 } })
  renderWithProviders(harness(), { client, route: '/metrics' })
  expect(await screen.findByText('60%')).toBeInTheDocument()
  expect(screen.getByText('Profili totali')).toBeInTheDocument()
  expect(screen.getByText('5')).toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
})

test('403 shows the forbidden error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'forbidden' }), route: '/metrics' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'unauthorized' }), route: '/metrics' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})

test('network error shows the retryable message', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'error' }), route: '/metrics' })
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/screens/metrics/MetricsPanel.test.tsx`
Expected: FAIL (modulo inesistente).

- [ ] **Step 3: Implementa `MetricsPanel.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { Metrics } from '../../types'

export function MetricsPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void client.getMetrics().then((r) => {
      if (!active) return
      if (r.status === 'ok') setMetrics(r.metrics)
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
    <div className="metrics">
      <h1>{t('metrics.title')}</h1>
      {error && <p className="error" role="alert">{error}</p>}
      {metrics === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        metrics && (
          <div className="metric-cards">
            <div className="metric-card"><span className="metric-value">{metrics.total_profiles}</span><span className="metric-label">{t('metrics.totalProfiles')}</span></div>
            <div className="metric-card"><span className="metric-value">{metrics.completed_profiles}</span><span className="metric-label">{t('metrics.completedProfiles')}</span></div>
            <div className="metric-card"><span className="metric-value">{Math.round(metrics.average_completeness * 100)}%</span><span className="metric-label">{t('metrics.averageCompleteness')}</span></div>
            <div className="metric-card"><span className="metric-value">{metrics.total_job_requests}</span><span className="metric-label">{t('metrics.totalJobRequests')}</span></div>
            <div className="metric-card"><span className="metric-value">{metrics.matching_runs}</span><span className="metric-label">{t('metrics.matchingRuns')}</span></div>
          </div>
        )
      )}
    </div>
  )
}
```

- [ ] **Step 4: Aggiungi le classi CSS (`styles/theme.css`)**

Append:
```css
.metric-cards { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; }
.metric-card { display: flex; flex-direction: column; gap: 4px; border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; min-width: 150px; }
.metric-value { font-size: 28px; font-weight: 800; }
.metric-label { color: var(--muted); font-size: 13px; }
```

- [ ] **Step 5: Esegui i test + gate**

Run: `cd operator-portal && npx vitest run src/screens/metrics/MetricsPanel.test.tsx && npm run typecheck && npm run lint`
Expected: PASS, pristine.

- [ ] **Step 6: Commit**

```bash
git add operator-portal/src/screens/metrics/MetricsPanel.tsx operator-portal/src/screens/metrics/MetricsPanel.test.tsx operator-portal/src/styles/theme.css
git commit -m "feat(operator-portal): supervisor metrics panel (read-only)"
```

---

### Task 4: Frontend — nav «Metriche» reale + rotta `/metrics` + integrazione

**Files:**
- Modify: `operator-portal/src/rbac/nav.ts` (`metrics` → `built: true`)
- Modify: `operator-portal/src/App.tsx` (rotta `/metrics`)
- Modify: `operator-portal/src/shell/Nav.test.tsx` (aggiungi test supervisore)
- Modify: `operator-portal/src/App.test.tsx` (supervisore raggiunge la sezione)

**Interfaces:**
- Consumes: `MetricsPanel` (Task 3); `NAV_BY_ROLE` (`rbac/nav`).
- Produces: rotta `/metrics` funzionante per il supervisore.

- [ ] **Step 1: Aggiungi il test della Nav (`Nav.test.tsx`)**

Append (NON sostituire i test esistenti):
```tsx
test('supervisor sees «Metriche» as a real link; «Attività operatori» stays disabled', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Metriche/ })).toHaveAttribute('href', '/metrics')
  expect(screen.queryByRole('link', { name: /Attività operatori/ })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Aggiungi il test d'integrazione (`App.test.tsx`)**

Append:
```tsx
test('an authenticated supervisor can reach the metrics section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  renderApp(client, '/metrics')
  // «Profili totali» is rendered only by MetricsPanel → proves the route mounted
  expect(await screen.findByText('Profili totali')).toBeInTheDocument()
})
```

- [ ] **Step 3: Esegui — l'integrazione deve fallire**

Run: `cd operator-portal && npx vitest run src/App.test.tsx src/shell/Nav.test.tsx`
Expected: FAIL (rotta `/metrics` assente → redirect a `/`; nav non ancora link).

- [ ] **Step 4: Marca la voce di nav `built` (`rbac/nav.ts`)**

Nel blocco `supervisor`, cambia la riga `metrics`:
```ts
    { path: '/metrics', labelKey: 'nav.metrics', built: true },
```

- [ ] **Step 5: Aggancia la rotta (`App.tsx`)**

Import: `import { MetricsPanel } from './screens/metrics/MetricsPanel'`. Dentro il blocco `<Route path="/" …>`, dopo `operators`, aggiungi:
```tsx
        <Route path="metrics" element={<MetricsPanel />} />
```

- [ ] **Step 6: Esegui i test — devono passare**

Run: `cd operator-portal && npx vitest run src/App.test.tsx src/shell/Nav.test.tsx`
Expected: PASS.

- [ ] **Step 7: Gate frontend completo + build**

Run: `cd operator-portal && npm test && npm run typecheck && npm run lint && npm run build`
Expected: tutto verde, pristine.

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/rbac/nav.ts operator-portal/src/App.tsx operator-portal/src/shell/Nav.test.tsx operator-portal/src/App.test.tsx
git commit -m "feat(operator-portal): wire metrics section route + real nav link"
```

---

## Self-Review

- **Spec coverage:** §2 obiettivi → servizio+endpoint (T1), tipi+client+i18n (T2), pannello (T3), nav+rotta (T4). Aggregato/anonimo: `Metrics` senza pseudonimi (test lo verifica). VIEW_METRICS + 403 + `metrics_viewed` (T1). Completezza = 5 sezioni-chiave (T1). Nessuna modifica a S4/S8; nessuna tabella nuova.
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto.
- **Type consistency:** `Metrics` ha gli stessi 5 campi in backend (`service.py`), contratto HTTP, `types.ts`, fake e pannello. `MetricsResult.metrics` usato da client→fake→pannello. `average_completeness` è 0–1 (backend) e reso come `Math.round(x*100)%` (pannello). `compute_metrics(conn)` consumato solo dal router.
- **Degrado/privacy:** loading gated `metrics === null && !error` (pattern S13/S14); risposta senza dati per-persona (test backend + struttura `Metrics`); accesso auditato.
