# UI Kiosk della Persona (text-first) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the person-facing kiosk SPA (React) that drives the interview in **text**, consuming the S8 kiosk API: language choice → informed consent → turn-by-turn interview → completion.

**Architecture:** A screen state machine (pure reducer, no URL routing) drives which screen is shown; inside the interview, the screen derives from the API `step.kind`. An isolated `kioskClient` wraps the S8 HTTP calls, injects `X-Kiosk-Token`, and maps HTTP outcomes to a typed result so the UI never blocks. i18n (react-i18next) + `dir=rtl` for Arabic; accessibility via a text-size context on CSS variables. Voice is a disabled placeholder (next subsystem).

**Tech Stack:** React 18 + Vite 5 + TypeScript 5, react-i18next, Vitest + @testing-library/react + jsdom. New directory `frontend/`.

## Global Constraints

- **Local/offline, open source with permissive licenses only** (MIT/Apache/BSD); budget zero; no external runtime dependency (`CLAUDE.md` §3).
- **Text-first; voice is OUT of this subsystem** — voice controls render only as a disabled placeholder; do NOT call `/kiosk/voice/*` (§3, spec §2).
- **Code and identifiers in English; ALL user-facing strings externalized via i18n** — no hard-coded UI copy in components (`CLAUDE.md` §11). Exception: the language picker's bilingual title and the language endonyms (e.g. `Italiano`, `العربية`) are constants.
- **Five languages: it, en, fr, es, ar. Arabic sets `dir=rtl` on the document root** (`CLAUDE.md` §8).
- **Interview content is already localized by the backend** (the language is passed to `start`); the UI localizes only its own chrome.
- **TDD**: write the failing test first; **only synthetic data** in tests (`CLAUDE.md` §9).
- **Kiosk device token via build-time env** `VITE_KIOSK_TOKEN`; never commit a real token — only `frontend/.env.example`. The person has no login/identity (spec §3.8).
- **Degradation never blocks**: `step.kind==="unavailable"` (HTTP 200), `404` (session expired), `401` (bad token), and network/5xx errors all render a gentle screen; text always works (§3, spec §3.4).
- **The «Ferma» (stop) control is mounted throughout the session** and resets to the language picker (`CLAUDE.md` §4/§7.1).
- Scope stays inside work/training: the `refusal` screen shows the gentle refusal and keeps the person in the interview (`CLAUDE.md` §2).

---

## File Structure

```
frontend/
  package.json               (Task 1)
  tsconfig.json / tsconfig.app.json / tsconfig.node.json   (Task 1)
  vite.config.ts             (Task 1 — vitest config + dev proxy to backend)
  eslint.config.js           (Task 1)
  index.html                 (Task 1)
  .env.example               (Task 1)
  src/
    main.tsx                 (Task 1 — entry)
    App.tsx                  (Task 1 placeholder → Task 10 full composition)
    vite-env.d.ts            (Task 1 — ImportMetaEnv types)
    types.ts                 (Task 2 — Step, StepKind, results, Screen)
    api/kioskClient.ts       (Task 2)
    state/kioskMachine.ts    (Task 3 — pure reducer)
    i18n/index.ts            (Task 4 — i18next init + applyLanguage)
    i18n/languages.ts        (Task 4 — language metadata + dirFor)
    i18n/locales/{it,en,fr,es,ar}.ts   (Task 4)
    a11y/TextSize.tsx        (Task 5 — context/provider on CSS vars)
    components/{BigButton,AnswerPrompt,ConfirmCorrect,Notice,StopButton,TextSizeControl,VoicePlaceholder}.tsx   (Task 6)
    screens/{LanguagePicker,Consent}.tsx        (Task 7)
    screens/{Question,Summary,Clarification}.tsx (Task 8)
    screens/{Refusal,Unavailable,Completed,Unauthorized}.tsx (Task 9)
    styles/theme.css         (Task 1 baseline → Task 5/6 extended)
    test/setup.ts            (Task 1)
    test/utils.tsx           (Task 6 — renderWithProviders)
    test/fakeClient.ts       (Task 10 — deterministic fake KioskClient)
```

Each `*.tsx`/`*.ts` implementation file gets a sibling `*.test.ts(x)` in the same folder.

---

## Task 1: Scaffold `frontend/` with test / typecheck / lint gate

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/eslint.config.js`, `frontend/index.html`, `frontend/.env.example`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/vite-env.d.ts`, `frontend/src/styles/theme.css`, `frontend/src/test/setup.ts`
- Create test: `frontend/src/App.test.tsx`
- Modify: `.gitignore` (repo root — add `frontend/node_modules/`, `frontend/dist/`, `frontend/.env`)

**Interfaces:**
- Produces: a working Vite+React+TS app with `npm test`, `npm run typecheck`, `npm run lint`, `npm run build` all green; an `App` component (placeholder) exported from `src/App.tsx`.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "bussola-kiosk",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc -b",
    "lint": "eslint ."
  },
  "dependencies": {
    "i18next": "^23.15.1",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-i18next": "^15.0.2"
  },
  "devDependencies": {
    "@eslint/js": "^9.10.0",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/node": "^22.5.5",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "eslint": "^9.10.0",
    "eslint-plugin-react-hooks": "^5.1.0-rc.0",
    "jsdom": "^25.0.0",
    "typescript": "^5.5.4",
    "typescript-eslint": "^8.5.0",
    "vite": "^5.4.5",
    "vitest": "^2.1.1"
  }
}
```

- [ ] **Step 2: Create the TypeScript configs**

`frontend/tsconfig.json`:
```json
{
  "files": [],
  "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }]
}
```

`frontend/tsconfig.app.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom", "vite/client"]
  },
  "include": ["src"]
}
```

`frontend/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "types": ["node"]
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Dev proxy: the SPA runs on the Vite dev server; the S8 API is served by the
// backend on 127.0.0.1:8000 (single-box, localhost — STATO_TECNICO §6).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/kiosk': 'http://127.0.0.1:8000' } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
```

- [ ] **Step 4: Create `frontend/eslint.config.js`**

```js
import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    plugins: { 'react-hooks': reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
)
```

- [ ] **Step 5: Create `frontend/index.html`, `src/main.tsx`, `src/vite-env.d.ts`, `src/App.tsx` (placeholder), `src/styles/theme.css`, `src/test/setup.ts`**

`frontend/index.html`:
```html
<!doctype html>
<html lang="it">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Bussola</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_KIOSK_TOKEN: string
  readonly VITE_API_BASE: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

`frontend/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import './styles/theme.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

`frontend/src/App.tsx` (placeholder — replaced in Task 10):
```tsx
export function App() {
  return <div className="app">Bussola</div>
}
```

`frontend/src/styles/theme.css` (baseline; extended in Tasks 5/6):
```css
:root {
  --text-scale: 1;
  --fg: #111111;
  --bg: #ffffff;
  --muted: #6b7280;
  --accent: #2563eb;
  --confirm: #15803d;
  --danger: #b91c1c;
  --warn-bg: #fffbeb;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, sans-serif;
  color: var(--fg);
  background: var(--bg);
  font-size: calc(18px * var(--text-scale));
  line-height: 1.5;
}
```

`frontend/src/test/setup.ts`:
```ts
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => cleanup())
```

- [ ] **Step 6: Write the failing smoke test**

`frontend/src/App.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { App } from './App'

test('renders the app shell', () => {
  render(<App />)
  expect(screen.getByText('Bussola')).toBeInTheDocument()
})
```

- [ ] **Step 7: Install dependencies and run the gate to verify it fails then passes**

Run (from `frontend/`):
```bash
npm install
npm test
```
Expected: `npm install` succeeds; `npm test` PASSES (1 test). Then:
```bash
npm run typecheck && npm run lint && npm run build
```
Expected: all exit 0.

- [ ] **Step 8: Update root `.gitignore` and commit**

Append to repo-root `.gitignore`:
```
frontend/node_modules/
frontend/dist/
frontend/.env
```

Create `frontend/.env.example`:
```
# Device token shared with the kiosk API (S8). Set the real value only on the
# locked kiosk box; never commit it. Rotation = rebuild.
VITE_KIOSK_TOKEN=changeme-kiosk-token
# Leave empty to use the Vite dev proxy / same origin.
VITE_API_BASE=
```

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig*.json frontend/vite.config.ts frontend/eslint.config.js frontend/index.html frontend/.env.example frontend/src .gitignore
git commit -m "feat(kiosk-ui): scaffold Vite+React+TS with vitest/typecheck/lint gate"
```

---

## Task 2: Types + `kioskClient` (S8 HTTP, typed results)

**Files:**
- Create: `frontend/src/types.ts`, `frontend/src/api/kioskClient.ts`
- Test: `frontend/src/api/kioskClient.test.ts`

