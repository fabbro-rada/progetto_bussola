# Export con autorizzazione — Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Le due superfici del portale per l'export con autorizzazione, sul contratto `/exports` (S16): operatore (richiesta con filtri+motivo, lista con stato, **download** del file JSON su `approved`) e supervisore (**coda approvazioni** con Approva-conferma / Nega-motivo).

**Architecture:** Estende `operator-portal/` (scheletro S11, pattern S12–S15). `operatorClient` esteso fail-closed (incl. `downloadExport` che restituisce un **Blob**); due schermate coese `/export` (operatore) e `/export-approvals` (supervisore) sotto la shell; dialoghi riusati/estesi da S14; `useApiError` per il 401. Il gate di autorizzazione resta **lato server**.

**Tech Stack:** React 18 + Vite 5 + TypeScript (strict) + react-i18next + react-router-dom. Test: Vitest + @testing-library/react. **Nessuna nuova dipendenza.**

## Global Constraints

- **Estendere solo `operator-portal/`.** `frontend/` (kiosk) e `backend/` NON si toccano. Nessuna nuova dipendenza.
- **TDD** (RED → GREEN), **solo dati sintetici**. Output test **pristine**.
- **Client fail-closed**, mai un throw: Bearer via `headers()`; `401→'unauthorized'`, `403→'forbidden'`, `404→'not-found'`, `409→'conflict'` (approve/deny) / `'not-approved'` (download), rete/5xx/JSON-invalido → `'error'`. `downloadExport` su 200 → `{status:'ok', blob}`.
- **Il server resta l'autorità (§7.3):** il pulsante Download è abilitato solo su `approved`, ma il gate reale è server-side; 409/404 sul download sono **degrado** (messaggio), mai dati.
- **Degrado UI:** `401`→`useApiError` (onUnauthorized + `/login`); `403`→`t('errors.forbidden')`; rete/5xx→`t('errors.generic')`; liste con loading gated `=== null && !error`.
- **Motivo obbligatorio:** la richiesta (`reason`) e il rifiuto (deny `reason`) hanno il campo obbligatorio → submit disabilitato se vuoto.
- **«Tutti i profili» esplicito:** i filtri vuoti si rendono come «Tutti i profili» (§7.3, chiarezza per l'approvatore).
- **i18n:** ogni stringa via `t(...)`; riuso delle etichette S13 (`profiles.filter*`, `profiles.any`, `pl.availability_*`, `pl.note_*`). Codice inglese.
- **Privacy (§2/§5):** nessuna PII resa; la coda dell'approvatore mostra metadati (richiedente, filtri, motivo), **nessun profilo**; il download è un **file**, non un'anteprima a schermo.
- **Gate** (da `operator-portal/`): `npm test && npm run typecheck && npm run lint && npm run build`.

---

### Task 1: Tipi + client `/exports` (con download-Blob) + fake + i18n

**Files:**
- Modify: `operator-portal/src/types.ts` (append)
- Modify: `operator-portal/src/api/operatorClient.ts` (6 metodi + export)
- Modify: `operator-portal/src/test/fakeClient.ts` (fixture + opts + counters + metodi)
- Modify: `operator-portal/src/i18n/locales/it.ts` (gruppo `exports` + `nav.exportApprovals` + etichette stato)
- Modify: `operator-portal/src/api/operatorClient.test.ts` (append)

**Interfaces:**
- Consumes: `ProfileFilters` (riuso: `{availability?, language?, note?, skill_query?}`); `headers`/`BASE` (`operatorClient.ts`); pattern fake S14/S15.
- Produces (Task 2–4):
  - `types.ts`: `ExportStatus = 'pending'|'approved'|'denied'`; `ExportRequest {id, requested_by, filters: ProfileFilters, reason, status, decided_by, decided_at, decision_reason, created_at}` (i campi `decided_*` sono `string|null`); result-union `CreateExportResult` (`ok{request}`), `ListExportsResult` (`ok{requests}`), `MutateExportResult` (`ok` | … | `not-found` | `conflict`), `DownloadExportResult` (`ok{blob:Blob}` | … | `not-found` | `not-approved`).
  - `OperatorClient`: `createExport(filters, reason)`, `listExports()`, `listPendingExports()`, `approveExport(id)`, `denyExport(id, reason)`, `downloadExport(id)`.
  - fake: fixture `EXPORT_REQUEST`; opts `exports/pending/createExp/approveExp/denyExp/download`; counters `expList/expPending/expCreate/expApprove/expDeny/expDownload`; array `createdExports`/`approvedIds`/`deniedExports`/`downloadedIds`.
  - i18n: gruppo `exports.*` + `nav.exportApprovals`.

- [ ] **Step 1: Scrivi i test del client (append a `operatorClient.test.ts`)**

```ts
test('createExport POSTs {filters, reason} and maps 201→ok', async () => {
  setToken('tok')
  const REQ = { id: 1, requested_by: 'm.rossi', filters: { skill_query: 'cucina' }, reason: 'Azienda X', status: 'pending', decided_by: null, decided_at: null, decision_reason: null, created_at: '2026-07-27T10:00:00Z' }
  const f = vi.fn().mockResolvedValue(res(201, REQ))
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.createExport({ skill_query: 'cucina' }, 'Azienda X')
  expect(r).toEqual({ status: 'ok', request: REQ })
  const [url, init] = f.mock.calls[0]
  expect(String(url)).toMatch(/\/exports$/)
  expect((init as RequestInit).method).toBe('POST')
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ filters: { skill_query: 'cucina' }, reason: 'Azienda X' })
  expect((init!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
})

test('listExports and listPendingExports hit the right paths and map status', async () => {
  setToken('tok')
  const f1 = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f1)
  expect(await operatorClient.listExports()).toEqual({ status: 'ok', requests: [] })
  expect(String(f1.mock.calls[0][0])).toMatch(/\/exports$/)
  const f2 = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f2)
  expect(await operatorClient.listPendingExports()).toEqual({ status: 'ok', requests: [] })
  expect(String(f2.mock.calls[0][0])).toMatch(/\/exports\/pending$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.listPendingExports()).toEqual({ status: 'forbidden' })
})

test('approveExport 204→ok, 409→conflict, 404→not-found', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(204)))
  expect(await operatorClient.approveExport(5)).toEqual({ status: 'ok' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(409)))
  expect(await operatorClient.approveExport(5)).toEqual({ status: 'conflict' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(404)))
  expect(await operatorClient.approveExport(5)).toEqual({ status: 'not-found' })
})

test('denyExport POSTs {reason} and maps 204→ok', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.denyExport(5, 'fuori scopo')).toEqual({ status: 'ok' })
  const [url, init] = f.mock.calls[0]
  expect(String(url)).toMatch(/\/exports\/5\/deny$/)
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ reason: 'fuori scopo' })
})

test('downloadExport returns a Blob on 200, not-approved on 409, not-found on 404', async () => {
  setToken('tok')
  const blob = new Blob(['[]'], { type: 'application/json' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 200, ok: true, blob: async () => blob }))
  const r = await operatorClient.downloadExport(5)
  expect(r).toEqual({ status: 'ok', blob })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 409, ok: false, blob: async () => new Blob() }))
  expect(await operatorClient.downloadExport(5)).toEqual({ status: 'not-approved' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 404, ok: false, blob: async () => new Blob() }))
  expect(await operatorClient.downloadExport(5)).toEqual({ status: 'not-found' })
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: FAIL (metodi inesistenti).

- [ ] **Step 3: Aggiungi i tipi (`types.ts`)**

Append (riusa `ProfileFilters`, già presente):
```ts
export type ExportStatus = 'pending' | 'approved' | 'denied'
export interface ExportRequest {
  id: number
  requested_by: string
  filters: ProfileFilters
  reason: string
  status: ExportStatus
  decided_by: string | null
  decided_at: string | null
  decision_reason: string | null
  created_at: string
}
export type CreateExportResult =
  | { status: 'ok'; request: ExportRequest }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
export type ListExportsResult =
  | { status: 'ok'; requests: ExportRequest[] }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
export type MutateExportResult =
  | { status: 'ok' }
  | { status: 'unauthorized' } | { status: 'forbidden' }
  | { status: 'not-found' } | { status: 'conflict' } | { status: 'error' }
export type DownloadExportResult =
  | { status: 'ok'; blob: Blob }
  | { status: 'unauthorized' } | { status: 'forbidden' }
  | { status: 'not-found' } | { status: 'not-approved' } | { status: 'error' }
```
Estendi `OperatorClient` (dopo `getMetrics`):
```ts
  createExport(filters: ProfileFilters, reason: string): Promise<CreateExportResult>
  listExports(): Promise<ListExportsResult>
  listPendingExports(): Promise<ListExportsResult>
  approveExport(id: number): Promise<MutateExportResult>
  denyExport(id: number, reason: string): Promise<MutateExportResult>
  downloadExport(id: number): Promise<DownloadExportResult>
```

- [ ] **Step 4: Implementa i 6 metodi (`operatorClient.ts`)**

Aggiungi ai tipi importati: `CreateExportResult, DownloadExportResult, ExportRequest, ListExportsResult, MutateExportResult, ProfileFilters` (se non già importati). Prima dell'export `operatorClient`:
```ts
async function createExport(filters: ProfileFilters, reason: string): Promise<CreateExportResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/exports`, { method: 'POST', headers: headers(true), body: JSON.stringify({ filters, reason }) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', request: (await res.json()) as ExportRequest }
  } catch {
    return { status: 'error' }
  }
}

async function listExportsAt(path: string): Promise<ListExportsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', requests: (await res.json()) as ExportRequest[] }
  } catch {
    return { status: 'error' }
  }
}

function listExports(): Promise<ListExportsResult> {
  return listExportsAt('/exports')
}

function listPendingExports(): Promise<ListExportsResult> {
  return listExportsAt('/exports/pending')
}

async function decideExport(id: number, action: 'approve' | 'deny', reason?: string): Promise<MutateExportResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/exports/${id}/${action}`, {
      method: 'POST',
      headers: headers(reason !== undefined),
      body: reason !== undefined ? JSON.stringify({ reason }) : undefined,
    })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 404) return { status: 'not-found' }
  if (res.status === 409) return { status: 'conflict' }
  if (res.status === 204 || res.ok) return { status: 'ok' }
  return { status: 'error' }
}

