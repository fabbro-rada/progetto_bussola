# Portale Operatore — Richieste + Matching spiegabile — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the operator portal's "Richieste di lavoro + matching spiegabile" section (sub-project 2/5): create/list/view job requests and run an explainable match, on the S11 shell, consuming the S6 API.

**Architecture:** Extend the existing `operatorClient` (S11) with feature methods (fail-closed, Bearer) and expose the injected client via `useAuth().client`. A `useApiError` hook centralizes 401→logout / 403 / error handling. New screens under `/job-requests` render inside the S11 `AppShell`; the matching results are expandable per-candidate cards showing per-requirement verdicts with cited evidence and gaps→training. Only compatible candidates are shown (the S6 `/match` endpoint returns only those, by design).

**Tech Stack:** React 18 + Vite + TS + react-router-dom + react-i18next, Vitest + @testing-library/react. Extends `operator-portal/`. No new dependencies.

## Global Constraints

- Local/offline, open-source permissive only; **no new dependencies**. Code English; all user strings i18n-externalized (Italian catalog, §11).
- Extends the S11 `operator-portal/` app (do not touch `frontend/`, the kiosk).
- Feature calls carry `Authorization: Bearer` (from sessionStorage, via the existing `headers()`); **fail-closed** — every method returns a typed result, never throws: 200/201→ok, 401→unauthorized, 403→forbidden, 404→not-found (get only), network/5xx/parse→error.
- **401 on any feature call → `onUnauthorized()` (clears session) + redirect to `/login`** (which shows the S11 «sessione scaduta» notice). This realizes the S11 follow-up for feature calls. 403→«non autorizzato» message; error→retryable message.
- **Only compatible candidates are shown** — the S6 `/match` endpoint returns only compatible ones (excluded are dropped by design, §5 minimization). Do NOT add an "excluded" list; do NOT change the backend.
- **Matching runs on an explicit click** («Esegui matching»), never automatically (LLM latency, §10; on-demand per S6).
- **Explainability (§2/§10, "mai una scatola nera"):** each candidate shows a transparent **fraction** (satisfied/total requirements), per-requirement ✓/✗ **with cited evidence**, and **gaps→recommended training**.
- **No PII (§5):** candidates are shown by opaque `pseudonym_id`; evidence text arrives already PII-filtered from the backend (S4/S6) — the UI does not reintroduce PII.
- The job-request form exposes ONLY the work-only `JobRequestCreate` fields (the backend schema is `extra="forbid"`).
- RBAC (§6): the section is operator-role, behind the S11 `ProtectedRoute`; the server remains the authority (403). TDD; only synthetic data; pristine test output.

## Backend contract (exact — S6)
- `GET /job-requests` → `JobRequest[]`; `POST /job-requests` (body `JobRequestCreate`) → 201 `JobRequest`; `GET /job-requests/{id}` → `JobRequest` | 404; `POST /job-requests/{id}/match` → `MatchResult[]` (only compatible).
- `JobRequestCreate`: `{ title, sector, description, required_skills: string[], required_languages: {language, min_level}[], required_availability: Availability|null, involves_night_shifts: boolean, training_prerequisites: string[] }`. `JobRequest` adds `{ id, created_by }`.
- `LanguageLevel`: `'basic'|'intermediate'|'fluent'|'native'`. `Availability`: `'full_time'|'part_time'|'flexible'`.
- `MatchResult`: `{ pseudonym_id: string, score: number, requirements: {requirement, satisfied, evidence|null}[], constraint: {compatible, reasons[]}, gaps: {requirement, recommended_training}[] }`.

---

## File Structure

```
operator-portal/src/
  types.ts                         (Task 1 — extend: JobRequest*, MatchResult*, feature result unions, enums)
  api/operatorClient.ts            (Task 1 — extend: listJobRequests/getJobRequest/createJobRequest/runMatch)
  test/fakeClient.ts               (Task 1 — extend fake with feature methods)
  auth/AuthContext.tsx             (Task 1 — expose `client` via useAuth)
  i18n/locales/it.ts               (Task 1 — add section strings)
  hooks/useApiError.ts             (Task 2)
  rbac/nav.ts                      (Task 3 — add `built` flag; jobRequests built)
  shell/Nav.tsx                    (Task 3 — real <Link> for built items)
  screens/jobRequests/JobRequestList.tsx      (Task 3)
  screens/jobRequests/JobRequestCreate.tsx    (Task 4)
  screens/jobRequests/MatchResults.tsx        (Task 5)
  screens/jobRequests/JobRequestDetail.tsx    (Task 6)
  App.tsx                          (Task 6 — nested routes)
```
Each `*.ts(x)` gets a sibling `*.test.ts(x)`.

---

## Task 1: types + `operatorClient` feature methods + fake + expose client + i18n

**Files:**
- Modify: `src/types.ts`, `src/api/operatorClient.ts`, `src/test/fakeClient.ts`, `src/auth/AuthContext.tsx`, `src/i18n/locales/it.ts`
- Test: `src/api/operatorClient.test.ts` (extend)

**Interfaces:**
- Produces (types): `LanguageLevel`, `Availability`, `RequiredLanguage`, `JobRequestCreate`, `JobRequest`, `RequirementVerdict`, `ConstraintOutcome`, `GapItem`, `MatchResult`, and result unions `ListJobRequestsResult`, `GetJobRequestResult`, `CreateJobRequestResult`, `MatchResultsResult`.
- `OperatorClient` gains: `listJobRequests()`, `getJobRequest(id)`, `createJobRequest(body)`, `runMatch(id)`.
- `AuthValue` gains `client: OperatorClient` (the injected client, so feature screens call `useAuth().client`).