**Interfaces:**
- Produces:
  - `type StepKind = 'question' | 'summary' | 'clarification' | 'refusal' | 'unavailable' | 'completed'`
  - `interface Step { kind: StepKind; text: string }`
  - `type StartResult = { status: 'ok'; sessionToken: string; step: Step } | { status: 'unauthorized' } | { status: 'unavailable' }`
  - `type SubmitResult = { status: 'ok'; step: Step } | { status: 'session-expired' } | { status: 'unauthorized' } | { status: 'unavailable' }`
  - `type Screen = 'language' | 'consent' | StepKind | 'unauthorized'`
  - `interface KioskClient { startInterview(language: string): Promise<StartResult>; submitAnswer(sessionToken: string, answer: string): Promise<SubmitResult> }`
  - `const kioskClient: KioskClient`

- [ ] **Step 1: Write the failing test**

`frontend/src/api/kioskClient.test.ts`:
```ts
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { kioskClient } from './kioskClient'

function mockFetch(status: number, body?: unknown) {
  return vi.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response)
}

beforeEach(() => vi.stubGlobal('fetch', mockFetch(200, { session_token: 't', step: { kind: 'question', text: 'Q' } })))
afterEach(() => vi.unstubAllGlobals())

test('start maps 200 to ok and sends the kiosk token header', async () => {
  const fetchMock = mockFetch(200, { session_token: 'tok', step: { kind: 'question', text: 'Ciao' } })
  vi.stubGlobal('fetch', fetchMock)
  const res = await kioskClient.startInterview('it')
  expect(res).toEqual({ status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Ciao' } })
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/kiosk/interview/start')
  expect((init as RequestInit).method).toBe('POST')
  expect((init!.headers as Record<string, string>)['X-Kiosk-Token']).toBeDefined()
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ language: 'it' })
})

test('start maps 401 to unauthorized', async () => {
  vi.stubGlobal('fetch', mockFetch(401))
  expect(await kioskClient.startInterview('it')).toEqual({ status: 'unauthorized' })
})

test('start maps a thrown fetch (backend down) to unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
  expect(await kioskClient.startInterview('it')).toEqual({ status: 'unavailable' })
})

test('submit maps 200 to ok with the step', async () => {
  vi.stubGlobal('fetch', mockFetch(200, { step: { kind: 'summary', text: 'Riepilogo' } }))
  expect(await kioskClient.submitAnswer('tok', 'ciao')).toEqual({ status: 'ok', step: { kind: 'summary', text: 'Riepilogo' } })
})

test('submit maps 404 to session-expired and 401 to unauthorized', async () => {
  vi.stubGlobal('fetch', mockFetch(404))
  expect(await kioskClient.submitAnswer('tok', 'x')).toEqual({ status: 'session-expired' })
  vi.stubGlobal('fetch', mockFetch(401))
  expect(await kioskClient.submitAnswer('tok', 'x')).toEqual({ status: 'unauthorized' })
})

test('submit maps 5xx to unavailable', async () => {
  vi.stubGlobal('fetch', mockFetch(503))
  expect(await kioskClient.submitAnswer('tok', 'x')).toEqual({ status: 'unavailable' })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- kioskClient`
Expected: FAIL (module `./kioskClient` not found).

- [ ] **Step 3: Implement `types.ts` and `kioskClient.ts`**

`frontend/src/types.ts`:
```ts
export type StepKind =
  | 'question'
  | 'summary'
  | 'clarification'
  | 'refusal'
  | 'unavailable'
  | 'completed'

export interface Step {
  kind: StepKind
  text: string
}

export type StartResult =
  | { status: 'ok'; sessionToken: string; step: Step }
  | { status: 'unauthorized' }
  | { status: 'unavailable' }

export type SubmitResult =
  | { status: 'ok'; step: Step }
  | { status: 'session-expired' }
  | { status: 'unauthorized' }
  | { status: 'unavailable' }

export type Screen = 'language' | 'consent' | StepKind | 'unauthorized'

export interface KioskClient {
  startInterview(language: string): Promise<StartResult>
  submitAnswer(sessionToken: string, answer: string): Promise<SubmitResult>
}
```

`frontend/src/api/kioskClient.ts`:
```ts
import type { KioskClient, StartResult, Step, SubmitResult } from '../types'

const BASE = import.meta.env.VITE_API_BASE ?? ''
const TOKEN = import.meta.env.VITE_KIOSK_TOKEN ?? ''

function headers(): Record<string, string> {
  return { 'Content-Type': 'application/json', 'X-Kiosk-Token': TOKEN }
}

async function startInterview(language: string): Promise<StartResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/kiosk/interview/start`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ language }),
    })
  } catch {
    return { status: 'unavailable' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (!res.ok) return { status: 'unavailable' }
  const data = (await res.json()) as { session_token: string; step: Step }
  return { status: 'ok', sessionToken: data.session_token, step: data.step }
}

async function submitAnswer(sessionToken: string, answer: string): Promise<SubmitResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/kiosk/interview/submit`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ session_token: sessionToken, answer }),
    })
  } catch {
    return { status: 'unavailable' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 404) return { status: 'session-expired' }
  if (!res.ok) return { status: 'unavailable' }
  const data = (await res.json()) as { step: Step }
  return { status: 'ok', step: data.step }
}

export const kioskClient: KioskClient = { startInterview, submitAnswer }
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- kioskClient && npm run typecheck && npm run lint`
Expected: PASS; exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/api
git commit -m "feat(kiosk-ui): typed S8 client with fail-closed degradation mapping"
```

---

## Task 3: `kioskMachine` — pure screen reducer

**Files:**
- Create: `frontend/src/state/kioskMachine.ts`
- Test: `frontend/src/state/kioskMachine.test.ts`

**Interfaces:**
- Consumes: `Screen`, `Step`, `StartResult`, `SubmitResult`, `StepKind` from `../types`.
- Produces:
  - `interface MachineState { screen: Screen; language: string | null; sessionToken: string | null; step: Step | null; lastAnswer: string | null }`
  - `const initialState: MachineState`
  - `type Action = { type: 'selectLanguage'; language: string } | { type: 'declineConsent' } | { type: 'started'; result: StartResult } | { type: 'submitting'; answer: string } | { type: 'submitted'; result: SubmitResult } | { type: 'stop' }`
  - `function reducer(state: MachineState, action: Action): MachineState`

- [ ] **Step 1: Write the failing test**

`frontend/src/state/kioskMachine.test.ts`:
```ts
import { expect, test } from 'vitest'
import { initialState, reducer } from './kioskMachine'

test('selectLanguage moves to consent and records the language', () => {
  const s = reducer(initialState, { type: 'selectLanguage', language: 'ar' })
  expect(s.screen).toBe('consent')
  expect(s.language).toBe('ar')
})

test('declineConsent resets to the initial state', () => {
  const s = reducer({ ...initialState, screen: 'consent', language: 'it' }, { type: 'declineConsent' })
  expect(s).toEqual(initialState)
})

test('started ok derives the screen from the step kind and stores the session token', () => {
  const s = reducer({ ...initialState, language: 'it' }, {
    type: 'started',
    result: { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } },
  })
  expect(s).toMatchObject({ screen: 'question', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } })
})

test('started unauthorized/unavailable route to their screens', () => {
  expect(reducer(initialState, { type: 'started', result: { status: 'unauthorized' } }).screen).toBe('unauthorized')
  expect(reducer(initialState, { type: 'started', result: { status: 'unavailable' } }).screen).toBe('unavailable')
})

test('submitting records lastAnswer for retry', () => {
  const s = reducer({ ...initialState, sessionToken: 'tok' }, { type: 'submitting', answer: 'so cucinare' })
  expect(s.lastAnswer).toBe('so cucinare')
})

test('submitted ok maps each step kind to its screen', () => {
  const base = { ...initialState, sessionToken: 'tok' }
  for (const kind of ['question', 'summary', 'clarification', 'refusal', 'unavailable', 'completed'] as const) {
    const s = reducer(base, { type: 'submitted', result: { status: 'ok', step: { kind, text: 't' } } })
    expect(s.screen).toBe(kind)
    expect(s.sessionToken).toBe('tok')
  }
})

test('submitted session-expired resets to the start; unauthorized routes to unauthorized', () => {
  const base = { ...initialState, sessionToken: 'tok', screen: 'question' as const }
  expect(reducer(base, { type: 'submitted', result: { status: 'session-expired' } })).toEqual(initialState)
  expect(reducer(base, { type: 'submitted', result: { status: 'unauthorized' } }).screen).toBe('unauthorized')
})