function approveExport(id: number): Promise<MutateExportResult> {
  return decideExport(id, 'approve')
}

function denyExport(id: number, reason: string): Promise<MutateExportResult> {
  return decideExport(id, 'deny', reason)
}

async function downloadExport(id: number): Promise<DownloadExportResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/exports/${id}/download`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 404) return { status: 'not-found' }
  if (res.status === 409) return { status: 'not-approved' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', blob: await res.blob() }
  } catch {
    return { status: 'error' }
  }
}
```
Aggiungi al literal `export const operatorClient` le 6 proprietà: `createExport, listExports, listPendingExports, approveExport, denyExport, downloadExport`.

- [ ] **Step 5: Esegui i test del client — devono passare**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: PASS.

- [ ] **Step 6: Estendi il fake (`test/fakeClient.ts`)**

Importa i tipi: `CreateExportResult, DownloadExportResult, ExportRequest, ListExportsResult, MutateExportResult, ProfileFilters`. Aggiungi la fixture (dopo `METRICS`):
```ts
export const EXPORT_REQUEST: ExportRequest = {
  id: 1, requested_by: 'm.rossi', filters: { skill_query: 'cucina' }, reason: 'Azienda X',
  status: 'pending', decided_by: null, decided_at: null, decision_reason: null, created_at: '2026-07-27T10:00:00Z',
}
```
Nella firma `opts` aggiungi:
```ts
  exports?: ListExportsResult
  pending?: ListExportsResult
  createExp?: CreateExportResult
  approveExp?: MutateExportResult
  denyExp?: MutateExportResult
  download?: DownloadExportResult
```
Nei `calls` aggiungi `expList/expPending/expCreate/expApprove/expDeny/expDownload` (init 0); aggiungi gli array `createdExports: { filters: ProfileFilters; reason: string }[]`, `approvedIds: number[]`, `deniedExports: { id: number; reason: string }[]`, `downloadedIds: number[]`; includili nel return. Aggiungi i metodi:
```ts
    async createExport(filters, reason) {
      calls.expCreate++
      createdExports.push({ filters, reason })
      return opts.createExp ?? { status: 'ok', request: EXPORT_REQUEST }
    },
    async listExports() {
      calls.expList++
      return opts.exports ?? { status: 'ok', requests: [EXPORT_REQUEST] }
    },
    async listPendingExports() {
      calls.expPending++
      return opts.pending ?? { status: 'ok', requests: [EXPORT_REQUEST] }
    },
    async approveExport(id) {
      calls.expApprove++
      approvedIds.push(id)
      return opts.approveExp ?? { status: 'ok' }
    },
    async denyExport(id, reason) {
      calls.expDeny++
      deniedExports.push({ id, reason })
      return opts.denyExp ?? { status: 'ok' }
    },
    async downloadExport(id) {
      calls.expDownload++
      downloadedIds.push(id)
      return opts.download ?? { status: 'ok', blob: new Blob(['[]'], { type: 'application/json' }) }
    },
```

