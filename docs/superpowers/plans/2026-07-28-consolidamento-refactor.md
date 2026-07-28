# Consolidamento (refactor a comportamento invariato) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidare 4 duplicazioni (§14) **senza cambiare comportamento**: `SUPPORTED_LANGUAGES` unica fonte; hook `useFetchOnMount`; util `formatTimestamp`; commento `nav.ts`. Le suite esistenti restano verdi e con **asserzioni invariate**; le nuove astrazioni hanno test propri.

**Architecture:** Backend: nuovo `bussola/languages.py` (fonte unica), i 3 siti la importano (`refusal.py` la ri-esporta). Frontend: `hooks/useFetchOnMount.ts` (pattern fetch-al-mount+degrado centralizzato) usato dai 3 pannelli; `util/formatTimestamp.ts` (output identico) usato da 2 punti; commento `nav.ts` aggiornato.

**Tech Stack:** Backend Python 3.12 (pytest/ruff/mypy). Frontend React 18 + TS (Vitest + RTL). **Nessuna nuova dipendenza. Nessun cambiamento di comportamento.**

## Global Constraints

- **Comportamento invariato (§9).** Nessun cambiamento osservabile, nessun cambio al contratto HTTP/RBAC/tipi/resa. `frontend/` (kiosk) NON si tocca. Nessuna nuova dipendenza.
- **Le suite esistenti restano verdi SENZA modifiche alle asserzioni.** Se un test esistente dovesse cambiare un'asserzione per passare → **STOP**, non è più un refactor neutro: segnalare come BLOCKED. (Aggiornare un *import* alla nuova posizione canonica è mechanical e ammesso; cambiare cosa un test *asserisce* no.)
- **Le nuove astrazioni hanno test focalizzati propri** (`useFetchOnMount`, `formatTimestamp`, `languages`).
- **`formatTimestamp` produce output IDENTICO** all'attuale `iso.replace('T', ' ').slice(0, 16)` — **nessun** indicatore di fuso (resta follow-up §14).
- **`built?` di `nav.ts` resta**; si aggiorna solo il commento header.
- **Gate backend** (da `backend/`, `.venv`): `pytest -q && ruff check . && mypy src`. **Gate frontend** (da `operator-portal/`): `npm test && npm run typecheck && npm run lint && npm run build`. DB attivo per i test backend: `docker compose up -d db`.

---

### Task 1: Backend — `SUPPORTED_LANGUAGES` unica fonte

**Files:**
- Create: `backend/src/bussola/languages.py`
- Modify: `backend/src/bussola/guardrails/refusal.py`
- Modify: `backend/src/bussola/guardrails/pii.py`
- Modify: `backend/src/bussola/system/service.py`
- Create: `backend/tests/test_languages.py`

**Interfaces:**
- Produces: `bussola.languages.SUPPORTED_LANGUAGES: tuple[str, ...] = ("it","en","fr","es","ar")`; `refusal.SUPPORTED_LANGUAGES` resta importabile (re-export).
- Consumes: nulla di nuovo.

- [ ] **Step 1: Avvia il DB + baseline verde**

Run: `cd backend && docker compose up -d db && pytest -q` — deve essere già verde (baseline pre-refactor).

- [ ] **Step 2: Scrivi il test della costante (`tests/test_languages.py`)**

```python
from bussola.languages import SUPPORTED_LANGUAGES


def test_supported_languages_is_the_canonical_five():
    assert SUPPORTED_LANGUAGES == ("it", "en", "fr", "es", "ar")


def test_consumers_share_the_same_constant():
    from bussola.guardrails import refusal
    from bussola.system import service
    assert refusal.SUPPORTED_LANGUAGES is SUPPORTED_LANGUAGES
    assert service.SUPPORTED_LANGUAGES is SUPPORTED_LANGUAGES
```

- [ ] **Step 3: Esegui — deve fallire**

Run: `cd backend && pytest -q tests/test_languages.py`
Expected: FAIL (`bussola.languages` non esiste).

- [ ] **Step 4: Crea `languages.py` e deduplica i 3 siti**