test('submitted unavailable keeps the session token so retry is possible', () => {
  const s = reducer({ ...initialState, sessionToken: 'tok' }, { type: 'submitted', result: { status: 'unavailable' } })
  expect(s.screen).toBe('unavailable')
  expect(s.sessionToken).toBe('tok')
})

test('stop resets to the initial state from anywhere', () => {
  const s = reducer({ ...initialState, screen: 'summary', sessionToken: 'tok', language: 'fr' }, { type: 'stop' })
  expect(s).toEqual(initialState)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- kioskMachine`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `kioskMachine.ts`**

```ts
import type { Screen, StartResult, Step, StepKind, SubmitResult } from '../types'

export interface MachineState {
  screen: Screen
  language: string | null
  sessionToken: string | null
  step: Step | null
  lastAnswer: string | null
}

export const initialState: MachineState = {
  screen: 'language',
  language: null,
  sessionToken: null,
  step: null,
  lastAnswer: null,
}

export type Action =
  | { type: 'selectLanguage'; language: string }
  | { type: 'declineConsent' }
  | { type: 'started'; result: StartResult }
  | { type: 'submitting'; answer: string }
  | { type: 'submitted'; result: SubmitResult }
  | { type: 'stop' }

// Step kinds map 1:1 to screens of the same name.
function screenFor(kind: StepKind): Screen {
  return kind
}

export function reducer(state: MachineState, action: Action): MachineState {
  switch (action.type) {
    case 'selectLanguage':
      return { ...state, language: action.language, screen: 'consent' }
    case 'declineConsent':
      return initialState
    case 'started': {
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized' }
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable' }
      return { ...state, sessionToken: r.sessionToken, step: r.step, screen: screenFor(r.step.kind) }
    }
    case 'submitting':
      return { ...state, lastAnswer: action.answer }
    case 'submitted': {
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized' }
      if (r.status === 'session-expired') return initialState
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable' }
      return { ...state, step: r.step, screen: screenFor(r.step.kind) }
    }
    case 'stop':
      return initialState
    default:
      return state
  }
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- kioskMachine && npm run typecheck && npm run lint`
Expected: PASS; exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/state
git commit -m "feat(kiosk-ui): pure screen state machine (step.kind -> screen, stop resets)"
```

---

## Task 4: i18n — catalogs, init, language metadata, `applyLanguage`

**Files:**
- Create: `frontend/src/i18n/languages.ts`, `frontend/src/i18n/index.ts`, `frontend/src/i18n/locales/{it,en,fr,es,ar}.ts`
- Test: `frontend/src/i18n/i18n.test.ts`

**Interfaces:**
- Produces:
  - `interface LanguageMeta { code: string; name: string; dir: 'ltr' | 'rtl' }`
  - `const LANGUAGES: LanguageMeta[]` (it, en, fr, es, ar — ar is rtl)
  - `function dirFor(code: string): 'ltr' | 'rtl'`
  - `default export` the initialized `i18n` instance
  - `function applyLanguage(code: string): void` — changes language AND sets `document.documentElement.dir` / `lang`
  - Catalog shape: keys `consent.title`, `consent.intro`? (no — see below), `consent.point.work|purpose|onlyWork|voluntary|local`, `consent.accept`, `consent.decline`, `prompt.placeholder`, `prompt.next`, `confirm.yes`, `confirm.no`, `confirm.correctPlaceholder`, `confirm.send`, `refusal.banner`, `unavailable.text`, `unavailable.retry`, `completed.text`, `completed.finish`, `unauthorized.text`, `stop.label`, `textSize.label`, `textSize.normal`, `textSize.large`, `textSize.xlarge`, `voice.placeholder`.

- [ ] **Step 1: Write the failing test**

`frontend/src/i18n/i18n.test.ts`:
```ts
import { expect, test } from 'vitest'
import i18n, { applyLanguage } from './index'
import { dirFor, LANGUAGES } from './languages'
import { it } from './locales/it'
import { en } from './locales/en'
import { fr } from './locales/fr'
import { es } from './locales/es'
import { ar } from './locales/ar'

test('all five languages are present with the right direction', () => {
  expect(LANGUAGES.map((l) => l.code)).toEqual(['it', 'en', 'fr', 'es', 'ar'])
  expect(dirFor('ar')).toBe('rtl')
  expect(dirFor('it')).toBe('ltr')
  expect(dirFor('unknown')).toBe('ltr')
})

test('every catalog has exactly the same keys as the Italian catalog', () => {
  const keysOf = (o: object, p = ''): string[] =>
    Object.entries(o).flatMap(([k, v]) =>
      typeof v === 'object' && v !== null ? keysOf(v, `${p}${k}.`) : [`${p}${k}`],
    )
  const itKeys = keysOf(it).sort()
  for (const cat of [en, fr, es, ar]) expect(keysOf(cat).sort()).toEqual(itKeys)
})

test('applyLanguage switches strings and sets document direction', () => {
  applyLanguage('it')
  expect(i18n.t('stop.label')).toBe('Ferma')
  expect(document.documentElement.dir).toBe('ltr')

  applyLanguage('ar')
  expect(i18n.t('stop.label')).toBe('إيقاف')
  expect(document.documentElement.dir).toBe('rtl')
  expect(document.documentElement.lang).toBe('ar')

  applyLanguage('en')
  expect(i18n.t('stop.label')).toBe('Stop')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- i18n`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement `languages.ts`**

```ts
export interface LanguageMeta {
  code: string
  name: string
  dir: 'ltr' | 'rtl'
}

// Each endonym is written in its own language/script (constant, not translated).
export const LANGUAGES: LanguageMeta[] = [
  { code: 'it', name: 'Italiano', dir: 'ltr' },
  { code: 'en', name: 'English', dir: 'ltr' },
  { code: 'fr', name: 'Français', dir: 'ltr' },
  { code: 'es', name: 'Español', dir: 'ltr' },
  { code: 'ar', name: 'العربية', dir: 'rtl' },
]

export function dirFor(code: string): 'ltr' | 'rtl' {
  return LANGUAGES.find((l) => l.code === code)?.dir ?? 'ltr'
}
```

- [ ] **Step 4: Implement the five catalogs**

`frontend/src/i18n/locales/it.ts`:
```ts
export const it = {
  consent: {
    title: 'Prima di iniziare 👋',
    point: {
      work: 'Ti faccio qualche domanda sul lavoro che sai fare e che vorresti fare.',
      purpose: 'Serve solo a trovarti opportunità di lavoro e formazione.',
      onlyWork: 'Raccolgo solo cose sul lavoro. Niente reati, niente salute, niente famiglia.',
      voluntary: 'È libero: puoi fermarti quando vuoi con il pulsante «Ferma».',
      local: 'I dati restano qui. Non escono.',
    },
    accept: 'Ho capito, iniziamo',
    decline: 'Non ora',
  },
  prompt: { placeholder: 'Scrivi qui la tua risposta…', next: 'Avanti' },
  confirm: {
    yes: 'Sì, è corretto',
    no: 'No, correggi qualcosa',
    correctPlaceholder: 'Scrivi la correzione…',
    send: 'Invia',
  },
  refusal: { banner: 'Posso aiutarti solo con lavoro e formazione.' },
  unavailable: { text: 'Un momento, ci riprovo tra poco. Puoi anche scrivere di nuovo.', retry: 'Riprova' },
  completed: {
    text: 'Grazie! Ho raccolto tutto. Un operatore userà il tuo profilo per cercarti opportunità.',
    finish: 'Ho finito',
  },
  unauthorized: { text: 'Questa postazione non è autorizzata. Chiedi aiuto a un operatore.' },
  stop: { label: 'Ferma' },
  textSize: { label: 'Dimensione del testo', normal: 'Normale', large: 'Grande', xlarge: 'Molto grande' },
  voice: { placeholder: 'Parla · Ascolta (prossima fase)' },
}
```

`frontend/src/i18n/locales/en.ts`:
```ts
export const en = {
  consent: {
    title: 'Before we start 👋',
    point: {
      work: "I'll ask you a few questions about the work you can do and would like to do.",
      purpose: "It's only to help find you work and training opportunities.",
      onlyWork: 'I only collect things about work. No offences, no health, no family.',
      voluntary: "It's free: you can stop whenever you want with the «Stop» button.",
      local: "Your data stays here. It doesn't leave.",
    },
    accept: "I understand, let's start",
    decline: 'Not now',
  },
  prompt: { placeholder: 'Type your answer here…', next: 'Next' },
  confirm: {
    yes: "Yes, that's correct",
    no: 'No, correct something',
    correctPlaceholder: 'Type the correction…',
    send: 'Send',
  },
  refusal: { banner: 'I can only help with work and training.' },
  unavailable: { text: "One moment, I'll try again shortly. You can also type again.", retry: 'Try again' },
  completed: {
    text: "Thank you! I've collected everything. An operator will use your profile to look for opportunities.",
    finish: "I'm done",
  },
  unauthorized: { text: 'This station is not authorized. Please ask an operator for help.' },
  stop: { label: 'Stop' },
  textSize: { label: 'Text size', normal: 'Normal', large: 'Large', xlarge: 'Very large' },
  voice: { placeholder: 'Speak · Listen (coming soon)' },
}
```

`frontend/src/i18n/locales/fr.ts`:
```ts
export const fr = {
  consent: {
    title: 'Avant de commencer 👋',
    point: {
      work: 'Je vais te poser quelques questions sur le travail que tu sais faire et que tu aimerais faire.',
      purpose: "C'est seulement pour t'aider à trouver du travail et des formations.",
      onlyWork: "Je ne recueille que des choses sur le travail. Pas d'infractions, pas de santé, pas de famille.",
      voluntary: "C'est libre : tu peux t'arrêter quand tu veux avec le bouton « Arrêter ».",
      local: 'Tes données restent ici. Elles ne sortent pas.',
    },
    accept: "J'ai compris, commençons",
    decline: 'Pas maintenant',
  },
  prompt: { placeholder: 'Écris ta réponse ici…', next: 'Suivant' },
  confirm: {
    yes: "Oui, c'est correct",
    no: 'Non, corriger quelque chose',
    correctPlaceholder: 'Écris la correction…',
    send: 'Envoyer',
  },
  refusal: { banner: 'Je peux seulement aider pour le travail et la formation.' },
  unavailable: { text: 'Un instant, je réessaie bientôt. Tu peux aussi réécrire.', retry: 'Réessayer' },
  completed: {
    text: "Merci ! J'ai tout recueilli. Un opérateur utilisera ton profil pour chercher des opportunités.",
    finish: "J'ai terminé",
  },
  unauthorized: { text: "Ce poste n'est pas autorisé. Demande de l'aide à un opérateur." },
  stop: { label: 'Arrêter' },
  textSize: { label: 'Taille du texte', normal: 'Normale', large: 'Grande', xlarge: 'Très grande' },
  voice: { placeholder: 'Parler · Écouter (bientôt)' },
}
```

`frontend/src/i18n/locales/es.ts`:
```ts
export const es = {
  consent: {
    title: 'Antes de empezar 👋',
    point: {
      work: 'Te haré algunas preguntas sobre el trabajo que sabes hacer y que te gustaría hacer.',
      purpose: 'Es solo para ayudarte a encontrar oportunidades de trabajo y formación.',
      onlyWork: 'Solo recojo cosas sobre el trabajo. Nada de delitos, nada de salud, nada de familia.',
      voluntary: 'Es libre: puedes parar cuando quieras con el botón «Detener».',
      local: 'Tus datos se quedan aquí. No salen.',
    },
    accept: 'Entendido, empecemos',
    decline: 'Ahora no',
  },
  prompt: { placeholder: 'Escribe aquí tu respuesta…', next: 'Siguiente' },
  confirm: {
    yes: 'Sí, es correcto',
    no: 'No, corregir algo',
    correctPlaceholder: 'Escribe la corrección…',
    send: 'Enviar',
  },
  refusal: { banner: 'Solo puedo ayudar con trabajo y formación.' },
  unavailable: { text: 'Un momento, lo intento de nuevo enseguida. También puedes escribir otra vez.', retry: 'Reintentar' },
  completed: {
    text: '¡Gracias! He recogido todo. Un operador usará tu perfil para buscar oportunidades.',
    finish: 'He terminado',
  },
  unauthorized: { text: 'Este puesto no está autorizado. Pide ayuda a un operador.' },
  stop: { label: 'Detener' },
  textSize: { label: 'Tamaño del texto', normal: 'Normal', large: 'Grande', xlarge: 'Muy grande' },
  voice: { placeholder: 'Hablar · Escuchar (próximamente)' },
}
```

`frontend/src/i18n/locales/ar.ts` (best-effort; native review is a pre-pilot follow-up — §8):
```ts
export const ar = {
  consent: {
    title: 'قبل أن نبدأ 👋',
    point: {
      work: 'سأطرح عليك بعض الأسئلة عن العمل الذي تعرف كيف تقوم به وتودّ القيام به.',
      purpose: 'هذا فقط لمساعدتك في إيجاد فرص عمل وتدريب.',
      onlyWork: 'أجمع فقط أمورًا تتعلق بالعمل. لا جرائم، لا صحة، لا عائلة.',
      voluntary: 'المشاركة حرة: يمكنك التوقف متى شئت بزر «إيقاف».',
      local: 'بياناتك تبقى هنا. لا تخرج.',
    },
    accept: 'فهمت، لنبدأ',
    decline: 'ليس الآن',
  },
  prompt: { placeholder: 'اكتب إجابتك هنا…', next: 'التالي' },
  confirm: {
    yes: 'نعم، هذا صحيح',
    no: 'لا، صحّح شيئًا',
    correctPlaceholder: 'اكتب التصحيح…',
    send: 'إرسال',
  },
  refusal: { banner: 'يمكنني المساعدة فقط في العمل والتدريب.' },
  unavailable: { text: 'لحظة، سأحاول مجددًا بعد قليل. يمكنك أيضًا الكتابة من جديد.', retry: 'أعد المحاولة' },
  completed: {
    text: 'شكرًا! لقد جمعت كل شيء. سيستخدم أحد الموظفين ملفك للبحث عن فرص.',
    finish: 'لقد انتهيت',
  },
  unauthorized: { text: 'هذه المحطة غير مصرّح بها. اطلب المساعدة من موظف.' },
  stop: { label: 'إيقاف' },
  textSize: { label: 'حجم النص', normal: 'عادي', large: 'كبير', xlarge: 'كبير جدًا' },
  voice: { placeholder: 'تحدّث · استمع (قريبًا)' },
}
```

- [ ] **Step 5: Implement `i18n/index.ts`**

```ts
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { dirFor } from './languages'
import { it } from './locales/it'
import { en } from './locales/en'
import { fr } from './locales/fr'
import { es } from './locales/es'
import { ar } from './locales/ar'

void i18n.use(initReactI18next).init({
  resources: {
    it: { translation: it },
    en: { translation: en },
    fr: { translation: fr },
    es: { translation: es },
    ar: { translation: ar },
  },
  lng: 'it',
  fallbackLng: 'it',
  interpolation: { escapeValue: false },
})

export function applyLanguage(code: string): void {
  void i18n.changeLanguage(code)
  const dir = dirFor(code)
  document.documentElement.dir = dir
  document.documentElement.lang = code
}

export default i18n
```

- [ ] **Step 6: Run the tests and the gate**

Run: `npm test -- i18n && npm run typecheck && npm run lint`
Expected: PASS (catalogs key-parity holds; direction switches).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/i18n
git commit -m "feat(kiosk-ui): i18n catalogs (it/en/fr/es/ar) + RTL applyLanguage"
```

---

## Task 5: Accessibility — `TextSize` context on CSS variables

**Files:**
- Create: `frontend/src/a11y/TextSize.tsx`
- Modify: `frontend/src/styles/theme.css` (add the text-size-driven rules and shared layout classes used by later tasks)
- Test: `frontend/src/a11y/TextSize.test.tsx`

**Interfaces:**
- Produces:
  - `type TextSize = 'normal' | 'large' | 'xlarge'`
  - `function TextSizeProvider(props: { children: ReactNode }): JSX.Element` — sets `--text-scale` on `document.documentElement`
  - `function useTextSize(): { size: TextSize; setSize: (s: TextSize) => void }`

- [ ] **Step 1: Write the failing test**

`frontend/src/a11y/TextSize.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { TextSizeProvider, useTextSize } from './TextSize'

function Probe() {
  const { size, setSize } = useTextSize()
  return (
    <div>
      <span>size:{size}</span>
      <button onClick={() => setSize('xlarge')}>bigger</button>
    </div>
  )
}

test('default is normal (scale 1) and setSize updates the CSS variable', async () => {
  render(
    <TextSizeProvider>
      <Probe />
    </TextSizeProvider>,
  )
  expect(screen.getByText('size:normal')).toBeInTheDocument()
  expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1')

  await userEvent.click(screen.getByText('bigger'))
  expect(screen.getByText('size:xlarge')).toBeInTheDocument()
  expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1.5')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- TextSize`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `TextSize.tsx`**

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type TextSize = 'normal' | 'large' | 'xlarge'

const SCALE: Record<TextSize, string> = { normal: '1', large: '1.25', xlarge: '1.5' }

interface TextSizeContextValue {
  size: TextSize
  setSize: (s: TextSize) => void
}

const TextSizeContext = createContext<TextSizeContextValue | null>(null)

export function TextSizeProvider({ children }: { children: ReactNode }) {
  const [size, setSize] = useState<TextSize>('normal')
  useEffect(() => {
    document.documentElement.style.setProperty('--text-scale', SCALE[size])
  }, [size])
  return <TextSizeContext.Provider value={{ size, setSize }}>{children}</TextSizeContext.Provider>
}

export function useTextSize(): TextSizeContextValue {
  const ctx = useContext(TextSizeContext)
  if (!ctx) throw new Error('useTextSize must be used within a TextSizeProvider')
  return ctx
}
```

- [ ] **Step 4: Extend `theme.css` with shared layout/high-contrast classes**

Append to `frontend/src/styles/theme.css`:
```css
.app { min-height: 100vh; display: flex; flex-direction: column; }
.chrome {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 12px 16px; border-bottom: 2px solid #e5e7eb;
}
main { flex: 1; padding: 24px 16px; max-width: 720px; margin-inline: auto; width: 100%; }

.prompt-text { font-size: calc(24px * var(--text-scale)); font-weight: 700; line-height: 1.35; }
textarea {
  width: 100%; min-height: 96px; padding: 14px; border: 2px solid #9ca3af;
  border-radius: 10px; font: inherit; font-size: calc(18px * var(--text-scale));
}
:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }

.big-button {
  font: inherit; font-size: calc(18px * var(--text-scale)); font-weight: 700;
  padding: 16px 24px; border-radius: 10px; border: 2px solid transparent; cursor: pointer;
  width: 100%; margin-block: 8px;
}
.big-button:disabled { opacity: 0.5; cursor: not-allowed; }
.big-confirm { background: var(--confirm); color: #fff; }
.big-secondary { background: #fff; color: #374151; border-color: #9ca3af; }
.big-danger { background: var(--danger); color: #fff; }

.stop-button {
  background: var(--danger); color: #fff; border: 0; border-radius: 8px;
  padding: 10px 16px; font: inherit; font-weight: 700; cursor: pointer;
}
.notice { padding: 20px; border-radius: 12px; font-size: calc(20px * var(--text-scale)); }
.notice-warn { background: var(--warn-bg); }
.notice-info { background: #f8fafc; }
.notice-success { background: #f0fdf4; }
.notice-error { background: #fef2f2; }
.banner-warn { background: var(--warn-bg); border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; font-weight: 600; }

.language-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.language-tile {
  font: inherit; font-size: calc(22px * var(--text-scale)); font-weight: 700;
  padding: 18px; border: 2px solid #cbd5e1; border-radius: 12px; background: #fff; cursor: pointer;
}
.voice-placeholder { color: var(--muted); border: 1px dashed #cbd5e1; border-radius: 8px; padding: 6px 10px; }
.text-size-control button { font: inherit; padding: 6px 10px; margin-inline-start: 4px; cursor: pointer; }
.text-size-control button[aria-pressed='true'] { background: var(--accent); color: #fff; }
```

- [ ] **Step 5: Run the tests and the gate**

Run: `npm test -- TextSize && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/a11y frontend/src/styles/theme.css
git commit -m "feat(kiosk-ui): text-size accessibility context + high-contrast theme classes"
```

---

## Task 6: Shared presentational components

**Files:**
- Create: `frontend/src/components/BigButton.tsx`, `AnswerPrompt.tsx`, `ConfirmCorrect.tsx`, `Notice.tsx`, `StopButton.tsx`, `TextSizeControl.tsx`, `VoicePlaceholder.tsx`
- Create: `frontend/src/test/utils.tsx` (render helper wrapping i18n + TextSize providers)
- Test: `frontend/src/components/AnswerPrompt.test.tsx`, `ConfirmCorrect.test.tsx`, `StopButton.test.tsx`, `TextSizeControl.test.tsx`, `VoicePlaceholder.test.tsx`

**Interfaces:**
- Consumes: `useTranslation` (react-i18next), `useTextSize` (Task 5).
- Produces:
  - `BigButton(props: { variant?: 'confirm' | 'secondary' | 'danger' } & ButtonHTMLAttributes<HTMLButtonElement>)`
  - `AnswerPrompt(props: { text: string; onSubmit: (answer: string) => void; banner?: string })` — text prompt + textarea + Next; trims; ignores empty
  - `ConfirmCorrect(props: { text: string; onSubmit: (answer: string) => void })` — Yes (submits `t('confirm.yes')`) / No→reveals textarea→Send (submits typed correction)
  - `Notice(props: { tone: 'warn' | 'info' | 'success' | 'error'; text: string; children?: ReactNode })`
  - `StopButton(props: { onStop: () => void })`
  - `TextSizeControl()` — three buttons, `aria-pressed` on the active size
  - `VoicePlaceholder()` — disabled, `aria-hidden`
  - `renderWithProviders(ui: ReactElement)` from `test/utils.tsx`

- [ ] **Step 1: Write `test/utils.tsx` and the failing tests**

`frontend/src/test/utils.tsx`:
```tsx
import { render, type RenderResult } from '@testing-library/react'
import { type ReactElement } from 'react'
import { I18nextProvider } from 'react-i18next'
import i18n from '../i18n'
import { TextSizeProvider } from '../a11y/TextSize'

export function renderWithProviders(ui: ReactElement): RenderResult {
  return render(
    <I18nextProvider i18n={i18n}>
      <TextSizeProvider>{ui}</TextSizeProvider>
    </I18nextProvider>,
  )
}
```

`frontend/src/components/AnswerPrompt.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { AnswerPrompt } from './AnswerPrompt'
import i18n from '../i18n'

test('submits the trimmed answer and clears the field; empty is ignored', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<AnswerPrompt text="Che lavoro sai fare?" onSubmit={onSubmit} />)
  expect(screen.getByText('Che lavoro sai fare?')).toBeInTheDocument()

  const next = screen.getByRole('button', { name: 'Avanti' })
  await userEvent.click(next)
  expect(onSubmit).not.toHaveBeenCalled() // empty ignored (button disabled)

  await userEvent.type(screen.getByRole('textbox'), '  so cucinare  ')
  await userEvent.click(next)
  expect(onSubmit).toHaveBeenCalledWith('so cucinare')
})

test('renders an optional banner (used by the refusal screen)', () => {
  renderWithProviders(<AnswerPrompt text="Torniamo a te" onSubmit={vi.fn()} banner="Solo lavoro" />)
  expect(screen.getByText('Solo lavoro')).toBeInTheDocument()
})
```

`frontend/src/components/ConfirmCorrect.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { ConfirmCorrect } from './ConfirmCorrect'
import i18n from '../i18n'

test('confirm submits the localized affirmative', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<ConfirmCorrect text="Ho capito: sai cucinare" onSubmit={onSubmit} />)
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è corretto' }))
  expect(onSubmit).toHaveBeenCalledWith('Sì, è corretto')
})

test('correct reveals a field and submits the typed correction', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<ConfirmCorrect text="Ho capito: sai cucinare" onSubmit={onSubmit} />)
  await userEvent.click(screen.getByRole('button', { name: 'No, correggi qualcosa' }))
  await userEvent.type(screen.getByRole('textbox'), 'so anche guidare il muletto')
  await userEvent.click(screen.getByRole('button', { name: 'Invia' }))
  expect(onSubmit).toHaveBeenCalledWith('so anche guidare il muletto')
})
```

`frontend/src/components/StopButton.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { StopButton } from './StopButton'
import i18n from '../i18n'

test('calls onStop when clicked', async () => {
  await i18n.changeLanguage('it')
  const onStop = vi.fn()
  renderWithProviders(<StopButton onStop={onStop} />)
  await userEvent.click(screen.getByRole('button', { name: /Ferma/ }))
  expect(onStop).toHaveBeenCalledOnce()
})
```

`frontend/src/components/TextSizeControl.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { TextSizeControl } from './TextSizeControl'
import i18n from '../i18n'

test('marks the chosen size as pressed and scales the root variable', async () => {
  await i18n.changeLanguage('it')
  renderWithProviders(<TextSizeControl />)
  await userEvent.click(screen.getByRole('button', { name: 'Molto grande' }))
  expect(screen.getByRole('button', { name: 'Molto grande' })).toHaveAttribute('aria-pressed', 'true')
  expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1.5')
})
```

`frontend/src/components/VoicePlaceholder.test.tsx`:
```tsx
import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { VoicePlaceholder } from './VoicePlaceholder'
import i18n from '../i18n'

test('is present but inert (aria-hidden, no interactive control)', async () => {
  await i18n.changeLanguage('it')
  const { container } = renderWithProviders(<VoicePlaceholder />)
  const el = container.querySelector('.voice-placeholder')
  expect(el).toBeTruthy()
  expect(el).toHaveAttribute('aria-hidden', 'true')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- components`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement the components**

`frontend/src/components/BigButton.tsx`:
```tsx
import { type ButtonHTMLAttributes } from 'react'

type Variant = 'confirm' | 'secondary' | 'danger'

export function BigButton({
  variant = 'confirm',
  className,
  ...props
}: { variant?: Variant } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`big-button big-${variant} ${className ?? ''}`.trim()} {...props} />
}
```

`frontend/src/components/AnswerPrompt.tsx`:
```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from './BigButton'

export function AnswerPrompt({
  text,
  onSubmit,
  banner,
}: {
  text: string
  onSubmit: (answer: string) => void
  banner?: string
}) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const trimmed = value.trim()
  return (
    <div>
      {banner && <div className="banner-warn">{banner}</div>}
      <p className="prompt-text">{text}</p>
      <textarea
        aria-label={t('prompt.placeholder')}
        placeholder={t('prompt.placeholder')}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <BigButton
        variant="confirm"
        disabled={!trimmed}
        onClick={() => {
          onSubmit(trimmed)
          setValue('')
        }}
      >
        {t('prompt.next')}
      </BigButton>
    </div>
  )
}
```

`frontend/src/components/ConfirmCorrect.tsx`:
```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from './BigButton'

export function ConfirmCorrect({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  const { t } = useTranslation()
  const [correcting, setCorrecting] = useState(false)
  const [value, setValue] = useState('')
  const trimmed = value.trim()
  return (
    <div>
      <p className="prompt-text">{text}</p>
      {!correcting ? (
        <>
          <BigButton variant="confirm" onClick={() => onSubmit(t('confirm.yes'))}>
            {t('confirm.yes')}
          </BigButton>
          <BigButton variant="secondary" onClick={() => setCorrecting(true)}>
            {t('confirm.no')}
          </BigButton>
        </>
      ) : (
        <>
          <textarea
            aria-label={t('confirm.correctPlaceholder')}
            placeholder={t('confirm.correctPlaceholder')}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <BigButton variant="confirm" disabled={!trimmed} onClick={() => onSubmit(trimmed)}>
            {t('confirm.send')}
          </BigButton>
        </>
      )}
    </div>
  )
}
```

`frontend/src/components/Notice.tsx`:
```tsx
import { type ReactNode } from 'react'

export function Notice({
  tone,
  text,
  children,
}: {
  tone: 'warn' | 'info' | 'success' | 'error'
  text: string
  children?: ReactNode
}) {
  return (
    <div className={`notice notice-${tone}`}>
      <p>{text}</p>
      {children}
    </div>
  )
}
```

`frontend/src/components/StopButton.tsx`:
```tsx
import { useTranslation } from 'react-i18next'

export function StopButton({ onStop }: { onStop: () => void }) {
  const { t } = useTranslation()
  return (
    <button className="stop-button" onClick={onStop}>
      ✕ {t('stop.label')}
    </button>
  )
}
```

`frontend/src/components/TextSizeControl.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { useTextSize, type TextSize } from '../a11y/TextSize'

const SIZES: TextSize[] = ['normal', 'large', 'xlarge']

export function TextSizeControl() {
  const { t } = useTranslation()
  const { size, setSize } = useTextSize()
  return (
    <div className="text-size-control" role="group" aria-label={t('textSize.label')}>
      {SIZES.map((s) => (
        <button key={s} aria-pressed={size === s} onClick={() => setSize(s)}>
          {t(`textSize.${s}`)}
        </button>
      ))}
    </div>
  )
}
```

`frontend/src/components/VoicePlaceholder.tsx`:
```tsx
import { useTranslation } from 'react-i18next'

// Voice is the next subsystem; this reserves the layout slot, inert for now.
export function VoicePlaceholder() {
  const { t } = useTranslation()
  return (
    <div className="voice-placeholder" aria-hidden="true">
      🎤 🔊 <em>{t('voice.placeholder')}</em>
    </div>
  )
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- components && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components frontend/src/test/utils.tsx
git commit -m "feat(kiosk-ui): shared components (prompt, confirm/correct, stop, text-size, voice placeholder)"
```

---

## Task 7: Entry screens — `LanguagePicker` + `Consent`

**Files:**
- Create: `frontend/src/screens/LanguagePicker.tsx`, `frontend/src/screens/Consent.tsx`
- Test: `frontend/src/screens/LanguagePicker.test.tsx`, `frontend/src/screens/Consent.test.tsx`

**Interfaces:**
- Consumes: `LANGUAGES` (Task 4), `BigButton` (Task 6), `useTranslation`.
- Produces:
  - `LanguagePicker(props: { onSelect: (code: string) => void })`
  - `Consent(props: { onAccept: () => void; onDecline: () => void })`

- [ ] **Step 1: Write the failing tests**

`frontend/src/screens/LanguagePicker.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { LanguagePicker } from './LanguagePicker'

test('shows all five endonyms and reports the chosen code', async () => {
  const onSelect = vi.fn()
  renderWithProviders(<LanguagePicker onSelect={onSelect} />)
  for (const name of ['Italiano', 'English', 'Français', 'Español', 'العربية']) {
    expect(screen.getByRole('button', { name })).toBeInTheDocument()
  }
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  expect(onSelect).toHaveBeenCalledWith('ar')
})
```

`frontend/src/screens/Consent.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Consent } from './Consent'
import i18n from '../i18n'

test('shows the consent points and wires accept/decline', async () => {
  await i18n.changeLanguage('it')
  const onAccept = vi.fn()
  const onDecline = vi.fn()
  renderWithProviders(<Consent onAccept={onAccept} onDecline={onDecline} />)
  expect(screen.getByText('Prima di iniziare 👋')).toBeInTheDocument()
  expect(screen.getByText(/Niente reati, niente salute, niente famiglia/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Ho capito, iniziamo' }))
  expect(onAccept).toHaveBeenCalledOnce()
  await userEvent.click(screen.getByRole('button', { name: 'Non ora' }))
  expect(onDecline).toHaveBeenCalledOnce()
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- screens/LanguagePicker screens/Consent`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement the screens**

`frontend/src/screens/LanguagePicker.tsx`:
```tsx
import { LANGUAGES } from '../i18n/languages'

// The picker itself is language-neutral: bilingual title + each endonym in its
// own script. No translated strings here (Global Constraints).
export function LanguagePicker({ onSelect }: { onSelect: (code: string) => void }) {
  return (
    <div className="language-picker">
      <h1 className="picker-title">Scegli la tua lingua · Choose your language</h1>
      <div className="language-grid">
        {LANGUAGES.map((l) => (
          <button
            key={l.code}
            className="language-tile"
            dir={l.dir}
            lang={l.code}
            onClick={() => onSelect(l.code)}
          >
            {l.name}
          </button>
        ))}
      </div>
    </div>
  )
}
```

`frontend/src/screens/Consent.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'

const POINTS = ['work', 'purpose', 'onlyWork', 'voluntary', 'local'] as const

export function Consent({ onAccept, onDecline }: { onAccept: () => void; onDecline: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="consent">
      <h1>{t('consent.title')}</h1>
      <ul>
        {POINTS.map((p) => (
          <li key={p}>{t(`consent.point.${p}`)}</li>
        ))}
      </ul>
      <BigButton variant="confirm" onClick={onAccept}>
        {t('consent.accept')}
      </BigButton>
      <BigButton variant="secondary" onClick={onDecline}>
        {t('consent.decline')}
      </BigButton>
    </div>
  )
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- screens/LanguagePicker screens/Consent && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/LanguagePicker.tsx frontend/src/screens/Consent.tsx frontend/src/screens/LanguagePicker.test.tsx frontend/src/screens/Consent.test.tsx
git commit -m "feat(kiosk-ui): language picker + informed consent screens"
```

---

## Task 8: Interview screens — `Question` + `Summary` + `Clarification`

**Files:**
- Create: `frontend/src/screens/Question.tsx`, `frontend/src/screens/Summary.tsx`, `frontend/src/screens/Clarification.tsx`
- Test: `frontend/src/screens/Question.test.tsx`, `frontend/src/screens/Summary.test.tsx`, `frontend/src/screens/Clarification.test.tsx`

**Interfaces:**
- Consumes: `AnswerPrompt`, `ConfirmCorrect` (Task 6).
- Produces:
  - `Question(props: { text: string; onSubmit: (answer: string) => void })` → `AnswerPrompt`
  - `Summary(props: { text: string; onSubmit: (answer: string) => void })` → `ConfirmCorrect`
  - `Clarification(props: { text: string; onSubmit: (answer: string) => void })` → `ConfirmCorrect`
  (Summary and Clarification both use the two-button confirm/correct pattern per spec §3.3 — §5 "chiede conferma".)

- [ ] **Step 1: Write the failing tests**

`frontend/src/screens/Question.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Question } from './Question'
import i18n from '../i18n'

test('shows the backend question text and submits the typed answer', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Question text="In quali lingue te la cavi?" onSubmit={onSubmit} />)
  expect(screen.getByText('In quali lingue te la cavi?')).toBeInTheDocument()
  await userEvent.type(screen.getByRole('textbox'), 'italiano e arabo')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))
  expect(onSubmit).toHaveBeenCalledWith('italiano e arabo')
})
```

`frontend/src/screens/Summary.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Summary } from './Summary'
import i18n from '../i18n'

test('shows the recap and confirms with one tap', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Summary text="Ecco cosa ho capito: sai cucinare" onSubmit={onSubmit} />)
  expect(screen.getByText('Ecco cosa ho capito: sai cucinare')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è corretto' }))
  expect(onSubmit).toHaveBeenCalledWith('Sì, è corretto')
})
```

`frontend/src/screens/Clarification.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Clarification } from './Clarification'
import i18n from '../i18n'

test('lets the person correct an incongruence', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Clarification text="Hai detto 5 anni, ma le date dicono 2. È corretto?" onSubmit={onSubmit} />)
  await userEvent.click(screen.getByRole('button', { name: 'No, correggi qualcosa' }))
  await userEvent.type(screen.getByRole('textbox'), 'erano 2 anni')
  await userEvent.click(screen.getByRole('button', { name: 'Invia' }))
  expect(onSubmit).toHaveBeenCalledWith('erano 2 anni')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- screens/Question screens/Summary screens/Clarification`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement the screens**

`frontend/src/screens/Question.tsx`:
```tsx
import { AnswerPrompt } from '../components/AnswerPrompt'

export function Question({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  return <AnswerPrompt text={text} onSubmit={onSubmit} />
}
```

`frontend/src/screens/Summary.tsx`:
```tsx
import { ConfirmCorrect } from '../components/ConfirmCorrect'

export function Summary({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  return <ConfirmCorrect text={text} onSubmit={onSubmit} />
}
```

`frontend/src/screens/Clarification.tsx`:
```tsx
import { ConfirmCorrect } from '../components/ConfirmCorrect'

export function Clarification({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  return <ConfirmCorrect text={text} onSubmit={onSubmit} />
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- screens/Question screens/Summary screens/Clarification && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Question.tsx frontend/src/screens/Summary.tsx frontend/src/screens/Clarification.tsx frontend/src/screens/Question.test.tsx frontend/src/screens/Summary.test.tsx frontend/src/screens/Clarification.test.tsx
git commit -m "feat(kiosk-ui): question + summary/clarification (confirm-correct) screens"
```

---

## Task 9: System-state screens — `Refusal` + `Unavailable` + `Completed` + `Unauthorized`

**Files:**
- Create: `frontend/src/screens/Refusal.tsx`, `Unavailable.tsx`, `Completed.tsx`, `Unauthorized.tsx`
- Test: `frontend/src/screens/Refusal.test.tsx`, `Unavailable.test.tsx`, `Completed.test.tsx`, `Unauthorized.test.tsx`

**Interfaces:**
- Consumes: `AnswerPrompt`, `Notice`, `BigButton` (Task 6), `useTranslation`.
- Produces:
  - `Refusal(props: { text: string; onSubmit: (answer: string) => void })` — gentle banner + `AnswerPrompt` (person stays in the interview, retries on-topic)
  - `Unavailable(props: { onRetry: () => void })` — info notice + retry button (localized copy, not API text)
  - `Completed(props: { onFinish: () => void })` — success notice + finish button
  - `Unauthorized()` — error notice, no action

- [ ] **Step 1: Write the failing tests**

`frontend/src/screens/Refusal.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Refusal } from './Refusal'
import i18n from '../i18n'

test('shows the gentle in-scope refusal and still accepts a new answer', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Refusal text="Torniamo a te: che lavoro ti piacerebbe?" onSubmit={onSubmit} />)
  expect(screen.getByText('Posso aiutarti solo con lavoro e formazione.')).toBeInTheDocument()
  expect(screen.getByText('Torniamo a te: che lavoro ti piacerebbe?')).toBeInTheDocument()
  await userEvent.type(screen.getByRole('textbox'), 'cuoco')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))
  expect(onSubmit).toHaveBeenCalledWith('cuoco')
})
```

`frontend/src/screens/Unavailable.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Unavailable } from './Unavailable'
import i18n from '../i18n'

test('shows a gentle degrade message and a retry action', async () => {
  await i18n.changeLanguage('it')
  const onRetry = vi.fn()
  renderWithProviders(<Unavailable onRetry={onRetry} />)
  expect(screen.getByText(/Un momento, ci riprovo/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Riprova' }))
  expect(onRetry).toHaveBeenCalledOnce()
})
```

`frontend/src/screens/Completed.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Completed } from './Completed'
import i18n from '../i18n'

test('thanks the person and finishes', async () => {
  await i18n.changeLanguage('it')
  const onFinish = vi.fn()
  renderWithProviders(<Completed onFinish={onFinish} />)
  expect(screen.getByText(/Grazie! Ho raccolto tutto/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Ho finito' }))
  expect(onFinish).toHaveBeenCalledOnce()
})
```

`frontend/src/screens/Unauthorized.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Unauthorized } from './Unauthorized'
import i18n from '../i18n'

test('shows the station-not-authorized message', async () => {
  await i18n.changeLanguage('it')
  renderWithProviders(<Unauthorized />)
  expect(screen.getByText(/Questa postazione non è autorizzata/)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- screens/Refusal screens/Unavailable screens/Completed screens/Unauthorized`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement the screens**

`frontend/src/screens/Refusal.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { AnswerPrompt } from '../components/AnswerPrompt'

export function Refusal({ text, onSubmit }: { text: string; onSubmit: (answer: string) => void }) {
  const { t } = useTranslation()
  return <AnswerPrompt text={text} onSubmit={onSubmit} banner={t('refusal.banner')} />
}
```

`frontend/src/screens/Unavailable.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { Notice } from '../components/Notice'

export function Unavailable({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <Notice tone="info" text={t('unavailable.text')}>
      <BigButton variant="confirm" onClick={onRetry}>
        {t('unavailable.retry')}
      </BigButton>
    </Notice>
  )
}
```

`frontend/src/screens/Completed.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { BigButton } from '../components/BigButton'
import { Notice } from '../components/Notice'

export function Completed({ onFinish }: { onFinish: () => void }) {
  const { t } = useTranslation()
  return (
    <Notice tone="success" text={t('completed.text')}>
      <BigButton variant="confirm" onClick={onFinish}>
        {t('completed.finish')}
      </BigButton>
    </Notice>
  )
}
```

`frontend/src/screens/Unauthorized.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { Notice } from '../components/Notice'

export function Unauthorized() {
  const { t } = useTranslation()
  return <Notice tone="error" text={t('unauthorized.text')} />
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- screens/Refusal screens/Unavailable screens/Completed screens/Unauthorized && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Refusal.tsx frontend/src/screens/Unavailable.tsx frontend/src/screens/Completed.tsx frontend/src/screens/Unauthorized.tsx frontend/src/screens/Refusal.test.tsx frontend/src/screens/Unavailable.test.tsx frontend/src/screens/Completed.test.tsx frontend/src/screens/Unauthorized.test.tsx
git commit -m "feat(kiosk-ui): system-state screens (refusal, unavailable, completed, unauthorized)"
```

---

## Task 10: App composition + full flow + always-mounted «Ferma»

**Files:**
- Modify (replace placeholder): `frontend/src/App.tsx`
- Create: `frontend/src/test/fakeClient.ts`
- Test: `frontend/src/App.test.tsx` (replace the Task 1 smoke test)

**Interfaces:**
- Consumes: `reducer`, `initialState` (Task 3); `kioskClient`, `KioskClient` (Task 2); `applyLanguage` (Task 4); `TextSizeProvider` (Task 5); all components (Task 6) and screens (Tasks 7-9).
- Produces:
  - `App(props?: { client?: KioskClient })` — default client is the real `kioskClient`; tests inject a fake.
  - `makeFakeClient(...)` helpers in `test/fakeClient.ts`.

- [ ] **Step 1: Write the failing test**

`frontend/src/test/fakeClient.ts`:
```ts
import type { KioskClient, StartResult, Step, SubmitResult } from '../types'

// Deterministic fake: `start` returns startResult; each `submit` returns the
// next scripted SubmitResult. Synthetic data only (§9).
export function makeFakeClient(opts: {
  start?: StartResult
  submits?: SubmitResult[]
}): KioskClient & { calls: { answers: string[] } } {
  const calls = { answers: [] as string[] }
  let i = 0
  const start: StartResult = opts.start ?? { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } }
  const submits = opts.submits ?? []
  return {
    calls,
    async startInterview() {
      return start
    },
    async submitAnswer(_token: string, answer: string) {
      calls.answers.push(answer)
      return submits[i++] ?? { status: 'ok', step: { kind: 'completed', text: 'fine' } }
    },
  }
}

export const step = (kind: Step['kind'], text: string): Step => ({ kind, text })
```

`frontend/src/App.test.tsx` (replaces Task 1 smoke test):
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { renderWithProviders } from './test/utils'
import { makeFakeClient, step } from './test/fakeClient'
import { App } from './App'

async function chooseItalianAndConsent() {
  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Ho capito, iniziamo' }))
}

test('happy path: language -> consent -> question -> summary -> completed', async () => {
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Che lavoro sai fare?') },
    submits: [
      { status: 'ok', step: step('summary', 'Ho capito: sai cucinare') },
      { status: 'ok', step: step('completed', 'Grazie!') },
    ],
  })
  renderWithProviders(<App client={client} />)

  await chooseItalianAndConsent()
  expect(await screen.findByText('Che lavoro sai fare?')).toBeInTheDocument()

  await userEvent.type(screen.getByRole('textbox'), 'so cucinare')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))

  expect(await screen.findByText('Ho capito: sai cucinare')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è corretto' }))

  expect(await screen.findByText(/Grazie! Ho raccolto tutto/)).toBeInTheDocument()
  expect(client.calls.answers).toEqual(['so cucinare', 'Sì, è corretto'])
})

test('«Ferma» resets to the language picker from mid-interview', async () => {
  const client = makeFakeClient({ start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Domanda') } })
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText('Domanda')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: /Ferma/ }))
  expect(screen.getByRole('button', { name: 'Italiano' })).toBeInTheDocument()
})

test('«Ferma» is not shown on the language picker (no session yet)', () => {
  renderWithProviders(<App client={makeFakeClient({})} />)
  expect(screen.queryByRole('button', { name: /Ferma/ })).not.toBeInTheDocument()
})

test('backend down on start -> unavailable screen, retry recovers', async () => {
  let firstCall = true
  const base = makeFakeClient({ start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Ripartiti') } })
  const client = {
    ...base,
    async startInterview() {
      if (firstCall) {
        firstCall = false
        return { status: 'unavailable' as const }
      }
      return { status: 'ok' as const, sessionToken: 'tok', step: step('question', 'Ripartiti') }
    },
  }
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText(/Un momento, ci riprovo/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Riprova' }))
  expect(await screen.findByText('Ripartiti')).toBeInTheDocument()
})

test('session expired mid-interview -> back to the language picker', async () => {
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Domanda') },
    submits: [{ status: 'session-expired' }],
  })
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()
  await userEvent.type(await screen.findByRole('textbox'), 'x')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))
  expect(await screen.findByRole('button', { name: 'Italiano' })).toBeInTheDocument()
})

test('unauthorized token -> station-not-authorized screen', async () => {
  const client = makeFakeClient({ start: { status: 'unauthorized' } })
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText(/Questa postazione non è autorizzata/)).toBeInTheDocument()
})

test('choosing Arabic sets the document direction to rtl', async () => {
  renderWithProviders(<App client={makeFakeClient({})} />)
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  expect(document.documentElement.dir).toBe('rtl')
})
```

Note: `App.test.tsx` uses `renderWithProviders` (i18n + TextSize). The Task 1 smoke test is fully replaced.

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- App`
Expected: FAIL (App still the placeholder; screens/flow absent).

- [ ] **Step 3: Implement `App.tsx`**

```tsx
import { useCallback, useReducer } from 'react'
import { kioskClient } from './api/kioskClient'
import type { KioskClient } from './types'
import { applyLanguage } from './i18n'
import { initialState, reducer } from './state/kioskMachine'
import { StopButton } from './components/StopButton'
import { TextSizeControl } from './components/TextSizeControl'
import { VoicePlaceholder } from './components/VoicePlaceholder'
import { LanguagePicker } from './screens/LanguagePicker'
import { Consent } from './screens/Consent'
import { Question } from './screens/Question'
import { Summary } from './screens/Summary'
import { Clarification } from './screens/Clarification'
import { Refusal } from './screens/Refusal'
import { Unavailable } from './screens/Unavailable'
import { Completed } from './screens/Completed'
import { Unauthorized } from './screens/Unauthorized'

export function App({ client = kioskClient }: { client?: KioskClient } = {}) {
  const [state, dispatch] = useReducer(reducer, initialState)

  const selectLanguage = useCallback((code: string) => {
    applyLanguage(code)
    dispatch({ type: 'selectLanguage', language: code })
  }, [])

  const start = useCallback(async () => {
    if (!state.language) return
    const result = await client.startInterview(state.language)
    dispatch({ type: 'started', result })
  }, [client, state.language])

  const submit = useCallback(
    async (answer: string) => {
      if (!state.sessionToken) return
      dispatch({ type: 'submitting', answer })
      const result = await client.submitAnswer(state.sessionToken, answer)
      dispatch({ type: 'submitted', result })
    },
    [client, state.sessionToken],
  )

  const retry = useCallback(async () => {
    if (state.sessionToken && state.lastAnswer !== null) {
      const result = await client.submitAnswer(state.sessionToken, state.lastAnswer)
      dispatch({ type: 'submitted', result })
    } else {
      await start()
    }
  }, [client, state.sessionToken, state.lastAnswer, start])

  const stop = useCallback(() => {
    applyLanguage('it')
    dispatch({ type: 'stop' })
  }, [])

  function renderScreen() {
    switch (state.screen) {
      case 'language':
        return <LanguagePicker onSelect={selectLanguage} />
      case 'consent':
        return <Consent onAccept={start} onDecline={() => dispatch({ type: 'declineConsent' })} />
      case 'question':
        return <Question text={state.step!.text} onSubmit={submit} />
      case 'summary':
        return <Summary text={state.step!.text} onSubmit={submit} />
      case 'clarification':
        return <Clarification text={state.step!.text} onSubmit={submit} />
      case 'refusal':
        return <Refusal text={state.step!.text} onSubmit={submit} />
      case 'unavailable':
        return <Unavailable onRetry={retry} />
      case 'completed':
        return <Completed onFinish={stop} />
      case 'unauthorized':
        return <Unauthorized />
    }
  }

  const inSession = state.screen !== 'language'
  return (
    <div className="app">
      <header className="chrome">
        {inSession ? <StopButton onStop={stop} /> : <span />}
        <TextSizeControl />
        <VoicePlaceholder />
      </header>
      <main>{renderScreen()}</main>
    </div>
  )
}
```

Note: `App` must be wrapped by `TextSizeProvider` — `main.tsx` renders `<App/>`, so update `main.tsx` to wrap it. See Step 4.

- [ ] **Step 4: Wrap the real app root with the providers in `main.tsx`**

Replace `frontend/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { I18nextProvider } from 'react-i18next'
import { App } from './App'
import i18n from './i18n'
import { TextSizeProvider } from './a11y/TextSize'
import './styles/theme.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nextProvider i18n={i18n}>
      <TextSizeProvider>
        <App />
      </TextSizeProvider>
    </I18nextProvider>
  </StrictMode>,
)
```

- [ ] **Step 5: Run the full suite and the gate**

Run: `npm test && npm run typecheck && npm run lint && npm run build`
Expected: all PASS / exit 0 (App flow + all prior tests green).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/main.tsx frontend/src/test/fakeClient.ts frontend/src/App.test.tsx
git commit -m "feat(kiosk-ui): compose full person flow with always-mounted stop + degradation"
```

---

## After all tasks

- Update `STATO_TECNICO.md`: add the `frontend/` directory (Vite+React+TS+react-i18next), the `kioskClient`, the screen state machine, i18n/RTL + `applyLanguage`, the text-size accessibility context, the build-time `VITE_KIOSK_TOKEN`, the dev proxy to `127.0.0.1:8000`, and the text-first / voice-next decomposition. Add to §14 follow-ups: (a) **Arabic strings need native-speaker review before pilot** (§8); (b) Playwright e2e + axe accessibility audit against the real S8 API (optional/manual, deferred); (c) the §7.1 "opzioni rapide" limitation (interview engine emits free-text) recorded in the spec.
- Run the final whole-branch review (opus), then `superpowers:finishing-a-development-branch`.
```