- [ ] **Step 7: Aggiungi le stringhe i18n (`i18n/locales/it.ts`)**

Nel gruppo `nav`, aggiungi: `exportApprovals: 'Approvazioni export',`. Aggiungi un nuovo gruppo `exports` (dopo `metrics`):
```ts
  exports: {
    title: 'Export',
    new: 'Nuova richiesta',
    createTitle: 'Nuova richiesta di export',
    reason: 'Motivo / destinatario',
    create: 'Invia richiesta',
    cancel: 'Annulla',
    empty: 'Nessuna richiesta.',
    colDate: 'Data',
    colFilters: 'Ambito',
    colStatus: 'Stato',
    colOutcome: 'Esito',
    colActions: 'Azioni',
    colRequester: 'Richiedente',
    status_pending: 'In attesa',
    status_approved: 'Approvata',
    status_denied: 'Negata',
    download: 'Scarica',
    downloadError: 'Download non riuscito. Riprova.',
    allProfiles: 'Tutti i profili',
    approvalsTitle: 'Approvazioni export',
    emptyPending: 'Nessuna richiesta in attesa.',
    approve: 'Approva',
    deny: 'Nega',
    confirm: 'Conferma',
    confirmApprove: 'Approvare l’export richiesto da «{{who}}»?\nAmbito: {{scope}}\nMotivo: {{reason}}',
    denyTitle: 'Nega la richiesta di «{{who}}»',
    denyReason: 'Motivo del rifiuto',
    denyConfirm: 'Conferma rifiuto',
  },
```

