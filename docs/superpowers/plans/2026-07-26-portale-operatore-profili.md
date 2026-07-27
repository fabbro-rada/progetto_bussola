# Portale Operatore — Consultazione profili — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the operator portal's "Profili" section (sub-project 3/5): search/filter work profiles and view a full work-only profile with per-skill evidence grade, on the S11 shell, consuming the S6 profiles API.

**Architecture:** Extend `operatorClient` (S12 pattern) with `searchProfiles(filters)`/`getProfile(pseudonym)` (fail-closed, Bearer, query params). New screens under `/profiles` render in the S11 `AppShell`; errors route through the existing `useApiError`; the `profiles` nav item becomes a real link (`built` flag). The profile detail shows the §5 work-only fields; each skill's evidence grade renders as a colour-coded word badge (Certificata/Dimostrata/Dichiarata).

**Tech Stack:** React 18 + Vite + TS + react-router-dom + react-i18next, Vitest + @testing-library/react. Extends `operator-portal/`. No new dependencies.

## Global Constraints

- Local/offline, open-source permissive only; **no new dependencies**. Code English; all user strings i18n-externalized (Italian catalog, §11) — including the enum→label maps.
- Extends the S11/S12 `operator-portal/` app; the kiosk at `frontend/` is NOT touched.
- Feature calls carry `Authorization: Bearer`; **fail-closed** — every method returns a typed result, never throws: 200→ok, 401→unauthorized, 403→forbidden, 404→not-found (get only), network/5xx/parse→error.
- **401 → `onUnauthorized()` + redirect to `/login`** via the existing `useApiError` hook; 403→«non autorizzato»; error→retryable message.
- **Unfiltered search allowed** → full list (S6 audits it; §7.3). The UI does not block it.
- **Consult-only, no export** here (export with authorization is sub-project 5). No profile editing (profiles are person-confirmed in S4; §5).
- **No PII (§5):** profiles shown by opaque `pseudonym_id`; free-text is already PII-filtered upstream (S4/S6) — the UI adds none.
- **Evidence grade** rendered as a word badge + colour (not colour alone), per §5 and the approved design.
- RBAC (§6): operator-role (`READ_PROFILES`) behind `ProtectedRoute`; server remains the authority (403). TDD; only synthetic data; pristine output.

## Backend contract (exact — S6)
- `GET /profiles?availability=&language=&note=&skill_query=` → `WorkProfile[]` (any filter optional; omitted params dropped). Server audits filter names + result count.
- `GET /profiles/{pseudonym}` → `WorkProfile` | 404. Server audits `profile_viewed`.
- `WorkProfile`: `{ pseudonym_id, languages: {language, level}[], digital_literacy: DigitalLiteracy|null, skills: {name, kind, evidence}[], experiences: {role, sector, duration_months}[], aspiration: {fields_of_interest: string[], availability: Availability|null, constraints: WorkConstraint[]}|null, desired_training: {topic}[], operational_notes: OperationalNoteCategory[] }`.
- Enums: `LanguageLevel` basic|intermediate|fluent|native; `DigitalLiteracy` none|basic|intermediate|advanced; `EvidenceGrade` stated|demonstrated|certified; `SkillKind` technical|soft; `Availability` full_time|part_time|flexible; `WorkConstraint` no_night_shifts|part_time_only|needs_training_first; `OperationalNoteCategory` needs_language_support|needs_literacy_support|limited_availability|prefers_team_work|prefers_solo_work.

---

## File Structure

```
operator-portal/src/
  types.ts                                   (Task 1 — WorkProfile + nested + enums + filters + result unions)
  api/operatorClient.ts                      (Task 1 — searchProfiles/getProfile)
  test/fakeClient.ts                         (Task 1 — fake + PROFILE fixture)
  i18n/locales/it.ts                         (Task 1 — profiles group + pl enum-label maps)
  screens/profiles/ProfileSearch.tsx         (Task 2)
  screens/profiles/SkillBadge.tsx            (Task 3)
  screens/profiles/ProfileDetail.tsx         (Task 3)
  rbac/nav.ts                                (Task 2 — profiles built:true)
  App.tsx                                     (Task 4 — nested routes)
```
Each `*.ts(x)` gets a sibling `*.test.ts(x)`.

---