- [ ] **Step 1: Write the failing test** (extend `src/api/operatorClient.test.ts`)

```ts
// add near the other tests (res() helper + setToken already imported)
const JOB = {
  id: 7, title: 'Aiuto cuoco', sector: 'Ristorazione', description: '', created_by: 'mrossi',
  required_skills: ['cucina'], required_languages: [{ language: 'it', min_level: 'intermediate' }],
  required_availability: 'full_time', involves_night_shifts: false, training_prerequisites: [],
}
const MATCH = {
  pseudonym_id: 'P-4F2A', score: 0.75,
  requirements: [{ requirement: 'Esperienza in cucina', satisfied: true, evidence: 'ho lavorato in un ristorante' }],
  constraint: { compatible: true, reasons: [] },
  gaps: [{ requirement: 'HACCP', recommended_training: 'Corso HACCP base' }],
}

test('listJobRequests: 200→ok with Bearer; 401→unauthorized; 403→forbidden', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, [JOB]))
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.listJobRequests()
  expect(r).toEqual({ status: 'ok', jobs: [JOB] })
  expect(String(f.mock.calls[0][0])).toContain('/job-requests')
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.listJobRequests()).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.listJobRequests()).toEqual({ status: 'forbidden' })
})

test('getJobRequest: 200→ok; 404→not-found', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(200, JOB)))
  expect(await operatorClient.getJobRequest(7)).toEqual({ status: 'ok', job: JOB })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(404)))
  expect(await operatorClient.getJobRequest(7)).toEqual({ status: 'not-found' })
})

test('createJobRequest: posts the body and maps 201→ok', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(201, JOB))
  vi.stubGlobal('fetch', f)
  const body = { title: 'Aiuto cuoco', sector: 'Ristorazione', description: '', required_skills: ['cucina'], required_languages: [{ language: 'it', min_level: 'intermediate' as const }], required_availability: 'full_time' as const, involves_night_shifts: false, training_prerequisites: [] }
  const r = await operatorClient.createJobRequest(body)
  expect(r).toEqual({ status: 'ok', job: JOB })
  expect((f.mock.calls[0][1] as RequestInit).method).toBe('POST')
  expect(JSON.parse((f.mock.calls[0][1] as RequestInit).body as string)).toEqual(body)
})

test('runMatch: 200→ok with results; network→error', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(200, [MATCH])))
  expect(await operatorClient.runMatch(7)).toEqual({ status: 'ok', results: [MATCH] })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.runMatch(7)).toEqual({ status: 'error' })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- operatorClient`
Expected: FAIL (methods not defined).

- [ ] **Step 3: Extend `types.ts`**

Append:
```ts
export type LanguageLevel = 'basic' | 'intermediate' | 'fluent' | 'native'
export type Availability = 'full_time' | 'part_time' | 'flexible'

export interface RequiredLanguage {
  language: string
  min_level: LanguageLevel
}

export interface JobRequestCreate {
  title: string
  sector: string
  description: string
  required_skills: string[]
  required_languages: RequiredLanguage[]
  required_availability: Availability | null
  involves_night_shifts: boolean
  training_prerequisites: string[]
}

export interface JobRequest extends JobRequestCreate {
  id: number
  created_by: string
}

export interface RequirementVerdict {
  requirement: string
  satisfied: boolean
  evidence: string | null
}
export interface ConstraintOutcome {
  compatible: boolean
  reasons: string[]
}
export interface GapItem {
  requirement: string
  recommended_training: string
}
export interface MatchResult {
  pseudonym_id: string
  score: number
  requirements: RequirementVerdict[]
  constraint: ConstraintOutcome
  gaps: GapItem[]
}

export type ListJobRequestsResult =
  | { status: 'ok'; jobs: JobRequest[] }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type GetJobRequestResult =
  | { status: 'ok'; job: JobRequest }
  | { status: 'not-found' }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type CreateJobRequestResult =
  | { status: 'ok'; job: JobRequest }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type MatchResultsResult =
  | { status: 'ok'; results: MatchResult[] }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
```
And extend the `OperatorClient` interface (add the 4 methods inside it):
```ts
export interface OperatorClient {
  login(username: string, password: string): Promise<LoginResult>
  me(): Promise<MeResult>
  logout(): Promise<void>
  changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult>
  listJobRequests(): Promise<ListJobRequestsResult>
  getJobRequest(id: number): Promise<GetJobRequestResult>
  createJobRequest(body: JobRequestCreate): Promise<CreateJobRequestResult>
  runMatch(id: number): Promise<MatchResultsResult>
}
```

- [ ] **Step 4: Extend `operatorClient.ts`** (add the 4 methods; reuse `headers(true)`/`headers(false)`)

Add before the final `export const operatorClient`:
```ts
async function listJobRequests(): Promise<ListJobRequestsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/job-requests`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', jobs: (await res.json()) as JobRequest[] }
  } catch {
    return { status: 'error' }
  }
}

async function getJobRequest(id: number): Promise<GetJobRequestResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/job-requests/${id}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 404) return { status: 'not-found' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', job: (await res.json()) as JobRequest }
  } catch {
    return { status: 'error' }
  }
}