- [ ] **Step 8: Gate + commit**

Run: `cd operator-portal && npm test && npm run typecheck && npm run lint`
```bash
git add operator-portal/src/types.ts operator-portal/src/api/operatorClient.ts operator-portal/src/api/operatorClient.test.ts operator-portal/src/test/fakeClient.ts operator-portal/src/i18n/locales/it.ts
git commit -m "feat(operator-portal): exports client (create/list/pending/approve/deny/download) + types + i18n"
```

---

### Task 2: Superficie operatore — `filterSummary` + `NewExportForm` + `ExportRequests`

**Files:**
- Create: `operator-portal/src/screens/exports/filterSummary.ts`
- Create: `operator-portal/src/screens/exports/download.ts`
- Create: `operator-portal/src/screens/exports/NewExportForm.tsx`
- Create: `operator-portal/src/screens/exports/ExportRequests.tsx`
- Create: `operator-portal/src/screens/exports/ExportRequests.test.tsx`
- Modify: `operator-portal/src/styles/theme.css` (append)

**Interfaces:**
- Consumes: client `createExport`/`listExports`/`downloadExport` (Task 1); `useAuth`/`useApiError`; i18n `exports.*` + `profiles.filter*`/`profiles.any` + `pl.availability_*`/`pl.note_*` + `errors.*` + `common.loading`; `ProfileFilters`/`Availability`/`OperationalNoteCategory`.
- Produces (Task 4): `ExportRequests` (default della rotta `/export`); `filterSummary(filters, t)` util (usata anche da Task 3).

- [ ] **Step 1: Scrivi i test (`ExportRequests.test.tsx`)**

```tsx
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, EXPORT_REQUEST } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ExportRequests } from './ExportRequests'

afterEach(() => sessionStorage.clear())

function harness(saveBlob = vi.fn()) {
  return (
    <Routes>
      <Route path="/export" element={<ExportRequests saveBlob={saveBlob} />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function op(overrides = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, ...overrides })
}

test('lists own requests with a readable scope and status', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: op(), route: '/export' })
  expect(await screen.findByText('cucina')).toBeInTheDocument() // filterSummary of {skill_query:'cucina'}
  expect(screen.getByText('In attesa')).toBeInTheDocument()
})

test('the new-request form sends the set filters + reason and reloads', async () => {
  setToken('tok')
  const client = op()
  renderWithProviders(harness(), { client, route: '/export' })
  await screen.findByText('cucina')
  await userEvent.click(screen.getByRole('button', { name: /Nuova richiesta/ }))
  await userEvent.type(screen.getByLabelText('Competenza'), 'muratura')
  await userEvent.type(screen.getByLabelText('Motivo / destinatario'), 'Azienda Y')
  await userEvent.click(screen.getByRole('button', { name: 'Invia richiesta' }))
  expect(client.createdExports[0]).toEqual({ filters: { skill_query: 'muratura' }, reason: 'Azienda Y' })
  await waitFor(() => expect(client.calls.expList).toBe(2)) // reloaded
})

test('reason is required: submit is disabled until it is filled', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: op(), route: '/export' })
  await screen.findByText('cucina')
  await userEvent.click(screen.getByRole('button', { name: /Nuova richiesta/ }))
  expect(screen.getByRole('button', { name: 'Invia richiesta' })).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Motivo / destinatario'), 'x')
  expect(screen.getByRole('button', { name: 'Invia richiesta' })).toBeEnabled()
})

test('Download is shown only for approved requests and triggers the file save', async () => {
  setToken('tok')
  const approved = { ...EXPORT_REQUEST, id: 7, status: 'approved' as const }
  const saveBlob = vi.fn()
  const client = op({ exports: { status: 'ok', requests: [approved] } })
  renderWithProviders(harness(saveBlob), { client, route: '/export' })
  const btn = await screen.findByRole('button', { name: 'Scarica' })
  await userEvent.click(btn)
  await waitFor(() => expect(client.downloadedIds).toEqual([7]))
  await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'export-7.json'))
})

test('a pending request has no Download button', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: op(), route: '/export' }) // default EXPORT_REQUEST is pending
  await screen.findByText('cucina')
  expect(screen.queryByRole('button', { name: 'Scarica' })).not.toBeInTheDocument()
})

test('403 on mount shows the error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: op({ exports: { status: 'forbidden' } }), route: '/export' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/screens/exports/ExportRequests.test.tsx`
Expected: FAIL (moduli inesistenti).

