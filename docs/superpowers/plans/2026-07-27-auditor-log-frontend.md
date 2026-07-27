# Vista del log di audit (Auditor) — Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Il visore del log di audit per il ruolo Auditor (§6), sul contratto `/audit` + `/audit/verify` (S18): tabella voci con filtri chi/cosa/quando, paginazione «Carica altri» a cursore, e verifica integrità su richiesta (§7.3).

**Architecture:** Estende `operator-portal/` (scheletro S11, pattern S12–S17). `operatorClient` esteso fail-closed (`listAudit`/`verifyAudit`); schermata coesa `/audit` (ruolo auditor, sola lettura). Nessuna nuova dipendenza; `frontend/` (kiosk) e `backend/` intatti.

**Tech Stack:** React 18 + Vite 5 + TypeScript (strict) + react-i18next + react-router-dom. Test: Vitest + @testing-library/react.

## Global Constraints

- **Estendere solo `operator-portal/`.** `frontend/` e `backend/` NON si toccano. Nessuna nuova dipendenza.
- **TDD** (RED → GREEN), **solo dati sintetici**. Output test **pristine**.
- **Client fail-closed**, mai un throw: Bearer via `headers()`; `401→'unauthorized'`, `403→'forbidden'`, rete/5xx/JSON-invalido → `'error'`.
- **Sola lettura (§6):** la sezione non ha azioni che mutano stato; la verifica è una lettura. `useApiError`: 401→logout+/login; 403→`t('errors.forbidden')`; error→`t('errors.generic')`; loading gated `=== null && !error`.
- **«Carica altri» a cursore:** `before` = id dell'ultima voce mostrata; il pulsante si mostra sse l'ultima pagina ha `LIMIT` voci, sparisce se ne ha meno (fine log). `LIMIT = 50`.
- **Verifica su richiesta:** un pulsante «Verifica integrità» → `verifyAudit()` → badge verde («catena integra») o rosso («manomissione rilevata alla riga N»).
- **Privacy (§2/§5):** si rendono solo pseudonimi opachi + metadati (`details`); nessuna PII (il log non ne contiene per costruzione). La sezione mostra **azioni degli operatori** (accountability), non profili.
- **Nav/titolo:** la label nav e il titolo pagina sono la stessa stringa («Log di audit») → i test d'integrazione interrogano per **ruolo/contenuto proprio** (non per testo puro), come da follow-up S17.
- **i18n:** ogni stringa via `t(...)`. Codice inglese.
- **Gate** (da `operator-portal/`): `npm test && npm run typecheck && npm run lint && npm run build`.

---

### Task 1: Tipi + client `listAudit`/`verifyAudit` + fake + i18n

**Files:**
- Modify: `operator-portal/src/types.ts` (append)
- Modify: `operator-portal/src/api/operatorClient.ts` (2 metodi + export)
- Modify: `operator-portal/src/test/fakeClient.ts` (fixture + opts + counters + metodi)
- Modify: `operator-portal/src/i18n/locales/it.ts` (gruppo `audit`)
- Modify: `operator-portal/src/api/operatorClient.test.ts` (append)

**Interfaces:**
- Consumes: `headers`/`BASE` (`operatorClient.ts`); pattern fake S16/S17.
- Produces (Task 2–3):
  - `types.ts`: `AuditEntry {id:number, occurred_at:string, actor:string|null, action:string, target_pseudonym:string|null, details:Record<string,unknown>}`; `AuditFilters {before?, limit?, actor?, action?, from?, to?}`; `AuditVerification {ok:boolean, broken_at:number|null, reason:string|null}`; `AuditListResult` (`ok{entries}`), `VerifyAuditResult` (`ok{verification}`).
  - `OperatorClient`: `listAudit(filters)`, `verifyAudit()`.
  - fake: fixture `AUDIT_ENTRY`; opts `audit`, `auditPages` (sequenza di pagine per test di «Carica altri»), `verify`; counters `audList`/`audVerify`; array `auditQueries`.
  - i18n: gruppo `audit.*`.