Crea `backend/src/bussola/languages.py`:
```python
"""Single source of truth for the five supported languages (§8).

A dependency-free module so any layer (guardrails, system, …) can import the
constant without creating cross-package coupling."""

from __future__ import annotations

SUPPORTED_LANGUAGES: tuple[str, ...] = ("it", "en", "fr", "es", "ar")
```
In `backend/src/bussola/guardrails/refusal.py`, sostituisci la riga 7 (`SUPPORTED_LANGUAGES: tuple[str, ...] = (...)`) con un **re-export esplicito** (ruff/mypy-clean, il test `test_refusal.py` continua a importarla da qui):
```python
from bussola.languages import SUPPORTED_LANGUAGES as SUPPORTED_LANGUAGES
```
In `backend/src/bussola/guardrails/pii.py`, sostituisci la riga 45 (`_SUPPORTED_LANGUAGES = ["it", ...]`) con:
```python
from bussola.languages import SUPPORTED_LANGUAGES

_SUPPORTED_LANGUAGES = list(SUPPORTED_LANGUAGES)
```
(colloca l'import in cima al file con gli altri import; `_SUPPORTED_LANGUAGES = list(...)` resta dov'era la definizione.)
In `backend/src/bussola/system/service.py`, sostituisci la riga 18 (`SUPPORTED_LANGUAGES = (...)`) con:
```python
from bussola.languages import SUPPORTED_LANGUAGES
```
(in cima con gli altri import; le righe che usano `SUPPORTED_LANGUAGES` restano invariate.)

- [ ] **Step 5: Esegui i test — devono passare**

Run: `cd backend && pytest -q tests/test_languages.py tests/guardrails tests/system`
Expected: PASS (nuovo test + i test guardrail/system esistenti, invariati).

- [ ] **Step 6: Gate backend completo**

Run: `cd backend && pytest -q && ruff check . && mypy src`
Expected: tutto verde, nessuna asserzione esistente modificata.

- [ ] **Step 7: Commit**

```bash
git add backend/src/bussola/languages.py backend/src/bussola/guardrails/refusal.py backend/src/bussola/guardrails/pii.py backend/src/bussola/system/service.py backend/tests/test_languages.py
git commit -m "refactor(backend): single SUPPORTED_LANGUAGES source (dedup 3 copies)"
```

---

### Task 2: Frontend — hook `useFetchOnMount` + refactor dei 3 pannelli

**Files:**
- Create: `operator-portal/src/hooks/useFetchOnMount.ts`
- Create: `operator-portal/src/hooks/useFetchOnMount.test.tsx`
- Modify: `operator-portal/src/screens/metrics/MetricsPanel.tsx`
- Modify: `operator-portal/src/screens/activity/OperatorActivityPanel.tsx`
- Modify: `operator-portal/src/screens/system/SystemConfigPanel.tsx`

**Interfaces:**
- Consumes: `useApiError` (`../hooks/useApiError`), `useTranslation`; i pannelli usano `useAuth().client`.
- Produces: `useFetchOnMount<R extends {status:'ok'|'unauthorized'|'forbidden'|'error'}, T>(fetcher: () => Promise<R>, onOk: (r: Extract<R,{status:'ok'}>) => T): { data: T | null; error: string }`.

- [ ] **Step 1: Baseline verde**

Run: `cd operator-portal && npm test` — verde (baseline; in particolare i test di MetricsPanel/OperatorActivityPanel/SystemConfigPanel).

- [ ] **Step 2: Scrivi il test dell'hook (`hooks/useFetchOnMount.test.tsx`)**

```tsx
import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { setToken } from '../auth/session'
import { useAuth } from '../auth/AuthContext'
import { useFetchOnMount } from './useFetchOnMount'
import { useCallback } from 'react'

function Probe() {
  const { client } = useAuth()
  const fetcher = useCallback(() => client.getMetrics(), [client])
  const { data, error } = useFetchOnMount(fetcher, (r) => r.metrics)
  if (error) return <p>ERR:{error}</p>
  if (data === null) return <p>LOADING</p>
  return <p>OK:{data.total_profiles}</p>
}

function harness() {
  return (
    <Routes>
      <Route path="/x" element={<Probe />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

afterEach(() => sessionStorage.clear())

test('ok → exposes the selected data', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, metrics: { status: 'ok', metrics: { total_profiles: 7, completed_profiles: 0, average_completeness: 0, total_job_requests: 0, matching_runs: 0 } } })
  renderWithProviders(harness(), { client, route: '/x' })
  expect(await screen.findByText('OK:7')).toBeInTheDocument()
})

test('forbidden → error message, no stuck loading', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, metrics: { status: 'forbidden' } })
  renderWithProviders(harness(), { client, route: '/x' })
  expect(await screen.findByText('ERR:Non hai i permessi per questa azione.')).toBeInTheDocument()
})

test('unauthorized → redirect to login', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, metrics: { status: 'unauthorized' } })
  renderWithProviders(harness(), { client, route: '/x' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})
```