- [ ] **Step 3: Implementa `filterSummary.ts` e `download.ts`**

`filterSummary.ts`:
```ts
import type { TFunction } from 'i18next'
import type { ProfileFilters } from '../../types'

export function filterSummary(filters: ProfileFilters, t: TFunction): string {
  const parts: string[] = []
  if (filters.availability) parts.push(t(`pl.availability_${filters.availability}`))
  if (filters.language) parts.push(filters.language)
  if (filters.note) parts.push(t(`pl.note_${filters.note}`))
  if (filters.skill_query) parts.push(filters.skill_query)
  return parts.length > 0 ? parts.join(' · ') : t('exports.allProfiles')
}
```

`download.ts`:
```ts
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 4: Implementa `NewExportForm.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { Availability, OperationalNoteCategory, ProfileFilters } from '../../types'

const AVAILABILITIES: Availability[] = ['full_time', 'part_time', 'flexible']
const NOTES: OperationalNoteCategory[] = [
  'needs_language_support', 'needs_literacy_support', 'limited_availability', 'prefers_team_work', 'prefers_solo_work',
]

export function NewExportForm({
  onSubmit,
  onCancel,
  busy,
  error,
}: {
  onSubmit: (filters: ProfileFilters, reason: string) => void
  onCancel: () => void
  busy: boolean
  error: string
}) {
  const { t } = useTranslation()
  const [availability, setAvailability] = useState<Availability | ''>('')
  const [language, setLanguage] = useState('')
  const [note, setNote] = useState<OperationalNoteCategory | ''>('')
  const [skillQuery, setSkillQuery] = useState('')
  const [reason, setReason] = useState('')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!reason.trim()) return
    const filters: ProfileFilters = {}
    if (availability) filters.availability = availability
    if (language.trim()) filters.language = language.trim()
    if (note) filters.note = note
    if (skillQuery.trim()) filters.skill_query = skillQuery.trim()
    onSubmit(filters, reason.trim())
  }

  return (
    <form className="op-create" onSubmit={submit}>
      <h2>{t('exports.createTitle')}</h2>
      <label>{t('profiles.filterAvailability')}
        <select value={availability} onChange={(e) => setAvailability(e.target.value as Availability | '')}>
          <option value="">{t('profiles.any')}</option>
          {AVAILABILITIES.map((a) => <option key={a} value={a}>{t(`pl.availability_${a}`)}</option>)}
        </select>
      </label>
      <label>{t('profiles.filterLanguage')}<input value={language} onChange={(e) => setLanguage(e.target.value)} /></label>
      <label>{t('profiles.filterNote')}
        <select value={note} onChange={(e) => setNote(e.target.value as OperationalNoteCategory | '')}>
          <option value="">{t('profiles.any')}</option>
          {NOTES.map((n) => <option key={n} value={n}>{t(`pl.note_${n}`)}</option>)}
        </select>
      </label>
      <label>{t('profiles.filterSkill')}<input value={skillQuery} onChange={(e) => setSkillQuery(e.target.value)} /></label>
      <label>{t('exports.reason')}<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="op-create-actions">
        <button type="button" onClick={onCancel}>{t('exports.cancel')}</button>
        <button type="submit" disabled={busy || !reason.trim()}>{t('exports.create')}</button>
      </div>
    </form>
  )
}
```

- [ ] **Step 5: Implementa `ExportRequests.tsx`**

```tsx
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { ExportRequest, ProfileFilters } from '../../types'
import { NewExportForm } from './NewExportForm'
import { filterSummary } from './filterSummary'
import { saveBlob as defaultSaveBlob } from './download'