- [ ] **Step 1: Scrivi i test del client (append a `operatorClient.test.ts`)**

```ts
test('listAudit sends set filters + before/limit and maps 200→ok', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.listAudit({ actor: 'm.rossi', action: 'profile_viewed', before: 51, limit: 50 })
  expect(r).toEqual({ status: 'ok', entries: [] })
  const url = String(f.mock.calls[0][0])
  expect(url).toContain('/audit?')
  expect(url).toContain('actor=m.rossi')
  expect(url).toContain('action=profile_viewed')
  expect(url).toContain('before=51')
  expect(url).toContain('limit=50')
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
})

test('listAudit with no filters hits /audit and maps 403/network', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.listAudit({})).toEqual({ status: 'ok', entries: [] })
  expect(String(f.mock.calls[0][0])).toMatch(/\/audit$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.listAudit({})).toEqual({ status: 'forbidden' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.listAudit({})).toEqual({ status: 'error' })
})

test('verifyAudit hits /audit/verify and maps 200→ok{verification}, 403→forbidden', async () => {
  setToken('tok')
  const v = { ok: true, broken_at: null, reason: null }
  const f = vi.fn().mockResolvedValue(res(200, v))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.verifyAudit()).toEqual({ status: 'ok', verification: v })
  expect(String(f.mock.calls[0][0])).toMatch(/\/audit\/verify$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.verifyAudit()).toEqual({ status: 'forbidden' })
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: FAIL (metodi inesistenti).

- [ ] **Step 3: Aggiungi i tipi (`types.ts`)**

Append:
```ts
export interface AuditEntry {
  id: number
  occurred_at: string
  actor: string | null
  action: string
  target_pseudonym: string | null
  details: Record<string, unknown>
}
export interface AuditFilters {
  before?: number
  limit?: number
  actor?: string
  action?: string
  from?: string
  to?: string
}
export interface AuditVerification {
  ok: boolean
  broken_at: number | null
  reason: string | null
}
export type AuditListResult =
  | { status: 'ok'; entries: AuditEntry[] }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
export type VerifyAuditResult =
  | { status: 'ok'; verification: AuditVerification }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
```
Estendi `OperatorClient` (dopo `downloadExport`):
```ts
  listAudit(filters: AuditFilters): Promise<AuditListResult>
  verifyAudit(): Promise<VerifyAuditResult>