## Task 1: types + `operatorClient` (searchProfiles/getProfile) + fake + i18n

**Files:**
- Modify: `src/types.ts`, `src/api/operatorClient.ts`, `src/test/fakeClient.ts`, `src/i18n/locales/it.ts`
- Test: `src/api/operatorClient.test.ts` (extend)

**Interfaces:**
- Produces: `DigitalLiteracy`, `EvidenceGrade`, `SkillKind`, `WorkConstraint`, `OperationalNoteCategory` types; `LanguageKnown`, `Skill`, `WorkExperience`, `Aspiration`, `DesiredTraining`, `WorkProfile`; `ProfileFilters`; `SearchProfilesResult`, `GetProfileResult`. `OperatorClient` gains `searchProfiles(filters)`, `getProfile(pseudonym)`.

- [ ] **Step 1: Write the failing test** (extend `src/api/operatorClient.test.ts`)

```ts
const PROFILE = {
  pseudonym_id: 'P-4F2A',
  languages: [{ language: 'it', level: 'fluent' }],
  digital_literacy: 'intermediate',
  skills: [{ name: 'Cucina', kind: 'technical', evidence: 'certified' }],
  experiences: [{ role: 'Aiuto cuoco', sector: 'Ristorazione', duration_months: 24 }],
  aspiration: { fields_of_interest: ['Ristorazione'], availability: 'full_time', constraints: ['no_night_shifts'] },
  desired_training: [{ topic: 'HACCP' }],
  operational_notes: ['needs_language_support'],
}

test('searchProfiles sends only the set filters as query params, with Bearer', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, [PROFILE]))
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.searchProfiles({ availability: 'full_time', skill_query: 'cucina' })
  expect(r).toEqual({ status: 'ok', profiles: [PROFILE] })
  const url = String(f.mock.calls[0][0])
  expect(url).toContain('/profiles?')
  expect(url).toContain('availability=full_time')
  expect(url).toContain('skill_query=cucina')
  expect(url).not.toContain('language=')
  expect(url).not.toContain('note=')
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
})

test('searchProfiles with no filters hits /profiles (no query string) and maps 401/403', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.searchProfiles({})).toEqual({ status: 'ok', profiles: [] })
  expect(String(f.mock.calls[0][0])).toMatch(/\/profiles$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.searchProfiles({})).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.searchProfiles({})).toEqual({ status: 'forbidden' })
})

test('getProfile maps 200→ok and 404→not-found', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(200, PROFILE)))
  expect(await operatorClient.getProfile('P-4F2A')).toEqual({ status: 'ok', profile: PROFILE })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(404)))
  expect(await operatorClient.getProfile('P-4F2A')).toEqual({ status: 'not-found' })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- operatorClient`
Expected: FAIL (methods not defined).

- [ ] **Step 3: Extend `types.ts`**

Append (note: `LanguageLevel` and `Availability` already exist from S12 — do NOT redeclare them):
```ts
export type DigitalLiteracy = 'none' | 'basic' | 'intermediate' | 'advanced'
export type EvidenceGrade = 'stated' | 'demonstrated' | 'certified'
export type SkillKind = 'technical' | 'soft'
export type WorkConstraint = 'no_night_shifts' | 'part_time_only' | 'needs_training_first'
export type OperationalNoteCategory =
  | 'needs_language_support'
  | 'needs_literacy_support'
  | 'limited_availability'
  | 'prefers_team_work'
  | 'prefers_solo_work'

export interface LanguageKnown {
  language: string
  level: LanguageLevel
}
export interface Skill {
  name: string
  kind: SkillKind
  evidence: EvidenceGrade
}
export interface WorkExperience {
  role: string
  sector: string
  duration_months: number
}
export interface Aspiration {
  fields_of_interest: string[]
  availability: Availability | null
  constraints: WorkConstraint[]
}
export interface DesiredTraining {
  topic: string
}
export interface WorkProfile {
  pseudonym_id: string
  languages: LanguageKnown[]
  digital_literacy: DigitalLiteracy | null
  skills: Skill[]
  experiences: WorkExperience[]
  aspiration: Aspiration | null
  desired_training: DesiredTraining[]
  operational_notes: OperationalNoteCategory[]
}

export interface ProfileFilters {
  availability?: Availability
  language?: string
  note?: OperationalNoteCategory
  skill_query?: string
}

export type SearchProfilesResult =
  | { status: 'ok'; profiles: WorkProfile[] }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type GetProfileResult =
  | { status: 'ok'; profile: WorkProfile }
  | { status: 'not-found' }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
```
Add to the `OperatorClient` interface:
```ts
  searchProfiles(filters: ProfileFilters): Promise<SearchProfilesResult>
  getProfile(pseudonym: string): Promise<GetProfileResult>
```