async function createJobRequest(body: JobRequestCreate): Promise<CreateJobRequestResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/job-requests`, { method: 'POST', headers: headers(true), body: JSON.stringify(body) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', job: (await res.json()) as JobRequest }
  } catch {
    return { status: 'error' }
  }
}

async function runMatch(id: number): Promise<MatchResultsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/job-requests/${id}/match`, { method: 'POST', headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', results: (await res.json()) as MatchResult[] }
  } catch {
    return { status: 'error' }
  }
}
```
Update the imports (`import type { ... ListJobRequestsResult, GetJobRequestResult, CreateJobRequestResult, MatchResultsResult, JobRequest, JobRequestCreate } from '../types'`) and add the 4 to the exported object:
```ts
export const operatorClient: OperatorClient = { login, me, logout, changePassword, listJobRequests, getJobRequest, createJobRequest, runMatch }
```

- [ ] **Step 5: Extend `test/fakeClient.ts`**

Extend `makeFakeClient`'s `opts` and returned object with the feature methods + call counters. Add sample fixtures `JOB`/`MATCH` exports for reuse:
```ts
import type {
  ChangeResult, CreateJobRequestResult, GetJobRequestResult, JobRequest,
  ListJobRequestsResult, LoginResult, MatchResult, MatchResultsResult, MeResult, Operator, OperatorClient, Role,
} from '../types'

export const JOB: JobRequest = {
  id: 7, title: 'Aiuto cuoco', sector: 'Ristorazione', description: '',
  required_skills: ['cucina'], required_languages: [{ language: 'it', min_level: 'intermediate' }],
  required_availability: 'full_time', involves_night_shifts: false, training_prerequisites: [], created_by: 'mrossi',
}
export const MATCH: MatchResult = {
  pseudonym_id: 'P-4F2A', score: 0.75,
  requirements: [
    { requirement: 'Esperienza in cucina', satisfied: true, evidence: 'ho lavorato in un ristorante' },
    { requirement: 'Attestato HACCP', satisfied: false, evidence: null },
  ],
  constraint: { compatible: true, reasons: [] },
  gaps: [{ requirement: 'Attestato HACCP', recommended_training: 'Corso HACCP base (8 ore)' }],
}

export function makeFakeClient(opts: {
  login?: LoginResult
  me?: MeResult
  change?: ChangeResult
  jobs?: ListJobRequestsResult
  job?: GetJobRequestResult
  create?: CreateJobRequestResult
  match?: MatchResultsResult
} = {}): OperatorClient & {
  calls: { login: number; me: number; logout: number; change: number; list: number; get: number; create: number; match: number }
  created: import('../types').JobRequestCreate[]
} {
  const calls = { login: 0, me: 0, logout: 0, change: 0, list: 0, get: 0, create: 0, match: 0 }
  const created: import('../types').JobRequestCreate[] = []
  return {
    calls,
    created,
    async login() { calls.login++; return opts.login ?? { status: 'ok', token: 'tok', operator: OPERATOR, mustChangePassword: false } },
    async me() { calls.me++; return opts.me ?? { status: 'unauthorized' } },
    async logout() { calls.logout++ },
    async changePassword() { calls.change++; return opts.change ?? { status: 'ok' } },
    async listJobRequests() { calls.list++; return opts.jobs ?? { status: 'ok', jobs: [JOB] } },
    async getJobRequest() { calls.get++; return opts.job ?? { status: 'ok', job: JOB } },
    async createJobRequest(body) { calls.create++; created.push(body); return opts.create ?? { status: 'ok', job: JOB } },
    async runMatch() { calls.match++; return opts.match ?? { status: 'ok', results: [MATCH] } },
  }
}
```
(Keep the existing `OPERATOR`/`operatorWith`/`ROLES` exports.)

- [ ] **Step 6: Expose `client` via `AuthContext`**

In `src/auth/AuthContext.tsx`: add `client: OperatorClient` to the `AuthValue` interface, and include `client` in the context `value` object (the `client` prop is already in scope). No other change.

- [ ] **Step 7: Add the section i18n strings** to `src/i18n/locales/it.ts`

Add these keys (merge into the existing catalog object):
```ts
  jobRequests: {
    title: 'Richieste di lavoro',
    new: 'Nuova richiesta',
    empty: 'Nessuna richiesta di lavoro.',
    colTitle: 'Titolo',
    colSector: 'Settore',
    colCreatedBy: 'Creata da',
  },
  jobForm: {
    title: 'Titolo',
    sector: 'Settore',
    description: 'Descrizione',
    skills: 'Competenze richieste (separate da virgola)',
    languages: 'Lingue richieste',
    language: 'Lingua',
    level: 'Livello minimo',
    addLanguage: 'Aggiungi lingua',
    removeLanguage: 'Rimuovi',
    availability: 'Disponibilità',
    availabilityNone: 'Non specificata',
    nightShifts: 'Prevede turni notturni',
    prerequisites: 'Prerequisiti formativi (separati da virgola)',
    submit: 'Crea richiesta',
    level_basic: 'Base',
    level_intermediate: 'Intermedio',
    level_fluent: 'Fluente',
    level_native: 'Madrelingua',
    availability_full_time: 'Tempo pieno',
    availability_part_time: 'Part-time',
    availability_flexible: 'Flessibile',
  },
  detail: {
    requirements: 'Requisiti della richiesta',
    runMatch: 'Esegui matching',
    calculating: 'Sto calcolando i candidati…',
    noResults: 'Nessun candidato compatibile.',
    back: 'Torna alle richieste',
  },
  match: {
    fraction: '{{n}}/{{total}} requisiti',
    constraintOk: 'Vincoli ok',
    evidence: 'Evidenza',
    noEvidence: 'non risulta',
    gapsTitle: 'Gap → formazione consigliata',
    expand: 'Dettagli',
    collapse: 'Nascondi',
  },