export function ExportRequests({ saveBlob = defaultSaveBlob }: { saveBlob?: (blob: Blob, filename: string) => void }) {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [requests, setRequests] = useState<ExportRequest[] | null>(null)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [createError, setCreateError] = useState('')

  const onErr = useCallback(
    (status: 'unauthorized' | 'forbidden' | 'error', set: (m: string) => void) => {
      const outcome = handleError(status)
      if (outcome !== 'handled') set(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    },
    [handleError, t],
  )

  const load = useCallback(async () => {
    setError('')
    const r = await client.listExports()
    if (r.status === 'ok') setRequests(r.requests)
    else onErr(r.status, setError)
  }, [client, onErr])

  useEffect(() => {
    void load()
  }, [load])

  async function create(filters: ProfileFilters, reason: string) {
    setCreateError('')
    setCreateBusy(true)
    const r = await client.createExport(filters, reason)
    setCreateBusy(false)
    if (r.status === 'ok') {
      setShowCreate(false)
      void load()
    } else onErr(r.status, setCreateError)
  }

  async function download(req: ExportRequest) {
    setError('')
    const r = await client.downloadExport(req.id)
    if (r.status === 'ok') saveBlob(r.blob, `export-${req.id}.json`)
    else if (r.status === 'unauthorized') handleError(r.status)
    else setError(t(r.status === 'forbidden' ? 'errors.forbidden' : 'exports.downloadError'))
  }

  return (
    <div className="op-admin">
      <div className="op-head">
        <h1>{t('exports.title')}</h1>
        <button type="button" onClick={() => { setShowCreate((s) => !s); setCreateError('') }}>+ {t('exports.new')}</button>
      </div>

      {showCreate && <NewExportForm onSubmit={create} onCancel={() => { setShowCreate(false); setCreateError('') }} busy={createBusy} error={createError} />}

      {error && <p className="error" role="alert">{error}</p>}
      {requests === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        requests &&
        (requests.length === 0 ? (
          <p>{t('exports.empty')}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t('exports.colDate')}</th>
                <th>{t('exports.colFilters')}</th>
                <th>{t('exports.colStatus')}</th>
                <th>{t('exports.colOutcome')}</th>
                <th>{t('exports.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => (
                <tr key={req.id}>
                  <td>{req.created_at.slice(0, 10)}</td>
                  <td>{filterSummary(req.filters, t)}</td>
                  <td><span className={`badge-status st-${req.status}`}>{t(`exports.status_${req.status}`)}</span></td>
                  <td>{req.decision_reason ?? '—'}</td>
                  <td>{req.status === 'approved' && <button type="button" onClick={() => download(req)}>{t('exports.download')}</button>}</td>
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

- [ ] **Step 6: Aggiungi le classi CSS (`styles/theme.css`)**

Append:
```css
.badge-status { border-radius: 10px; padding: 2px 10px; font-size: 12px; font-weight: 700; }
.st-pending { background: #fef3c7; color: #92400e; }
.st-approved { background: #dcfce7; color: #15803d; }
.st-denied { background: #f3f4f6; color: #4b5563; }
.op-create textarea { padding: 8px; border: 1px solid var(--border); border-radius: 8px; font: inherit; min-height: 60px; }
```

- [ ] **Step 7: Esegui i test + gate**

Run: `cd operator-portal && npx vitest run src/screens/exports/ExportRequests.test.tsx && npm run typecheck && npm run lint`
Expected: PASS, pristine.

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/screens/exports/filterSummary.ts operator-portal/src/screens/exports/download.ts operator-portal/src/screens/exports/NewExportForm.tsx operator-portal/src/screens/exports/ExportRequests.tsx operator-portal/src/screens/exports/ExportRequests.test.tsx operator-portal/src/styles/theme.css
git commit -m "feat(operator-portal): operator export surface (request + list + file download)"
```

---

### Task 3: Superficie supervisore — `DenyDialog` + `ExportApprovals`

**Files:**
- Create: `operator-portal/src/screens/exports/DenyDialog.tsx`
- Create: `operator-portal/src/screens/exports/ExportApprovals.tsx`
- Create: `operator-portal/src/screens/exports/ExportApprovals.test.tsx`

**Interfaces:**
- Consumes: client `listPendingExports`/`approveExport`/`denyExport` (Task 1); `ConfirmDialog` (`../operators/ConfirmDialog`, S14) per l'approvazione; `filterSummary` (Task 2); `useAuth`/`useApiError`; i18n `exports.*` + `errors.*` + `common.loading`.
- Produces (Task 4): `ExportApprovals` (default della rotta `/export-approvals`).

- [ ] **Step 1: Scrivi i test (`ExportApprovals.test.tsx`)**

```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, EXPORT_REQUEST } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ExportApprovals } from './ExportApprovals'

afterEach(() => sessionStorage.clear())

function sup(overrides = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, ...overrides })
}

test('shows the pending queue with requester, readable scope, and reason', async () => {
  setToken('tok')
  renderWithProviders(<ExportApprovals />, { client: sup(), route: '/export-approvals' })
  expect(await screen.findByText('m.rossi')).toBeInTheDocument()
  expect(screen.getByText('cucina')).toBeInTheDocument()
  expect(screen.getByText('Azienda X')).toBeInTheDocument()
})

test('empty filters render as «Tutti i profili»', async () => {
  setToken('tok')
  const allProfiles = { ...EXPORT_REQUEST, id: 9, filters: {} }
  renderWithProviders(<ExportApprovals />, { client: sup({ pending: { status: 'ok', requests: [allProfiles] } }), route: '/export-approvals' })
  expect(await screen.findByText('Tutti i profili')).toBeInTheDocument()
})

test('approve asks for confirmation then calls approveExport and reloads', async () => {
  setToken('tok')
  const client = sup()
  renderWithProviders(<ExportApprovals />, { client, route: '/export-approvals' })
  await screen.findByText('m.rossi')
  await userEvent.click(screen.getByRole('button', { name: 'Approva' }))
  await userEvent.click(screen.getByRole('button', { name: 'Conferma' }))
  await waitFor(() => expect(client.approvedIds).toEqual([1]))
  await waitFor(() => expect(client.calls.expPending).toBe(2))
})

test('deny requires a reason and sends it', async () => {
  setToken('tok')
  const client = sup()
  renderWithProviders(<ExportApprovals />, { client, route: '/export-approvals' })
  await screen.findByText('m.rossi')
  await userEvent.click(screen.getByRole('button', { name: 'Nega' }))
  const confirm = screen.getByRole('button', { name: 'Conferma rifiuto' })
  expect(confirm).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Motivo del rifiuto'), 'fuori scopo')
  await userEvent.click(confirm)
  await waitFor(() => expect(client.deniedExports).toEqual([{ id: 1, reason: 'fuori scopo' }]))
})

test('403 on mount shows the error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(<ExportApprovals />, { client: sup({ pending: { status: 'forbidden' } }), route: '/export-approvals' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/screens/exports/ExportApprovals.test.tsx`
Expected: FAIL (moduli inesistenti).

- [ ] **Step 3: Implementa `DenyDialog.tsx`**

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export function DenyDialog({
  title,
  onConfirm,
  onCancel,
}: {
  title: string
  onConfirm: (reason: string) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h2>{title}</h2>
        <label>{t('exports.denyReason')}
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <div className="modal-actions">
          <button type="button" onClick={onCancel}>{t('exports.cancel')}</button>
          <button type="button" className="primary" disabled={!reason.trim()} onClick={() => onConfirm(reason.trim())}>
            {t('exports.denyConfirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Implementa `ExportApprovals.tsx`**

```tsx
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { ExportRequest } from '../../types'
import { ConfirmDialog } from '../operators/ConfirmDialog'
import { DenyDialog } from './DenyDialog'
import { filterSummary } from './filterSummary'

export function ExportApprovals() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [pending, setPending] = useState<ExportRequest[] | null>(null)
  const [error, setError] = useState('')
  const [approving, setApproving] = useState<ExportRequest | null>(null)
  const [denying, setDenying] = useState<ExportRequest | null>(null)

  const onErr = useCallback(
    (status: 'unauthorized' | 'forbidden' | 'error') => {
      const outcome = handleError(status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    },
    [handleError, t],
  )

  const load = useCallback(async () => {
    setError('')
    const r = await client.listPendingExports()
    if (r.status === 'ok') setPending(r.requests)
    else onErr(r.status)
  }, [client, onErr])

  useEffect(() => {
    void load()
  }, [load])

  async function confirmApprove() {
    if (!approving) return
    const req = approving
    setApproving(null)
    const r = await client.approveExport(req.id)
    if (r.status === 'ok' || r.status === 'conflict' || r.status === 'not-found') void load()
    else onErr(r.status)
  }

  async function confirmDeny(reason: string) {
    if (!denying) return
    const req = denying
    setDenying(null)
    const r = await client.denyExport(req.id, reason)
    if (r.status === 'ok' || r.status === 'conflict' || r.status === 'not-found') void load()
    else onErr(r.status)
  }

  return (
    <div className="op-admin">
      <h1>{t('exports.approvalsTitle')}</h1>

      {error && <p className="error" role="alert">{error}</p>}
      {pending === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        pending &&
        (pending.length === 0 ? (
          <p>{t('exports.emptyPending')}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t('exports.colRequester')}</th>
                <th>{t('exports.colFilters')}</th>
                <th>{t('exports.colOutcome')}</th>
                <th>{t('exports.colDate')}</th>
                <th>{t('exports.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {pending.map((req) => (
                <tr key={req.id}>
                  <td>{req.requested_by}</td>
                  <td>{filterSummary(req.filters, t)}</td>
                  <td>{req.reason}</td>
                  <td>{req.created_at.slice(0, 10)}</td>
                  <td className="op-actions">
                    <button type="button" onClick={() => setApproving(req)}>{t('exports.approve')}</button>
                    <button type="button" onClick={() => setDenying(req)}>{t('exports.deny')}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))
      )}

      {approving && (
        <ConfirmDialog
          message={t('exports.confirmApprove', {
            who: approving.requested_by,
            scope: filterSummary(approving.filters, t),
            reason: approving.reason,
          })}
          confirmLabel={t('exports.confirm')}
          onConfirm={confirmApprove}
          onCancel={() => setApproving(null)}
        />
      )}
      {denying && (
        <DenyDialog
          title={t('exports.denyTitle', { who: denying.requested_by })}
          onConfirm={confirmDeny}
          onCancel={() => setDenying(null)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 5: Esegui i test + gate**

Run: `cd operator-portal && npx vitest run src/screens/exports/ExportApprovals.test.tsx && npm run typecheck && npm run lint`
Expected: PASS, pristine.

- [ ] **Step 6: Commit**

```bash
git add operator-portal/src/screens/exports/DenyDialog.tsx operator-portal/src/screens/exports/ExportApprovals.tsx operator-portal/src/screens/exports/ExportApprovals.test.tsx
git commit -m "feat(operator-portal): supervisor export-approvals queue (approve/deny)"
```

---

### Task 4: Nav (2 link) + rotte `/export` e `/export-approvals` + integrazione

**Files:**
- Modify: `operator-portal/src/rbac/nav.ts`
- Modify: `operator-portal/src/App.tsx`
- Modify: `operator-portal/src/shell/Nav.test.tsx`
- Modify: `operator-portal/src/App.test.tsx`

**Interfaces:**
- Consumes: `ExportRequests` (Task 2), `ExportApprovals` (Task 3).
- Produces: rotte `/export` (operatore) e `/export-approvals` (supervisore) funzionanti.

- [ ] **Step 1: Aggiorna il test della Nav (`Nav.test.tsx`)**

Sostituisci il test «the built sections render real links; others stay disabled» (operatore) affinché «Export» sia ora un link reale, e aggiungi un test supervisore per «Approvazioni export». Prima, aggiorna il test operatore esistente:
```tsx
test('the built sections render real links; Export is built too', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, { client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } }) })
  expect(await screen.findByRole('link', { name: /Richieste di lavoro/ })).toHaveAttribute('href', '/job-requests')
  expect(await screen.findByRole('link', { name: /Profili/ })).toHaveAttribute('href', '/profiles')
  expect(await screen.findByRole('link', { name: /Export/ })).toHaveAttribute('href', '/export')
})
```
Poi aggiungi:
```tsx
test('supervisor sees «Approvazioni export» as a real link', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, { client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } }) })
  expect(await screen.findByRole('link', { name: /Approvazioni export/ })).toHaveAttribute('href', '/export-approvals')
})
```

- [ ] **Step 2: Aggiungi i test d'integrazione (`App.test.tsx`)**

Append:
```tsx
test('an operator can reach the export section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } })
  renderApp(client, '/export')
  expect(await screen.findByRole('button', { name: /Nuova richiesta/ })).toBeInTheDocument()
})