- [ ] **Step 4: Extend `operatorClient.ts`** (add the 2 methods before `export const operatorClient`)

```ts
async function searchProfiles(filters: ProfileFilters): Promise<SearchProfilesResult> {
  const qs = new URLSearchParams()
  if (filters.availability) qs.set('availability', filters.availability)
  if (filters.language) qs.set('language', filters.language)
  if (filters.note) qs.set('note', filters.note)
  if (filters.skill_query) qs.set('skill_query', filters.skill_query)
  const q = qs.toString()
  let res: Response
  try {
    res = await fetch(`${BASE}/profiles${q ? `?${q}` : ''}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', profiles: (await res.json()) as WorkProfile[] }
  } catch {
    return { status: 'error' }
  }
}

async function getProfile(pseudonym: string): Promise<GetProfileResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/profiles/${encodeURIComponent(pseudonym)}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 404) return { status: 'not-found' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', profile: (await res.json()) as WorkProfile }
  } catch {
    return { status: 'error' }
  }
}
```
Update the type import (`ProfileFilters, SearchProfilesResult, GetProfileResult, WorkProfile`) and add both to the exported object.

- [ ] **Step 5: Extend `test/fakeClient.ts`**

Add a `PROFILE` fixture (export) and extend `makeFakeClient` opts + return with `searchProfiles`/`getProfile` + call counters:
```ts
export const PROFILE: WorkProfile = {
  pseudonym_id: 'P-4F2A',
  languages: [{ language: 'it', level: 'fluent' }, { language: 'ar', level: 'native' }],
  digital_literacy: 'intermediate',
  skills: [
    { name: 'Cucina', kind: 'technical', evidence: 'certified' },
    { name: 'Puntualità', kind: 'soft', evidence: 'stated' },
  ],
  experiences: [{ role: 'Aiuto cuoco', sector: 'Ristorazione', duration_months: 24 }],
  aspiration: { fields_of_interest: ['Ristorazione'], availability: 'full_time', constraints: ['no_night_shifts'] },
  desired_training: [{ topic: 'HACCP' }],
  operational_notes: ['needs_language_support'],
}
```
In `makeFakeClient` add opts `profiles?: SearchProfilesResult`, `profile?: GetProfileResult`; add counters `psearch`/`pget` to the `calls` object (distinct names — the S12 `get` counter is the job-request one, do not reuse it); add a `searched: ProfileFilters[]` array to the returned object (alongside the existing `created`); and the two methods:
```ts
    async searchProfiles(filters) { calls.psearch++; searched.push(filters); return opts.profiles ?? { status: 'ok', profiles: [PROFILE] } },
    async getProfile() { calls.pget++; return opts.profile ?? { status: 'ok', profile: PROFILE } },