```
Plus — add these two keys INTO the **existing** `errors` object (which already has `invalidCredentials`/`sessionExpired`/`generic`); do NOT create a second `errors:` key (that would duplicate and drop the S11 keys):
```ts
    forbidden: 'Non hai i permessi per questa azione.',
    notFound: 'Elemento non trovato.',
```
(The `jobRequests`/`jobForm`/`detail`/`match` groups above are new sibling objects; reuse the existing `errors.generic`/`errors.sessionExpired`. All screens/hooks use `errors.forbidden`/`errors.notFound`.)

- [ ] **Step 8: Run the tests and the gate**

Run: `npm test -- operatorClient && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add operator-portal/src/types.ts operator-portal/src/api operator-portal/src/test/fakeClient.ts operator-portal/src/auth/AuthContext.tsx operator-portal/src/i18n/locales/it.ts
git commit -m "feat(operator-portal): job-request/match client methods + types + expose client + i18n"
```

---

## Task 2: `useApiError` hook

**Files:**
- Create: `src/hooks/useApiError.ts`
- Test: `src/hooks/useApiError.test.tsx`

**Interfaces:**
- Consumes: `useAuth().onUnauthorized`, react-router `useNavigate`.
- Produces: `useApiError(): (status: 'unauthorized' | 'forbidden' | 'not-found' | 'error') => 'forbidden' | 'not-found' | 'error' | 'handled'` — on `'unauthorized'` it calls `onUnauthorized()` + `navigate('/login', { replace: true })` and returns `'handled'` (the S11 flag makes Login show «sessione scaduta»); otherwise returns the status unchanged for the caller to render a message.

- [ ] **Step 1: Write the failing test**

`src/hooks/useApiError.test.tsx`:
```tsx
import { renderHook } from '@testing-library/react'
import { expect, test, vi, afterEach } from 'vitest'
import { type ReactNode } from 'react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import i18n from '../i18n'
import { AuthProvider } from '../auth/AuthContext'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { setToken, getToken } from '../auth/session'
import { useApiError } from './useApiError'

afterEach(() => sessionStorage.clear())

function wrap(): ({ children }: { children: ReactNode }) => JSX.Element {
  return ({ children }) => (
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={['/x']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider client={makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })}>
          <Routes>
            <Route path="/x" element={<>{children}</>} />
            <Route path="/login" element={<div>LOGIN</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </I18nextProvider>
  )
}

test('unauthorized clears the token and is reported as handled', () => {
  setToken('tok')
  const { result } = renderHook(() => useApiError(), { wrapper: wrap() })
  expect(result.current('unauthorized')).toBe('handled')
  expect(getToken()).toBeNull()
})

test('forbidden/not-found/error are returned unchanged', () => {
  const { result } = renderHook(() => useApiError(), { wrapper: wrap() })
  expect(result.current('forbidden')).toBe('forbidden')
  expect(result.current('not-found')).toBe('not-found')
  expect(result.current('error')).toBe('error')
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- useApiError`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `useApiError.ts`**

```ts
import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

type ErrorStatus = 'unauthorized' | 'forbidden' | 'not-found' | 'error'

export function useApiError(): (status: ErrorStatus) => 'forbidden' | 'not-found' | 'error' | 'handled' {
  const { onUnauthorized } = useAuth()
  const navigate = useNavigate()
  return useCallback(
    (status: ErrorStatus) => {
      if (status === 'unauthorized') {
        onUnauthorized() // sets the S11 sessionExpired flag; Login renders the notice
        navigate('/login', { replace: true })
        return 'handled' as const
      }
      return status
    },
    [onUnauthorized, navigate],
  )
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- useApiError && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add operator-portal/src/hooks/useApiError.ts operator-portal/src/hooks/useApiError.test.tsx
git commit -m "feat(operator-portal): useApiError hook (401→logout+redirect; 403/404/error passthrough)"
```

---

## Task 3: `JobRequestList` + Nav real link

**Files:**
- Create: `src/screens/jobRequests/JobRequestList.tsx`
- Modify: `src/rbac/nav.ts` (add `built` flag), `src/shell/Nav.tsx` (render `<Link>` for built items), `src/shell/Nav.test.tsx` (add a link assertion)
- Test: `src/screens/jobRequests/JobRequestList.test.tsx`

**Interfaces:**
- `NavItem` gains `built?: boolean`; `jobRequests` is `built: true`.
- `Nav` renders a `<Link to={item.path}>` for `built` items, the disabled placeholder otherwise.
- `JobRequestList()` — loads via `useAuth().client.listJobRequests()` on mount; renders a table (title, sector, created_by) with each row linking to `/job-requests/:id`, a «Nuova richiesta» link to `/job-requests/new`, and an empty state; on non-ok uses `useApiError` (unauthorized handled; forbidden/error → message).

- [ ] **Step 1: Write the failing tests**

`src/screens/jobRequests/JobRequestList.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, JOB } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { JobRequestList } from './JobRequestList'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/job-requests" element={<JobRequestList />} />
      <Route path="/job-requests/new" element={<div>NEW</div>} />
      <Route path="/job-requests/:id" element={<div>DETAIL</div>} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

test('renders the job requests with a link to each detail and to new', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, jobs: { status: 'ok', jobs: [JOB] } })
  renderWithProviders(harness(), { client, route: '/job-requests' })
  expect(await screen.findByText('Aiuto cuoco')).toBeInTheDocument()
  expect(screen.getByText('Ristorazione')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Nuova richiesta' })).toHaveAttribute('href', '/job-requests/new')
})