```

- [ ] **Step 4: Implementa i 2 metodi (`operatorClient.ts`)**

Aggiungi ai tipi importati: `AuditEntry, AuditFilters, AuditListResult, AuditVerification, VerifyAuditResult`. Prima dell'export `operatorClient`:
```ts
async function listAudit(filters: AuditFilters): Promise<AuditListResult> {
  const qs = new URLSearchParams()
  if (filters.before !== undefined) qs.set('before', String(filters.before))
  if (filters.limit !== undefined) qs.set('limit', String(filters.limit))
  if (filters.actor) qs.set('actor', filters.actor)
  if (filters.action) qs.set('action', filters.action)
  if (filters.from) qs.set('from', filters.from)
  if (filters.to) qs.set('to', filters.to)
  const q = qs.toString()
  let res: Response
  try {
    res = await fetch(`${BASE}/audit${q ? `?${q}` : ''}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', entries: (await res.json()) as AuditEntry[] }
  } catch {
    return { status: 'error' }
  }
}

async function verifyAudit(): Promise<VerifyAuditResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/audit/verify`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', verification: (await res.json()) as AuditVerification }
  } catch {
    return { status: 'error' }
  }
}
```
Aggiungi al literal `export const operatorClient`: `listAudit, verifyAudit`.

- [ ] **Step 5: Esegui i test del client — devono passare**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: PASS.

- [ ] **Step 6: Estendi il fake (`test/fakeClient.ts`)**

Importa i tipi: `AuditEntry, AuditFilters, AuditListResult, VerifyAuditResult`. Aggiungi la fixture (dopo `EXPORT_REQUEST`):
```ts
export const AUDIT_ENTRY: AuditEntry = {
  id: 3, occurred_at: '2026-07-27T10:00:00Z', actor: 'm.rossi', action: 'profile_viewed', target_pseudonym: 'P-4F2A', details: {},
}
```
Nella firma `opts` aggiungi:
```ts
  audit?: AuditListResult
  auditPages?: AuditListResult[]
  verify?: VerifyAuditResult
```
Nei `calls` aggiungi `audList/audVerify` (init 0); aggiungi l'array `auditQueries: AuditFilters[]` (init `[]`, incluso nel return). Prima del `return {`, aggiungi un indice di pagina: `let auditPageIdx = 0`. Aggiungi i metodi:
```ts
    async listAudit(filters) {
      calls.audList++
      auditQueries.push(filters)
      if (opts.auditPages) return opts.auditPages[Math.min(auditPageIdx++, opts.auditPages.length - 1)]
      return opts.audit ?? { status: 'ok', entries: [AUDIT_ENTRY] }
    },
    async verifyAudit() {
      calls.audVerify++
      return opts.verify ?? { status: 'ok', verification: { ok: true, broken_at: null, reason: null } }
    },
```

- [ ] **Step 7: Aggiungi le stringhe i18n (`i18n/locales/it.ts`)**

Nuovo gruppo `audit` (dopo `exports`):
```ts
  audit: {
    title: 'Log di audit',
    filterActor: 'Attore',
    filterAction: 'Azione',
    filterFrom: 'Da',
    filterTo: 'A',
    search: 'Cerca',
    empty: 'Nessuna voce.',
    colWhen: 'Data e ora',
    colActor: 'Attore',
    colAction: 'Azione',
    colTarget: 'Pseudonimo',
    colDetails: 'Dettagli',
    none: '—',
    loadMore: 'Carica altri',
    verify: 'Verifica integrità',
    verifyOk: 'Catena integra',
    verifyBroken: 'Manomissione rilevata alla riga {{id}}',
  },
```
(`nav.audit` = «Log di audit» esiste già.)

- [ ] **Step 8: Gate + commit**

Run: `cd operator-portal && npm test && npm run typecheck && npm run lint`
```bash
git add operator-portal/src/types.ts operator-portal/src/api/operatorClient.ts operator-portal/src/api/operatorClient.test.ts operator-portal/src/test/fakeClient.ts operator-portal/src/i18n/locales/it.ts
git commit -m "feat(operator-portal): audit client (listAudit/verifyAudit) + types + i18n"
```

---

### Task 2: Schermata `AuditLog` (lista + filtri + «Carica altri» + «Verifica integrità»)

**Files:**
- Create: `operator-portal/src/screens/audit/detailsSummary.ts`
- Create: `operator-portal/src/screens/audit/AuditLog.tsx`
- Create: `operator-portal/src/screens/audit/AuditLog.test.tsx`
- Modify: `operator-portal/src/styles/theme.css` (append)

**Interfaces:**
- Consumes: client `listAudit`/`verifyAudit` (Task 1); `useAuth`/`useApiError`; i18n `audit.*` + `errors.*` + `common.loading`; `AuditEntry`/`AuditFilters`/`AuditVerification`.
- Produces (Task 3): `AuditLog` (default della rotta `/audit`); `LIMIT` esportato (page size).

- [ ] **Step 1: Scrivi i test (`AuditLog.test.tsx`)**

```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, AUDIT_ENTRY } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { AuditLog, LIMIT } from './AuditLog'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/audit" element={<AuditLog />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function auditor(overrides = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'auditor' }) }, ...overrides })
}