```
(Import the added types. Update the returned object's type annotation to include the `psearch`/`pget` counters and `searched: ProfileFilters[]`.)

- [ ] **Step 6: Add i18n** to `src/i18n/locales/it.ts` — a `profiles` group + a `pl` (profile-labels) group:
```ts
  profiles: {
    title: 'Profili',
    search: 'Cerca',
    filterAvailability: 'Disponibilità',
    filterLanguage: 'Lingua',
    filterNote: 'Nota operativa',
    filterSkill: 'Competenza',
    any: 'Qualsiasi',
    empty: 'Nessun profilo trovato.',
    colPseudonym: 'Pseudonimo',
    colLanguages: 'Lingue',
    colAvailability: 'Disponibilità',
    colSkills: 'Competenze',
    skillsCount: '{{n}} competenze',
    notFound: 'Profilo non trovato.',
    digitalLiteracy: 'Alfabetizzazione digitale',
    skills: 'Competenze',
    languages: 'Lingue',
    experiences: 'Esperienze',
    aspiration: 'Aspirazioni',
    interests: 'Interessi',
    constraints: 'Vincoli',
    training: 'Formazione desiderata',
    notes: 'Note operative',
    months: '{{n}} mesi',
    none: '—',
  },
  pl: {
    level_basic: 'Base', level_intermediate: 'Intermedio', level_fluent: 'Fluente', level_native: 'Madrelingua',
    digital_none: 'Nessuna', digital_basic: 'Base', digital_intermediate: 'Intermedia', digital_advanced: 'Avanzata',
    evidence_stated: 'Dichiarata', evidence_demonstrated: 'Dimostrata', evidence_certified: 'Certificata',
    kind_technical: 'Tecnica', kind_soft: 'Trasversale',
    availability_full_time: 'Tempo pieno', availability_part_time: 'Part-time', availability_flexible: 'Flessibile',
    constraint_no_night_shifts: 'Niente turni notturni', constraint_part_time_only: 'Solo part-time', constraint_needs_training_first: 'Serve formazione prima',
    note_needs_language_support: 'Supporto linguistico', note_needs_literacy_support: 'Supporto alfabetizzazione', note_limited_availability: 'Disponibilità limitata', note_prefers_team_work: 'Preferisce team', note_prefers_solo_work: 'Preferisce lavoro individuale',
  },
```

- [ ] **Step 7: Run the tests and the gate**

Run: `npm test -- operatorClient && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/types.ts operator-portal/src/api operator-portal/src/test/fakeClient.ts operator-portal/src/i18n/locales/it.ts
git commit -m "feat(operator-portal): profiles client (search/get) + WorkProfile types + i18n labels"
```

---

## Task 2: `ProfileSearch` (filters + results) + Nav real link

**Files:**
- Create: `src/screens/profiles/ProfileSearch.tsx`
- Modify: `src/rbac/nav.ts` (profiles `built: true`)
- Test: `src/screens/profiles/ProfileSearch.test.tsx`

**Interfaces:**
- `ProfileSearch()` — filter panel (availability select, language text, note select, skill_query text) + «Cerca»; loads via `useAuth().client.searchProfiles(filters)` on mount (empty filters → full list) and on «Cerca» (with the set filters); results as rows (pseudonym Link to `/profiles/:pseudonym`, languages, availability, skills count); empty state; non-ok via `useApiError`.
- `rbac/nav.ts`: the operator `profiles` item gains `built: true`.

- [ ] **Step 1: Write the failing test**

`src/screens/profiles/ProfileSearch.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, PROFILE } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ProfileSearch } from './ProfileSearch'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/profiles" element={<ProfileSearch />} />
      <Route path="/profiles/:pseudonym" element={<div>DETAIL</div>} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

test('loads all profiles on mount and links each row to its detail', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profiles: { status: 'ok', profiles: [PROFILE] } })
  renderWithProviders(harness(), { client, route: '/profiles' })
  expect(await screen.findByRole('link', { name: 'P-4F2A' })).toHaveAttribute('href', '/profiles/P-4F2A')
  expect(client.searched[0]).toEqual({}) // mount search: no filters
})

test('«Cerca» sends the set filters', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profiles: { status: 'ok', profiles: [PROFILE] } })
  renderWithProviders(harness(), { client, route: '/profiles' })
  await screen.findByRole('link', { name: 'P-4F2A' })
  await userEvent.type(screen.getByLabelText('Competenza'), 'cucina')
  await userEvent.click(screen.getByRole('button', { name: 'Cerca' }))
  await waitFor(() => expect(client.searched.at(-1)).toEqual({ skill_query: 'cucina' }))
})