test('a supervisor can reach the export-approvals section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  renderApp(client, '/export-approvals')
  expect(await screen.findByText('Approvazioni export')).toBeInTheDocument()
})
```

- [ ] **Step 3: Esegui — i test d'integrazione devono fallire**

Run: `cd operator-portal && npx vitest run src/App.test.tsx src/shell/Nav.test.tsx`
Expected: FAIL (rotte assenti / «Export» non ancora link / «Approvazioni export» assente).

- [ ] **Step 4: Marca le voci di nav (`rbac/nav.ts`)**

Nel blocco `operator`, cambia la riga `export`:
```ts
    { path: '/export', labelKey: 'nav.export', built: true },
```
Nel blocco `supervisor`, aggiungi (dopo `activity` o prima — l'ordine è UX):
```ts
    { path: '/export-approvals', labelKey: 'nav.exportApprovals', built: true },
```

- [ ] **Step 5: Aggancia le rotte (`App.tsx`)**

Aggiungi gli import: `import { ExportRequests } from './screens/exports/ExportRequests'` e `import { ExportApprovals } from './screens/exports/ExportApprovals'`. Dentro il blocco `<Route path="/" …>`, dopo `metrics`, aggiungi:
```tsx
        <Route path="export" element={<ExportRequests />} />
        <Route path="export-approvals" element={<ExportApprovals />} />
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
git commit -m "feat(operator-portal): wire export + export-approvals routes and nav links"
```

---

## Self-Review

- **Spec coverage:** §2 obiettivi → client 6 metodi+download-Blob (T1), superficie operatore (T2), superficie supervisore (T3), nav+rotte (T4). Gate server-side (download 409/404 come degrado), motivo obbligatorio (form + deny), «Tutti i profili» (filterSummary), Approva-conferma/Nega-motivo (ConfirmDialog + DenyDialog), download come file (saveBlob seam). Tutti coperti.
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto.
- **Type consistency:** `ExportRequest`/`ExportStatus`/le result-union (T1) usate da client, fake e schermate (T2/T3); `filters: ProfileFilters` riusato; `filterSummary(filters, t)` definita in T2 e riusata in T3; `saveBlob(blob, filename)` seam (default in `download.ts`, prop in `ExportRequests`); i metodi client `createExport(filters, reason)`/`approveExport(id)`/`denyExport(id, reason)`/`downloadExport(id)` con le stesse firme in T1 e nelle schermate; `MutateExportResult` include `conflict`/`not-found`, `DownloadExportResult` include `not-approved`/`not-found`; i18n `exports.*`+`nav.exportApprovals` (T1) consumati da T2–T4; riuso etichette S13 (`profiles.filter*`, `pl.*`).
- **Rossa/privacy:** il Download è UI-comodità, il gate è server-side; la coda mostra metadati (no profili/PII); «Tutti i profili» esplicito; loading gated `!error`.