test('lists entries on mount', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: auditor(), route: '/audit' })
  expect(await screen.findByText('profile_viewed')).toBeInTheDocument()
  expect(screen.getByText('P-4F2A')).toBeInTheDocument()
})

test('«Cerca» sends the set filters', async () => {
  setToken('tok')
  const client = auditor()
  renderWithProviders(harness(), { client, route: '/audit' })
  await screen.findByText('profile_viewed')
  await userEvent.type(screen.getByLabelText('Attore'), 'm.rossi')
  await userEvent.type(screen.getByLabelText('Azione'), 'profile_viewed')
  await userEvent.click(screen.getByRole('button', { name: 'Cerca' }))
  await waitFor(() => expect(client.auditQueries.at(-1)).toMatchObject({ actor: 'm.rossi', action: 'profile_viewed', limit: LIMIT }))
})

test('«Carica altri» pages with before=<last id> and appends; hides at end', async () => {
  setToken('tok')
  const full = Array.from({ length: LIMIT }, (_, i) => ({ ...AUDIT_ENTRY, id: 100 - i, action: 'a' + (100 - i) }))
  const client = auditor({ auditPages: [
    { status: 'ok', entries: full },                                   // mount: full page → hasMore
    { status: 'ok', entries: [{ ...AUDIT_ENTRY, id: 40, action: 'older' }] },  // load-more: short page → end
  ] })
  renderWithProviders(harness(), { client, route: '/audit' })
  await screen.findByText('a100')
  await userEvent.click(screen.getByRole('button', { name: 'Carica altri' }))
  await waitFor(() => expect(screen.getByText('older')).toBeInTheDocument())
  expect(client.auditQueries.at(-1)).toMatchObject({ before: 51 }) // full[49].id = 100-49 = 51
  expect(screen.queryByRole('button', { name: 'Carica altri' })).not.toBeInTheDocument()
})

test('«Verifica integrità»: green badge on an intact chain', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: auditor(), route: '/audit' })
  await screen.findByText('profile_viewed')
  await userEvent.click(screen.getByRole('button', { name: 'Verifica integrità' }))
  expect(await screen.findByText('Catena integra')).toBeInTheDocument()
})

test('«Verifica integrità»: red badge with the broken row on a tampered chain', async () => {
  setToken('tok')
  const client = auditor({ verify: { status: 'ok', verification: { ok: false, broken_at: 7, reason: 'prev_hash mismatch' } } })
  renderWithProviders(harness(), { client, route: '/audit' })
  await screen.findByText('profile_viewed')
  await userEvent.click(screen.getByRole('button', { name: 'Verifica integrità' }))
  expect(await screen.findByText('Manomissione rilevata alla riga 7')).toBeInTheDocument()
})

test('empty state when the log has no entries', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: auditor({ audit: { status: 'ok', entries: [] } }), route: '/audit' })
  expect(await screen.findByText('Nessuna voce.')).toBeInTheDocument()
})