test('empty state when no profiles match', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profiles: { status: 'ok', profiles: [] } })
  renderWithProviders(harness(), { client, route: '/profiles' })
  expect(await screen.findByText('Nessun profilo trovato.')).toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profiles: { status: 'unauthorized' } })
  renderWithProviders(harness(), { client, route: '/profiles' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- ProfileSearch`
Expected: FAIL (module not found).

- [ ] **Step 3: Update `rbac/nav.ts`** — mark the operator `profiles` item built:
```ts
    { path: '/profiles', labelKey: 'nav.profiles', built: true },
```

- [ ] **Step 4: Implement `ProfileSearch.tsx`**

```tsx
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { Availability, OperationalNoteCategory, ProfileFilters, WorkProfile } from '../../types'

const AVAILABILITIES: Availability[] = ['full_time', 'part_time', 'flexible']
const NOTES: OperationalNoteCategory[] = [
  'needs_language_support', 'needs_literacy_support', 'limited_availability', 'prefers_team_work', 'prefers_solo_work',
]

export function ProfileSearch() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [availability, setAvailability] = useState<Availability | ''>('')
  const [language, setLanguage] = useState('')
  const [note, setNote] = useState<OperationalNoteCategory | ''>('')
  const [skillQuery, setSkillQuery] = useState('')
  const [profiles, setProfiles] = useState<WorkProfile[] | null>(null)
  const [error, setError] = useState('')

  const runSearch = useCallback(
    async (filters: ProfileFilters) => {
      setError('')
      const r = await client.searchProfiles(filters)
      if (r.status === 'ok') setProfiles(r.profiles)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    },
    [client, handleError, t],
  )

  useEffect(() => {
    void runSearch({}) // full list on mount (allowed + audited, §7.3)
  }, [runSearch])

  function submit(e: FormEvent) {
    e.preventDefault()
    const filters: ProfileFilters = {}
    if (availability) filters.availability = availability
    if (language.trim()) filters.language = language.trim()
    if (note) filters.note = note
    if (skillQuery.trim()) filters.skill_query = skillQuery.trim()
    void runSearch(filters)
  }

  return (
    <div className="profile-search">
      <h1>{t('profiles.title')}</h1>
      <form className="filters" onSubmit={submit}>
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
        <button type="submit">{t('profiles.search')}</button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      {profiles === null ? (
        <p>{t('common.loading')}</p>
      ) : profiles.length === 0 ? (
        <p>{t('profiles.empty')}</p>
      ) : (
        <table>
          <thead>
            <tr><th>{t('profiles.colPseudonym')}</th><th>{t('profiles.colLanguages')}</th><th>{t('profiles.colAvailability')}</th><th>{t('profiles.colSkills')}</th></tr>
          </thead>
          <tbody>
            {profiles.map((p) => (
              <tr key={p.pseudonym_id}>
                <td><Link to={`/profiles/${p.pseudonym_id}`}>{p.pseudonym_id}</Link></td>
                <td>{p.languages.map((l) => l.language).join(', ') || t('profiles.none')}</td>
                <td>{p.aspiration?.availability ? t(`pl.availability_${p.aspiration.availability}`) : t('profiles.none')}</td>
                <td>{t('profiles.skillsCount', { n: p.skills.length })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS (existing Nav tests still green — the `profiles` item is now a link, its text unchanged).

- [ ] **Step 6: Commit**

```bash
git add operator-portal/src/screens/profiles/ProfileSearch.tsx operator-portal/src/screens/profiles/ProfileSearch.test.tsx operator-portal/src/rbac/nav.ts
git commit -m "feat(operator-portal): profile search (filters + results) + real nav link"
```

---

## Task 3: `SkillBadge` + `ProfileDetail`

**Files:**
- Create: `src/screens/profiles/SkillBadge.tsx`, `src/screens/profiles/ProfileDetail.tsx`
- Modify: `src/styles/theme.css` (append evidence-badge + detail styles)
- Test: `src/screens/profiles/SkillBadge.test.tsx`, `src/screens/profiles/ProfileDetail.test.tsx`

**Interfaces:**
- `SkillBadge({ grade: EvidenceGrade })` — a colour-coded word badge: `t('pl.evidence_<grade>')` with class `ev-<grade>` (certified green, demonstrated blue, stated grey) + an icon (✓/◆/○).
- `ProfileDetail()` — reads `:pseudonym`, loads `client.getProfile(pseudonym)` on mount; renders the full work-only profile (digital literacy, skills with kind + `<SkillBadge>`, languages+level, experiences, aspiration incl. interests/availability/constraints, desired training, operational notes) via the `pl.*` labels; 404 → `profiles.notFound`; non-ok via `useApiError`.

- [ ] **Step 1: Write the failing tests**

`src/screens/profiles/SkillBadge.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { SkillBadge } from './SkillBadge'

test('renders the evidence grade word for each level', () => {
  renderWithProviders(
    <>
      <SkillBadge grade="certified" />
      <SkillBadge grade="demonstrated" />
      <SkillBadge grade="stated" />
    </>,
  )
  expect(screen.getByText(/Certificata/)).toBeInTheDocument()
  expect(screen.getByText(/Dimostrata/)).toBeInTheDocument()
  expect(screen.getByText(/Dichiarata/)).toBeInTheDocument()
})
```
`src/screens/profiles/ProfileDetail.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, PROFILE } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ProfileDetail } from './ProfileDetail'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/profiles/:pseudonym" element={<ProfileDetail />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

test('renders the work-only profile with per-skill evidence grade', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profile: { status: 'ok', profile: PROFILE } })
  renderWithProviders(harness(), { client, route: '/profiles/P-4F2A' })
  expect(await screen.findByText('P-4F2A')).toBeInTheDocument()
  expect(screen.getByText('Cucina')).toBeInTheDocument()
  expect(screen.getByText(/Certificata/)).toBeInTheDocument() // skill evidence grade
  expect(screen.getByText(/Dichiarata/)).toBeInTheDocument()
  expect(screen.getByText('Aiuto cuoco')).toBeInTheDocument() // experience
  expect(screen.getByText(/Niente turni notturni/)).toBeInTheDocument() // constraint label
  expect(screen.getByText(/Supporto linguistico/)).toBeInTheDocument() // operational note label
})

test('404 shows the not-found message', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profile: { status: 'not-found' } })
  renderWithProviders(harness(), { client, route: '/profiles/P-XXXX' })
  expect(await screen.findByText('Profilo non trovato.')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- SkillBadge ProfileDetail`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement `SkillBadge.tsx`**

```tsx
import { useTranslation } from 'react-i18next'
import type { EvidenceGrade } from '../../types'

const ICON: Record<EvidenceGrade, string> = { certified: '✓', demonstrated: '◆', stated: '○' }

export function SkillBadge({ grade }: { grade: EvidenceGrade }) {
  const { t } = useTranslation()
  return (
    <span className={`ev-badge ev-${grade}`}>
      {ICON[grade]} {t(`pl.evidence_${grade}`)}
    </span>
  )
}
```

- [ ] **Step 4: Implement `ProfileDetail.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { WorkProfile } from '../../types'
import { SkillBadge } from './SkillBadge'

export function ProfileDetail() {
  const { t } = useTranslation()
  const { pseudonym } = useParams()
  const { client } = useAuth()
  const handleError = useApiError()
  const [profile, setProfile] = useState<WorkProfile | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void client.getProfile(pseudonym ?? '').then((r) => {
      if (!active) return
      if (r.status === 'ok') setProfile(r.profile)
      else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled')
          setError(t(outcome === 'not-found' ? 'profiles.notFound' : outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
      }
    })
    return () => { active = false }
  }, [client, handleError, pseudonym, t])

  if (error) return <p className="error" role="alert">{error}</p>
  if (profile === null) return <p>{t('common.loading')}</p>

  return (
    <div className="profile-detail">
      <p><Link to="/profiles">← {t('profiles.title')}</Link></p>
      <div className="pd-head">
        <h1>{profile.pseudonym_id}</h1>
        <span>{t('profiles.digitalLiteracy')}: {profile.digital_literacy ? t(`pl.digital_${profile.digital_literacy}`) : t('profiles.none')}</span>
      </div>

      <h2>{t('profiles.skills')}</h2>
      <ul className="skills">
        {profile.skills.map((s, i) => (
          <li key={i}>
            <span className="skill-name">{s.name}</span> <span className="muted">· {t(`pl.kind_${s.kind}`)}</span> <SkillBadge grade={s.evidence} />
          </li>
        ))}
      </ul>

      <h2>{t('profiles.languages')}</h2>
      <ul>{profile.languages.map((l, i) => <li key={i}>{l.language} — {t(`pl.level_${l.level}`)}</li>)}</ul>

      <h2>{t('profiles.experiences')}</h2>
      <ul>{profile.experiences.map((e, i) => <li key={i}>{e.role} — {e.sector} — {t('profiles.months', { n: e.duration_months })}</li>)}</ul>

      {profile.aspiration && (
        <>
          <h2>{t('profiles.aspiration')}</h2>
          <p>{t('profiles.interests')}: {profile.aspiration.fields_of_interest.join(', ') || t('profiles.none')}</p>
          <p>{t('profiles.colAvailability')}: {profile.aspiration.availability ? t(`pl.availability_${profile.aspiration.availability}`) : t('profiles.none')}</p>
          <p>{t('profiles.constraints')}: {profile.aspiration.constraints.map((c) => t(`pl.constraint_${c}`)).join(', ') || t('profiles.none')}</p>
        </>
      )}

      {profile.desired_training.length > 0 && (
        <>
          <h2>{t('profiles.training')}</h2>
          <ul>{profile.desired_training.map((d, i) => <li key={i}>{d.topic}</li>)}</ul>
        </>
      )}

      {profile.operational_notes.length > 0 && (
        <>
          <h2>{t('profiles.notes')}</h2>
          <ul>{profile.operational_notes.map((n, i) => <li key={i}>{t(`pl.note_${n}`)}</li>)}</ul>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Append styles to `theme.css`**

```css
.filters { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; margin-bottom: 16px; }
.filters label { display: flex; flex-direction: column; gap: 4px; font-weight: 600; }
.filters input, .filters select { padding: 8px; border: 1px solid var(--border); border-radius: 8px; font: inherit; }
.filters button { padding: 9px 16px; border: 0; border-radius: 8px; background: var(--accent); color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
.skills { list-style: none; padding: 0; } .skills li { margin: 4px 0; }
.muted { color: var(--muted); }
.ev-badge { border-radius: 10px; padding: 2px 10px; font-size: 12px; font-weight: 700; margin-left: 6px; }
.ev-certified { background: #dcfce7; color: #15803d; }
.ev-demonstrated { background: #dbeafe; color: #1d4ed8; }
.ev-stated { background: #f3f4f6; color: #6b7280; }
.pd-head { display: flex; align-items: baseline; justify-content: space-between; }
```

- [ ] **Step 6: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add operator-portal/src/screens/profiles/SkillBadge.tsx operator-portal/src/screens/profiles/SkillBadge.test.tsx operator-portal/src/screens/profiles/ProfileDetail.tsx operator-portal/src/screens/profiles/ProfileDetail.test.tsx operator-portal/src/styles/theme.css
git commit -m "feat(operator-portal): profile detail (work-only) + evidence-grade badge"
```

---

## Task 4: App routes + section integration

**Files:**
- Modify: `src/App.tsx` (nested routes)
- Test: `src/App.test.tsx` (add a section reachability test)

**Interfaces:**
- `App.tsx` gains, under the `/` ProtectedRoute/AppShell block: `<Route path="profiles" element={<ProfileSearch />} />` and `<Route path="profiles/:pseudonym" element={<ProfileDetail />} />`.

- [ ] **Step 1: Write the failing test** (add to `src/App.test.tsx`)

```ts
test('an authenticated operator can reach the profiles section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } })
  renderApp(client, '/profiles')
  // «Cerca» is rendered only by ProfileSearch → proves the route mounted (not just the Nav link)
  expect(await screen.findByRole('button', { name: 'Cerca' })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- App`
Expected: FAIL (route not wired → falls through to Home; no «Cerca» button).

- [ ] **Step 3: Wire the nested routes in `App.tsx`**

Add the imports and the two routes inside the `<Route path="/" ...>` block (after the job-requests routes):
```tsx
import { ProfileSearch } from './screens/profiles/ProfileSearch'
import { ProfileDetail } from './screens/profiles/ProfileDetail'
// ...inside the "/" block:
        <Route path="profiles" element={<ProfileSearch />} />
        <Route path="profiles/:pseudonym" element={<ProfileDetail />} />
```

- [ ] **Step 4: Run the full suite and the gate**

Run: `npm test && npm run typecheck && npm run lint && npm run build`
Expected: all PASS / exit 0; output pristine.

- [ ] **Step 5: Commit**

```bash
git add operator-portal/src/App.tsx operator-portal/src/App.test.tsx
git commit -m "feat(operator-portal): wire profiles section routes"
```

---

## After all tasks

- Update `STATO_TECNICO.md`: the profiles section, the `operatorClient` search/get methods, the evidence-grade badge rendering, the "unfiltered search allowed + audited" choice, and advance the roadmap (sub-projects 4–5: admin, metrics+export with backend follow-on).
- Run the final whole-branch review (opus), then `superpowers:finishing-a-development-branch`.
```