- [ ] **Step 3: Esegui — deve fallire**

Run: `cd operator-portal && npx vitest run src/hooks/useFetchOnMount.test.tsx`
Expected: FAIL (`useFetchOnMount` non esiste).

- [ ] **Step 4: Implementa l'hook (`hooks/useFetchOnMount.ts`)**

```ts
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useApiError } from './useApiError'

type Fetchable = { status: 'ok' | 'unauthorized' | 'forbidden' | 'error' }

// Centralizes the fetch-on-mount + degrade pattern shared by the read-only
// panels: 401 → useApiError (redirect), 403/error → i18n message, unmount guard.
export function useFetchOnMount<R extends Fetchable, T>(
  fetcher: () => Promise<R>,
  onOk: (r: Extract<R, { status: 'ok' }>) => T,
): { data: T | null; error: string } {
  const { t } = useTranslation()
  const handleError = useApiError()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const onOkRef = useRef(onOk)
  onOkRef.current = onOk

  useEffect(() => {
    let active = true
    void fetcher().then((r) => {
      if (!active) return
      if (r.status === 'ok') {
        setData(onOkRef.current(r as Extract<R, { status: 'ok' }>))
      } else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') {
          setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
        }
      }
    })
    return () => {
      active = false
    }
  }, [fetcher, handleError, t])

  return { data, error }
}
```
(NB: il `fetcher` va passato **stabile** — via `useCallback([client])` — così le deps `[fetcher, handleError, t]` restano equivalenti alle `[client, handleError, t]` originali e l'effetto non si ri-esegue a ogni render. `onOk` è tenuto in un ref: non è una dipendenza.)

- [ ] **Step 5: Refactor `MetricsPanel.tsx`**

Sostituisci l'header del componente (import + effect + state) mantenendo **identico** il JSX del return:
```tsx
import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useFetchOnMount } from '../../hooks/useFetchOnMount'

export function MetricsPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const fetchMetrics = useCallback(() => client.getMetrics(), [client])
  const { data: metrics, error } = useFetchOnMount(fetchMetrics, (r) => r.metrics)

  return (
    // ... JSX INVARIATO: usa `metrics` ed `error` esattamente come prima ...
  )
}
```
(Rimuovi gli import ora inutilizzati `useEffect`/`useState`/`useApiError` e il tipo `Metrics` se non più referenziato nel corpo.)

- [ ] **Step 6: Refactor `OperatorActivityPanel.tsx` e `SystemConfigPanel.tsx` allo stesso modo**

`OperatorActivityPanel`:
```tsx
  const fetchActivity = useCallback(() => client.getOperatorActivity(), [client])
  const { data: activity, error } = useFetchOnMount(fetchActivity, (r) => r.activity)
```
`SystemConfigPanel`:
```tsx
  const fetchConfig = useCallback(() => client.getSystemConfig(), [client])
  const { data: config, error } = useFetchOnMount(fetchConfig, (r) => r.config)
```
In entrambi: rimuovi `useEffect`/`useState`/`useApiError` non più usati; aggiungi `useCallback`; **JSX invariato** (usa `activity`/`config` ed `error` come prima). `SystemConfigPanel` mantiene l'import di `Fragment`.

- [ ] **Step 7: Esegui i test — devono passare (asserzioni esistenti invariate)**

Run: `cd operator-portal && npx vitest run src/hooks/useFetchOnMount.test.tsx src/screens/metrics src/screens/activity src/screens/system && npm run typecheck && npm run lint`
Expected: PASS. **Nessuna asserzione esistente modificata** nei test dei 3 pannelli. Se un test dei pannelli richiede una modifica → STOP (comportamento cambiato).

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/hooks/useFetchOnMount.ts operator-portal/src/hooks/useFetchOnMount.test.tsx operator-portal/src/screens/metrics/MetricsPanel.tsx operator-portal/src/screens/activity/OperatorActivityPanel.tsx operator-portal/src/screens/system/SystemConfigPanel.tsx
git commit -m "refactor(operator-portal): useFetchOnMount hook (dedup 3 read-only panels)"
```

---

### Task 3: Frontend — util `formatTimestamp` + commento `nav.ts`

**Files:**
- Create: `operator-portal/src/util/formatTimestamp.ts`
- Create: `operator-portal/src/util/formatTimestamp.test.ts`
- Modify: `operator-portal/src/screens/audit/AuditLog.tsx`
- Modify: `operator-portal/src/screens/activity/OperatorActivityPanel.tsx`
- Modify: `operator-portal/src/rbac/nav.ts`

**Interfaces:**
- Produces: `formatTimestamp(iso: string): string` = `iso.replace('T', ' ').slice(0, 16)` (identico all'attuale).

- [ ] **Step 1: Scrivi il test della util (`util/formatTimestamp.test.ts`)**

```ts
import { expect, test } from 'vitest'
import { formatTimestamp } from './formatTimestamp'

test('renders an ISO instant as «YYYY-MM-DD HH:MM» (identical to the prior inline slice)', () => {
  expect(formatTimestamp('2026-07-27T10:00:00Z')).toBe('2026-07-27 10:00')
  expect(formatTimestamp('2026-01-02T23:45:59Z')).toBe('2026-01-02 23:45')
})
```

- [ ] **Step 2: Esegui — deve fallire**

Run: `cd operator-portal && npx vitest run src/util/formatTimestamp.test.ts`
Expected: FAIL (modulo inesistente).

- [ ] **Step 3: Implementa `formatTimestamp.ts`**

```ts
// Compact display of an ISO timestamp as «YYYY-MM-DD HH:MM».
// NOTE: keeps the exact behavior of the prior inline slice (no timezone
// indicator — a TZ-aware formatter is a separate follow-up).
export function formatTimestamp(iso: string): string {
  return iso.replace('T', ' ').slice(0, 16)
}
```

- [ ] **Step 4: Applica in `AuditLog.tsx` e `OperatorActivityPanel.tsx`**

`AuditLog.tsx`: aggiungi `import { formatTimestamp } from '../../util/formatTimestamp'` e sostituisci `{e.occurred_at.replace('T', ' ').slice(0, 16)}` con `{formatTimestamp(e.occurred_at)}`.
`OperatorActivityPanel.tsx`: aggiungi lo stesso import e sostituisci `{a.last_active.replace('T', ' ').slice(0, 16)}` con `{formatTimestamp(a.last_active)}`.

- [ ] **Step 5: Aggiorna il commento header di `nav.ts`**

Sostituisci il commento header (righe ~9-12, che oggi dice «until then, items render as disabled placeholders … Once a section's screen exists, mark it `built`») con:
```ts
// UX-only nav skeleton (§6). The server remains the authority (403). Every
// section is currently built; the `built` flag stays so a future not-yet-built
// section can render as a disabled placeholder instead of a real link.
```
(Non modificare le voci: il flag `built?` e i `built: true` restano invariati.)

- [ ] **Step 6: Esegui i test — devono passare (asserzioni esistenti invariate)**

Run: `cd operator-portal && npx vitest run src/util src/screens/audit src/screens/activity && npm run typecheck && npm run lint`
Expected: PASS; i test di AuditLog/OperatorActivityPanel invariati (l'output timestamp è identico).

- [ ] **Step 7: Gate frontend completo + build**

Run: `cd operator-portal && npm test && npm run typecheck && npm run lint && npm run build`
Expected: tutto verde, pristine.

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/util/formatTimestamp.ts operator-portal/src/util/formatTimestamp.test.ts operator-portal/src/screens/audit/AuditLog.tsx operator-portal/src/screens/activity/OperatorActivityPanel.tsx operator-portal/src/rbac/nav.ts
git commit -m "refactor(operator-portal): shared formatTimestamp util + refresh nav comment"
```

---

## Self-Review

- **Spec coverage:** 4 item → `languages.py` dedup (T1), `useFetchOnMount` (T2), `formatTimestamp` (T3), commento `nav.ts` (T3). Tutti a comportamento invariato; test esistenti invariati + nuovi test focalizzati. `built?` mantenuto. `formatTimestamp` output identico (no TZ). PII-cache/ruff-format esclusi (come da spec).
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto. Nel refactor dei pannelli il JSX resta INVARIATO — indicato esplicitamente.
- **Type/behavior consistency:** hook `useFetchOnMount(fetcher, onOk)` con `fetcher` stabile via `useCallback([client])` → deps `[fetcher, handleError, t]` ≡ originali `[client, handleError, t]` (nessun re-fetch loop); `onOk` in ref (non dipendenza). `formatTimestamp` = trasformazione byte-identica. `refusal.SUPPORTED_LANGUAGES` re-export via `import ... as ...` → `test_refusal.py` invariato; F401/mypy puliti.
- **Regola di stop:** se un'asserzione di un test esistente deve cambiare, il refactor non è neutro → BLOCKED. Nessuna prevista.