test('403 on mount shows the error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: auditor({ audit: { status: 'forbidden' } }), route: '/audit' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/screens/audit/AuditLog.test.tsx`
Expected: FAIL (moduli inesistenti).

- [ ] **Step 3: Implementa `detailsSummary.ts`**

```ts
export function detailsSummary(details: Record<string, unknown>): string {
  const parts = Object.entries(details).map(([k, v]) => `${k}=${String(v)}`)
  return parts.length > 0 ? parts.join(', ') : '—'
}
```

- [ ] **Step 4: Implementa `AuditLog.tsx`**

```tsx
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { AuditEntry, AuditFilters, AuditVerification } from '../../types'
import { detailsSummary } from './detailsSummary'

export const LIMIT = 50

export function AuditLog() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const [actor, setActor] = useState('')
  const [action, setAction] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [verification, setVerification] = useState<AuditVerification | null>(null)

  const onErr = useCallback(
    (status: 'unauthorized' | 'forbidden' | 'error') => {
      const outcome = handleError(status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    },
    [handleError, t],
  )

  const currentFilters = useCallback((): AuditFilters => {
    const f: AuditFilters = { limit: LIMIT }
    if (actor.trim()) f.actor = actor.trim()
    if (action.trim()) f.action = action.trim()
    if (from) f.from = from
    if (to) f.to = to
    return f
  }, [actor, action, from, to])

  const runSearch = useCallback(
    async (filters: AuditFilters) => {
      setError('')
      const r = await client.listAudit(filters)
      if (r.status === 'ok') {
        setEntries(r.entries)
        setHasMore(r.entries.length === LIMIT)
      } else onErr(r.status)
    },
    [client, onErr],
  )

  useEffect(() => {
    void runSearch({ limit: LIMIT })
  }, [runSearch])

  function submit(e: FormEvent) {
    e.preventDefault()
    void runSearch(currentFilters())
  }

  async function loadMore() {
    if (!entries || entries.length === 0) return
    const before = entries[entries.length - 1].id
    const r = await client.listAudit({ ...currentFilters(), before })
    if (r.status === 'ok') {
      const page = r.entries
      setEntries((prev) => [...(prev ?? []), ...page])
      setHasMore(page.length === LIMIT)
    } else onErr(r.status)
  }

  async function verify() {
    setError('')
    const r = await client.verifyAudit()
    if (r.status === 'ok') setVerification(r.verification)
    else onErr(r.status)
  }

  return (
    <div className="audit-log">
      <h1>{t('audit.title')}</h1>
      <div className="audit-toolbar">
        <form className="filters" onSubmit={submit}>
          <label>{t('audit.filterActor')}<input value={actor} onChange={(e) => setActor(e.target.value)} /></label>
          <label>{t('audit.filterAction')}<input value={action} onChange={(e) => setAction(e.target.value)} /></label>
          <label>{t('audit.filterFrom')}<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label>{t('audit.filterTo')}<input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
          <button type="submit">{t('audit.search')}</button>
        </form>
        <div className="audit-verify">
          <button type="button" onClick={verify}>{t('audit.verify')}</button>
          {verification &&
            (verification.ok ? (
              <span className="badge-status st-approved">{t('audit.verifyOk')}</span>
            ) : (
              <span className="badge-danger" role="alert">{t('audit.verifyBroken', { id: verification.broken_at })}</span>
            ))}
        </div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {entries === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        entries &&
        (entries.length === 0 ? (
          <p>{t('audit.empty')}</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>{t('audit.colWhen')}</th>
                  <th>{t('audit.colActor')}</th>
                  <th>{t('audit.colAction')}</th>
                  <th>{t('audit.colTarget')}</th>
                  <th>{t('audit.colDetails')}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id}>
                    <td>{e.occurred_at.replace('T', ' ').slice(0, 16)}</td>
                    <td>{e.actor ?? t('audit.none')}</td>
                    <td>{e.action}</td>
                    <td>{e.target_pseudonym ?? t('audit.none')}</td>
                    <td>{detailsSummary(e.details)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {hasMore && (
              <button type="button" className="audit-more" onClick={loadMore}>{t('audit.loadMore')}</button>
            )}
          </>
        ))
      )}
    </div>
  )
}
```

- [ ] **Step 5: Aggiungi le classi CSS (`styles/theme.css`)**

Append:
```css
.audit-toolbar { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.audit-verify { display: flex; gap: 8px; align-items: center; }
.badge-danger { border-radius: 10px; padding: 2px 10px; font-size: 12px; font-weight: 700; background: #fee2e2; color: #b91c1c; }
.audit-more { margin-top: 10px; padding: 8px 14px; border: 1px solid var(--border); border-radius: 8px; background: #fff; font: inherit; cursor: pointer; }
```

- [ ] **Step 6: Esegui i test + gate**

Run: `cd operator-portal && npx vitest run src/screens/audit/AuditLog.test.tsx && npm run typecheck && npm run lint`
Expected: PASS, pristine.

- [ ] **Step 7: Commit**

```bash
git add operator-portal/src/screens/audit/detailsSummary.ts operator-portal/src/screens/audit/AuditLog.tsx operator-portal/src/screens/audit/AuditLog.test.tsx operator-portal/src/styles/theme.css
git commit -m "feat(operator-portal): auditor log viewer (filters + load-more + integrity check)"
```

---

### Task 3: Nav «Log di audit» reale + rotta `/audit` + integrazione

**Files:**
- Modify: `operator-portal/src/rbac/nav.ts`
- Modify: `operator-portal/src/App.tsx`
- Modify: `operator-portal/src/shell/Nav.test.tsx`
- Modify: `operator-portal/src/App.test.tsx`

**Interfaces:**
- Consumes: `AuditLog` (Task 2).
- Produces: rotta `/audit` funzionante per l'auditor.

- [ ] **Step 1: Aggiungi il test della Nav (`Nav.test.tsx`)**

Append (NON sostituire i test esistenti):
```tsx
test('auditor sees «Log di audit» as a real link', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'auditor' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Log di audit/ })).toHaveAttribute('href', '/audit')
})
```

- [ ] **Step 2: Aggiungi il test d'integrazione (`App.test.tsx`)**

Append (query per contenuto proprio della schermata, non per il titolo == label nav):
```tsx
test('an authenticated auditor can reach the audit log section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'auditor' }) } })
  renderApp(client, '/audit')
  // «Verifica integrità» is rendered only by AuditLog → proves the route mounted
  expect(await screen.findByRole('button', { name: 'Verifica integrità' })).toBeInTheDocument()
})
```

- [ ] **Step 3: Esegui — l'integrazione deve fallire**

Run: `cd operator-portal && npx vitest run src/App.test.tsx src/shell/Nav.test.tsx`
Expected: FAIL (rotta `/audit` assente → redirect a `/`; nav non ancora link).

- [ ] **Step 4: Marca la voce di nav `built` (`rbac/nav.ts`)**

Nel blocco `auditor`, cambia la riga:
```ts
  auditor: [{ path: '/audit', labelKey: 'nav.audit', built: true }],
```

- [ ] **Step 5: Aggancia la rotta (`App.tsx`)**

Import: `import { AuditLog } from './screens/audit/AuditLog'`. Dentro il blocco `<Route path="/" …>`, dopo `export-approvals`, aggiungi:
```tsx
        <Route path="audit" element={<AuditLog />} />
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
git commit -m "feat(operator-portal): wire audit log route + real nav link"
```

---

## Self-Review

- **Spec coverage:** §2 obiettivi → client `listAudit`/`verifyAudit` (T1), schermata con filtri+lista+«Carica altri»+«Verifica integrità» (T2), nav+rotta (T3). Sola lettura (nessuna azione mutante), cursore before + hasMore su page==LIMIT, badge verde/rosso(+riga), details compatti, pseudonimi opachi/«—», loading gated `!error`. Tutti coperti.
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto.
- **Type consistency:** `AuditEntry`/`AuditFilters`/`AuditVerification`/le result-union (T1) usate da client, fake e schermata (T2); `LIMIT` esportato da `AuditLog` e importato dal test; `listAudit(filters)`/`verifyAudit()` firme identiche in T1 e nella schermata; fake `auditPages`/`auditQueries`/`AUDIT_ENTRY` consumati dal test T2; i18n `audit.*` (T1) consumati da T2/T3; `nav.audit` pre-esistente.
- **Rossa/privacy:** vista sola-lettura; verifica su richiesta (no O(n) al mount); pseudonimi opachi + metadati, nessuna PII; nav/titolo stessa stringa → test d'integrazione per ruolo/contenuto proprio (S17).