test('empty state when there are no requests', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, jobs: { status: 'ok', jobs: [] } })
  renderWithProviders(harness(), { client, route: '/job-requests' })
  expect(await screen.findByText('Nessuna richiesta di lavoro.')).toBeInTheDocument()
})

test('401 while listing redirects to login', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, jobs: { status: 'unauthorized' } })
  renderWithProviders(harness(), { client, route: '/job-requests' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})
```
Add to `src/shell/Nav.test.tsx` (keep existing tests):
```tsx
test('the built job-requests item is a real link; others stay disabled', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, { client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } }) })
  expect(await screen.findByRole('link', { name: /Richieste di lavoro/ })).toHaveAttribute('href', '/job-requests')
  // 'Profili' is not yet built → not a link
  expect(screen.queryByRole('link', { name: /Profili/ })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- JobRequestList Nav`
Expected: FAIL (module not found; no link yet).

- [ ] **Step 3: Update `rbac/nav.ts`** — add `built?: boolean` to `NavItem` and mark job-requests built:
```ts
export interface NavItem {
  path: string
  labelKey: string
  built?: boolean
}
// ...operator array's first item:
{ path: '/job-requests', labelKey: 'nav.jobRequests', built: true },
```
(leave the other items without `built`.)

- [ ] **Step 4: Update `shell/Nav.tsx`** — render a `<Link>` for built items:
```tsx
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import { NAV_BY_ROLE } from '../rbac/nav'

export function Nav() {
  const { t } = useTranslation()
  const { operator } = useAuth()
  if (!operator) return null
  const items = NAV_BY_ROLE[operator.role]
  return (
    <nav className="nav" aria-label={t('nav.ariaLabel')}>
      <ul>
        {items.map((item) => (
          <li key={item.path}>
            {item.built ? (
              <Link className="nav-item" to={item.path}>
                {t(item.labelKey)}
              </Link>
            ) : (
              <span className="nav-item disabled" aria-disabled="true">
                {t(item.labelKey)} <em className="coming">({t('common.comingSoon')})</em>
              </span>
            )}
          </li>
        ))}
      </ul>
    </nav>
  )
}
```

- [ ] **Step 5: Implement `JobRequestList.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { JobRequest } from '../../types'

export function JobRequestList() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<JobRequest[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void client.listJobRequests().then((r) => {
      if (!active) return
      if (r.status === 'ok') setJobs(r.jobs)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    })
    return () => {
      active = false
    }
  }, [client, handleError, t])

  if (error) return <p className="error" role="alert">{error}</p>
  if (jobs === null) return <p>{t('common.loading')}</p>

  return (
    <div className="job-list">
      <div className="section-head">
        <h1>{t('jobRequests.title')}</h1>
        <Link className="btn" to="/job-requests/new">{t('jobRequests.new')}</Link>
      </div>
      {jobs.length === 0 ? (
        <p>{t('jobRequests.empty')}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>{t('jobRequests.colTitle')}</th>
              <th>{t('jobRequests.colSector')}</th>
              <th>{t('jobRequests.colCreatedBy')}</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} onClick={() => navigate(`/job-requests/${j.id}`)} style={{ cursor: 'pointer' }}>
                <td><Link to={`/job-requests/${j.id}`}>{j.title}</Link></td>
                <td>{j.sector}</td>
                <td>{j.created_by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
```
(`errors.forbidden`/`errors.generic` come from the existing `errors` object extended in Task 1.)

- [ ] **Step 6: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS (existing Nav tests still green — the built item still shows its text, now as a link).

- [ ] **Step 7: Commit**

```bash
git add operator-portal/src/screens/jobRequests/JobRequestList.tsx operator-portal/src/screens/jobRequests/JobRequestList.test.tsx operator-portal/src/rbac/nav.ts operator-portal/src/shell/Nav.tsx operator-portal/src/shell/Nav.test.tsx
git commit -m "feat(operator-portal): job requests list + real nav link for built sections"
```

---

## Task 4: `JobRequestCreate` form

**Files:**
- Create: `src/screens/jobRequests/JobRequestCreate.tsx`
- Test: `src/screens/jobRequests/JobRequestCreate.test.tsx`

**Interfaces:**
- `JobRequestCreate()` — a form over the `JobRequestCreate` fields; on submit builds the body (splitting comma-separated skills/prerequisites; collecting language rows; availability select with a "none"→null option; night-shifts checkbox), calls `client.createJobRequest(body)`, and on `ok` navigates to `/job-requests/:id`; non-ok via `useApiError`.

- [ ] **Step 1: Write the failing test**

`src/screens/jobRequests/JobRequestCreate.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { JobRequestCreate } from './JobRequestCreate'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/job-requests/new" element={<JobRequestCreate />} />
      <Route path="/job-requests/:id" element={<div>DETAIL</div>} />
    </Routes>
  )
}

test('submits the work-only body and navigates to the created detail', async () => {
  setToken('tok')
  // create defaults to { status: 'ok', job: JOB } (id 7) → navigates to /job-requests/7
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  renderWithProviders(harness(), { client, route: '/job-requests/new' })
  await userEvent.type(screen.getByLabelText('Titolo'), 'Aiuto cuoco')
  await userEvent.type(screen.getByLabelText('Settore'), 'Ristorazione')
  await userEvent.type(screen.getByLabelText(/Competenze richieste/), 'cucina, igiene')
  await userEvent.click(screen.getByRole('button', { name: 'Crea richiesta' }))
  await waitFor(() => expect(screen.getByText('DETAIL')).toBeInTheDocument())
  expect(client.created[0]).toMatchObject({
    title: 'Aiuto cuoco',
    sector: 'Ristorazione',
    required_skills: ['cucina', 'igiene'],
    required_availability: null,
    involves_night_shifts: false,
    required_languages: [],
    training_prerequisites: [],
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- JobRequestCreate`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `JobRequestCreate.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { Availability, LanguageLevel, RequiredLanguage } from '../../types'

const LEVELS: LanguageLevel[] = ['basic', 'intermediate', 'fluent', 'native']
const AVAILABILITIES: Availability[] = ['full_time', 'part_time', 'flexible']

function splitCsv(s: string): string[] {
  return s.split(',').map((x) => x.trim()).filter(Boolean)
}

export function JobRequestCreate() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [sector, setSector] = useState('')
  const [description, setDescription] = useState('')
  const [skills, setSkills] = useState('')
  const [prerequisites, setPrerequisites] = useState('')
  const [languages, setLanguages] = useState<RequiredLanguage[]>([])
  const [availability, setAvailability] = useState<Availability | ''>('')
  const [nightShifts, setNightShifts] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function addLanguage() {
    setLanguages((ls) => [...ls, { language: '', min_level: 'basic' }])
  }
  function updateLanguage(i: number, patch: Partial<RequiredLanguage>) {
    setLanguages((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }
  function removeLanguage(i: number) {
    setLanguages((ls) => ls.filter((_, idx) => idx !== i))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    const body = {
      title,
      sector,
      description,
      required_skills: splitCsv(skills),
      required_languages: languages.filter((l) => l.language.trim() !== ''),
      required_availability: availability === '' ? null : availability,
      involves_night_shifts: nightShifts,
      training_prerequisites: splitCsv(prerequisites),
    }
    const r = await client.createJobRequest(body)
    setBusy(false)
    if (r.status === 'ok') navigate(`/job-requests/${r.job.id}`, { replace: true })
    else {
      const outcome = handleError(r.status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    }
  }

  return (
    <form className="job-form" onSubmit={submit}>
      <h1>{t('jobRequests.new')}</h1>
      <label>{t('jobForm.title')}<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      <label>{t('jobForm.sector')}<input value={sector} onChange={(e) => setSector(e.target.value)} /></label>
      <label>{t('jobForm.description')}<textarea value={description} onChange={(e) => setDescription(e.target.value)} /></label>
      <label>{t('jobForm.skills')}<input value={skills} onChange={(e) => setSkills(e.target.value)} /></label>

      <fieldset>
        <legend>{t('jobForm.languages')}</legend>
        {languages.map((l, i) => (
          <div key={i} className="lang-row">
            <input aria-label={`${t('jobForm.language')} ${i + 1}`} value={l.language} onChange={(e) => updateLanguage(i, { language: e.target.value })} />
            <select aria-label={`${t('jobForm.level')} ${i + 1}`} value={l.min_level} onChange={(e) => updateLanguage(i, { min_level: e.target.value as LanguageLevel })}>
              {LEVELS.map((lv) => <option key={lv} value={lv}>{t(`jobForm.level_${lv}`)}</option>)}
            </select>
            <button type="button" onClick={() => removeLanguage(i)}>{t('jobForm.removeLanguage')}</button>
          </div>
        ))}
        <button type="button" onClick={addLanguage}>{t('jobForm.addLanguage')}</button>
      </fieldset>

      <label>{t('jobForm.availability')}
        <select value={availability} onChange={(e) => setAvailability(e.target.value as Availability | '')}>
          <option value="">{t('jobForm.availabilityNone')}</option>
          {AVAILABILITIES.map((a) => <option key={a} value={a}>{t(`jobForm.availability_${a}`)}</option>)}
        </select>
      </label>
      <label className="check"><input type="checkbox" checked={nightShifts} onChange={(e) => setNightShifts(e.target.checked)} /> {t('jobForm.nightShifts')}</label>
      <label>{t('jobForm.prerequisites')}<input value={prerequisites} onChange={(e) => setPrerequisites(e.target.value)} /></label>

      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || !title || !sector}>{t('jobForm.submit')}</button>
    </form>
  )
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add operator-portal/src/screens/jobRequests/JobRequestCreate.tsx operator-portal/src/screens/jobRequests/JobRequestCreate.test.tsx
git commit -m "feat(operator-portal): job request create form (work-only fields)"
```

---

## Task 5: `MatchResults` — explainable candidate cards

**Files:**
- Create: `src/screens/jobRequests/MatchResults.tsx`
- Modify: `src/styles/theme.css` (append match/table/form styles)
- Test: `src/screens/jobRequests/MatchResults.test.tsx`

**Interfaces:**
- `MatchResults(props: { results: MatchResult[] })` — renders one expandable card per candidate: `pseudonym_id`, a transparent fraction `t('match.fraction', {n, total})` (n = satisfied count, total = requirements length), an expand toggle revealing per-requirement ✓/✗ + evidence and the gaps→training box. Empty `results` → `t('detail.noResults')`.

- [ ] **Step 1: Write the failing test**

`src/screens/jobRequests/MatchResults.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { MATCH } from '../../test/fakeClient'
import { MatchResults } from './MatchResults'

afterEach(() => sessionStorage.clear())

test('shows pseudonym, transparent fraction, and (expanded) verdicts with evidence + gaps', async () => {
  renderWithProviders(<MatchResults results={[MATCH]} />)
  expect(screen.getByText('P-4F2A')).toBeInTheDocument()
  expect(screen.getByText('1/2 requisiti')).toBeInTheDocument() // 1 satisfied of 2
  await userEvent.click(screen.getByRole('button', { name: /Dettagli/ }))
  expect(screen.getByText('Esperienza in cucina')).toBeInTheDocument()
  expect(screen.getByText(/ho lavorato in un ristorante/)).toBeInTheDocument()
  expect(screen.getByText(/Corso HACCP base/)).toBeInTheDocument()
})

test('empty results shows the no-candidates message', () => {
  renderWithProviders(<MatchResults results={[]} />)
  expect(screen.getByText('Nessun candidato compatibile.')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- MatchResults`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `MatchResults.tsx`**

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { MatchResult } from '../../types'

function Card({ result }: { result: MatchResult }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const satisfied = result.requirements.filter((r) => r.satisfied).length
  const total = result.requirements.length
  return (
    <div className="match-card">
      <div className="match-head">
        <span className="pseudonym">{result.pseudonym_id}</span>
        <span className="badges">
          <span className="badge ok">✓ {t('match.constraintOk')}</span>
          <span className="fraction">{t('match.fraction', { n: satisfied, total })}</span>
          <button type="button" className="expand" onClick={() => setOpen((o) => !o)}>
            {open ? t('match.collapse') : t('match.expand')}
          </button>
        </span>
      </div>
      {open && (
        <div className="match-detail">
          <ul className="verdicts">
            {result.requirements.map((r, i) => (
              <li key={i}>
                <span className={r.satisfied ? 'ok' : 'no'}>{r.satisfied ? '✓' : '✗'}</span> {r.requirement}
                {' — '}
                <em>{r.evidence ?? t('match.noEvidence')}</em>
              </li>
            ))}
          </ul>
          {result.gaps.length > 0 && (
            <div className="gaps">
              <strong>{t('match.gapsTitle')}</strong>
              <ul>
                {result.gaps.map((g, i) => (
                  <li key={i}>{g.requirement} → <em>{g.recommended_training}</em></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function MatchResults({ results }: { results: MatchResult[] }) {
  const { t } = useTranslation()
  if (results.length === 0) return <p>{t('detail.noResults')}</p>
  return (
    <div className="match-results">
      {results.map((r) => (
        <Card key={r.pseudonym_id} result={r} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Append styles to `theme.css`**

```css
.section-head { display: flex; align-items: center; justify-content: space-between; }
.btn { background: var(--accent); color: #fff; padding: 8px 14px; border-radius: 8px; text-decoration: none; font-weight: 700; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
.job-form { max-width: 640px; display: flex; flex-direction: column; gap: 12px; }
.job-form label { display: flex; flex-direction: column; gap: 4px; font-weight: 600; }
.job-form input, .job-form textarea, .job-form select { padding: 8px; border: 1px solid var(--border); border-radius: 8px; font: inherit; }
.job-form .check { flex-direction: row; align-items: center; gap: 8px; }
.lang-row { display: flex; gap: 8px; margin-bottom: 6px; }
.match-card { border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; }
.match-head { display: flex; align-items: center; justify-content: space-between; }
.match-head .badges { display: flex; gap: 8px; align-items: center; }
.badge.ok { background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 700; }
.match-detail { margin-top: 8px; padding-left: 8px; border-left: 3px solid var(--border); }
.verdicts { list-style: none; padding: 0; } .verdicts .ok { color: #15803d; font-weight: 700; } .verdicts .no { color: var(--danger); font-weight: 700; }
.gaps { background: #eff6ff; border-radius: 8px; padding: 8px; margin-top: 8px; }
```

- [ ] **Step 5: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add operator-portal/src/screens/jobRequests/MatchResults.tsx operator-portal/src/screens/jobRequests/MatchResults.test.tsx operator-portal/src/styles/theme.css
git commit -m "feat(operator-portal): explainable match results (expandable cards, fraction, evidence, gaps)"
```

---

## Task 6: `JobRequestDetail` + run matching + App routes + integration

**Files:**
- Create: `src/screens/jobRequests/JobRequestDetail.tsx`
- Modify: `src/App.tsx` (nested routes)
- Test: `src/screens/jobRequests/JobRequestDetail.test.tsx`, `src/App.test.tsx` (add a section flow test)

**Interfaces:**
- `JobRequestDetail()` — reads `:id` (react-router `useParams`), loads via `client.getJobRequest(id)`; shows the request's requirements + an «Esegui matching» button; on click calls `client.runMatch(id)` with a busy state and renders `<MatchResults results={...} />`; non-ok via `useApiError`.
- `App.tsx` gains nested routes under `/`: `job-requests`, `job-requests/new`, `job-requests/:id`.

- [ ] **Step 1: Write the failing tests**

`src/screens/jobRequests/JobRequestDetail.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, JOB, MATCH } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { JobRequestDetail } from './JobRequestDetail'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/job-requests/:id" element={<JobRequestDetail />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

test('shows the request then runs matching on click, rendering explainable results', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    job: { status: 'ok', job: JOB },
    match: { status: 'ok', results: [MATCH] },
  })
  renderWithProviders(harness(), { client, route: '/job-requests/7' })
  expect(await screen.findByText('Aiuto cuoco')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Esegui matching' }))
  expect(await screen.findByText('P-4F2A')).toBeInTheDocument()
  expect(client.calls.match).toBe(1)
})

test('no compatible candidates message when match returns empty', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    job: { status: 'ok', job: JOB },
    match: { status: 'ok', results: [] },
  })
  renderWithProviders(harness(), { client, route: '/job-requests/7' })
  await userEvent.click(await screen.findByRole('button', { name: 'Esegui matching' }))
  expect(await screen.findByText('Nessun candidato compatibile.')).toBeInTheDocument()
})
```
Add to `src/App.test.tsx` (a routed section-reachability test):
```tsx
test('an authenticated operator can navigate to the job-requests section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } })
  renderApp(client, '/job-requests')
  expect(await screen.findByText('Richieste di lavoro')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- JobRequestDetail App`
Expected: FAIL (module not found; route not wired).

- [ ] **Step 3: Implement `JobRequestDetail.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { JobRequest, MatchResult } from '../../types'
import { MatchResults } from './MatchResults'

export function JobRequestDetail() {
  const { t } = useTranslation()
  const { id } = useParams()
  const jobId = Number(id)
  const { client } = useAuth()
  const handleError = useApiError()
  const [job, setJob] = useState<JobRequest | null>(null)
  const [results, setResults] = useState<MatchResult[] | null>(null)
  const [error, setError] = useState('')
  const [matching, setMatching] = useState(false)

  useEffect(() => {
    let active = true
    void client.getJobRequest(jobId).then((r) => {
      if (!active) return
      if (r.status === 'ok') setJob(r.job)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') setError(t(outcome === 'not-found' ? 'errors.notFound' : outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    })
    return () => { active = false }
  }, [client, handleError, jobId, t])

  async function runMatch() {
    setError('')
    setMatching(true)
    const r = await client.runMatch(jobId)
    setMatching(false)
    if (r.status === 'ok') setResults(r.results)
    else {
      const outcome = handleError(r.status)
      if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    }
  }

  if (error) return <p className="error" role="alert">{error}</p>
  if (job === null) return <p>{t('common.loading')}</p>

  return (
    <div className="job-detail">
      <p><Link to="/job-requests">← {t('detail.back')}</Link></p>
      <h1>{job.title}</h1>
      <p>{job.sector}</p>
      <h2>{t('detail.requirements')}</h2>
      <ul>
        {job.required_skills.map((s) => <li key={s}>{s}</li>)}
        {job.required_languages.map((l) => <li key={l.language}>{l.language} — {t(`jobForm.level_${l.min_level}`)}</li>)}
      </ul>
      <button type="button" onClick={() => void runMatch()} disabled={matching}>{t('detail.runMatch')}</button>
      {matching && <p role="status">{t('detail.calculating')}</p>}
      {results !== null && <MatchResults results={results} />}
    </div>
  )
}
```

- [ ] **Step 4: Wire the nested routes in `App.tsx`**

Add imports and nested routes inside the `<Route path="/" ...>` block (after the `unauthorized` route):
```tsx
import { JobRequestList } from './screens/jobRequests/JobRequestList'
import { JobRequestCreate } from './screens/jobRequests/JobRequestCreate'
import { JobRequestDetail } from './screens/jobRequests/JobRequestDetail'
// ...inside <Route path="/" element={<ProtectedRoute><AppShell/></ProtectedRoute>}>
        <Route index element={<Home />} />
        <Route path="unauthorized" element={<Unauthorized />} />
        <Route path="job-requests" element={<JobRequestList />} />
        <Route path="job-requests/new" element={<JobRequestCreate />} />
        <Route path="job-requests/:id" element={<JobRequestDetail />} />
```

- [ ] **Step 5: Run the full suite and the gate**

Run: `npm test && npm run typecheck && npm run lint && npm run build`
Expected: all PASS / exit 0; output pristine.

- [ ] **Step 6: Commit**

```bash
git add operator-portal/src/screens/jobRequests/JobRequestDetail.tsx operator-portal/src/screens/jobRequests/JobRequestDetail.test.tsx operator-portal/src/App.tsx operator-portal/src/App.test.tsx
git commit -m "feat(operator-portal): job request detail + run matching; wire section routes"
```

---

## After all tasks

- Update `STATO_TECNICO.md`: the richieste+matching section, the `operatorClient` feature methods + `useApiError` (closes the S11 401-interceptor follow-up), the explainable match rendering, the "only compatible" choice (S6 minimization), and advance the roadmap (sub-projects 3–5: profiles, admin, metrics+export with the backend follow-on).
- Run the final whole-branch review (opus), then `superpowers:finishing-a-development-branch`.
```
