# Portale Operatore — Fondamenta + Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the operator portal's foundation + authentication: a separate Vite+React+TS app with login, a forced change-password gate, session handling, logout, and an RBAC-aware authenticated shell — consuming the S5 auth API.

**Architecture:** A new standalone app in `operator-portal/` (the kiosk at `frontend/` is untouched). react-router for multi-view routing; an isolated `operatorClient` (Bearer token from sessionStorage) with typed fail-closed results; an `AuthProvider` context; `ProtectedRoute` guards (auth + must-change-password gate); a role-driven shell whose nav is a skeleton that later sub-projects extend.

**Tech Stack:** React 18 + Vite 5 + TypeScript, react-router-dom (MIT, new), react-i18next, Vitest + @testing-library/react. New directory `operator-portal/`.

## Global Constraints

- **Local/offline, open-source permissive only.** New dependency: `react-router-dom` (MIT). Others mirror the kiosk (`CLAUDE.md` §3).
- **Separate app in `operator-portal/`** (sibling of `frontend/`/`backend/`); the kiosk app at `frontend/` is NOT touched.
- **Session token via `Authorization: Bearer <token>`**, stored in **sessionStorage** (survives reload, cleared on tab/browser close). The `operatorClient` injects it; components never call `fetch`.
- **`must_change_password` gate enforced in the UI** (closes the S5 follow-up — the server does not enforce it): a logged-in operator with `must_change_password` is forced to `/change-password` before any other protected view.
- **Fail-closed degradation, never leave ambiguous state:** `401` → clear token + redirect to `/login` with a "sessione scaduta" notice; `403` → "non autorizzato"; login bad-creds `401` → generic "credenziali non valide"; network/5xx → retryable error. The backend error body is `{detail: string}`. No path throws to the UI.
- **RBAC nav by role (§6), UX-only** (the server remains the authority, returning 403): operator → Richieste di lavoro · Profili · Export; supervisor → Metriche · Attività; admin → Utenze · Configurazione; auditor → Audit. In THIS sub-project the nav items are **disabled placeholders** ("in arrivo") — the section pages arrive in later sub-projects.
- **All user-facing strings externalized via i18n** in an Italian catalog (`CLAUDE.md` §11); code/identifiers in English.
- **TDD; only synthetic data.** Vitest + @testing-library/react; `operatorClient` injected into `AuthProvider` so tests use a fake (no real fetch). Test output pristine.
- **Backend request/response field names exact:** login body `{username, password}`; response `{token, operator, must_change_password}`; change-password body `{old_password, new_password}`; `Operator = {id, username, display_name, role, is_active, must_change_password}`; `Role ∈ 'operator'|'supervisor'|'admin'|'auditor'`.

---

## File Structure

```
operator-portal/
  package.json, tsconfig.json, tsconfig.app.json, tsconfig.node.json, vite.config.ts, eslint.config.js, index.html, .env.example   (Task 1)
  src/
    main.tsx            (Task 1 placeholder → Task 6 providers+router)
    App.tsx             (Task 1 placeholder → Task 6 routes)
    vite-env.d.ts       (Task 1 — VITE_API_BASE)
    types.ts            (Task 2 — Operator, Role, result unions, OperatorClient)
    api/operatorClient.ts        (Task 2)
    auth/session.ts     (Task 2 — sessionStorage token; operatorClient depends on it)
    auth/AuthContext.tsx(Task 3 — AuthProvider/useAuth)
    auth/ProtectedRoute.tsx      (Task 5)
    rbac/nav.ts         (Task 5 — Role → nav items)
    shell/AppShell.tsx, shell/Nav.tsx   (Task 5)
    screens/Login.tsx, screens/ChangePassword.tsx   (Task 4)
    screens/Home.tsx, screens/Unauthorized.tsx      (Task 5)
    i18n/index.ts, i18n/locales/it.ts   (Task 2)
    styles/theme.css    (Task 1 baseline → Task 5 shell styles)
    test/setup.ts       (Task 1)
    test/utils.tsx      (Task 3 — renderWithProviders: MemoryRouter+i18n+AuthProvider)
    test/fakeClient.ts  (Task 2 — makeFakeClient)
```

Each `*.ts(x)` gets a sibling `*.test.ts(x)`.

---

## Task 1: Scaffold `operator-portal/` with test/typecheck/lint gate

**Files:**
- Create: `operator-portal/package.json`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`, `eslint.config.js`, `index.html`, `.env.example`, `src/main.tsx`, `src/App.tsx`, `src/vite-env.d.ts`, `src/styles/theme.css`, `src/test/setup.ts`
- Create test: `src/App.test.tsx`
- Modify: repo-root `.gitignore` (add `operator-portal/node_modules/`, `operator-portal/dist/`, `operator-portal/.env`)

**Interfaces:**
- Produces: a working app with `npm test`/`typecheck`/`lint`/`build` green; a placeholder `App` exported from `src/App.tsx`.

- [ ] **Step 1: Create `operator-portal/package.json`** (mirrors the kiosk, name changed, `react-router-dom` added)

```json
{
  "name": "bussola-operator-portal",
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
    "react-i18next": "^15.0.2",
    "react-router-dom": "^6.26.2"
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

- [ ] **Step 2: Create the three tsconfig files** — byte-identical to the kiosk's (`frontend/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`). Copy them verbatim:

`tsconfig.json`:
```json
{
  "files": [],
  "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }]
}
```
`tsconfig.app.json`:
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
`tsconfig.node.json`:
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

- [ ] **Step 3: Create `vite.config.ts`** (proxy the operator API paths; dev port 5174 so it can run alongside the kiosk)

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// The operator portal runs on its own Vite dev server (port 5174, alongside the
// kiosk on 5173); the S5/S6 API is served by the backend on 127.0.0.1:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/operators': 'http://127.0.0.1:8000',
      '/job-requests': 'http://127.0.0.1:8000',
      '/profiles': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
```

- [ ] **Step 4: Create `eslint.config.js`** — byte-identical to the kiosk's:

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
  {
    files: ['vite.config.ts'],
    rules: { '@typescript-eslint/triple-slash-reference': 'off' },
  },
)
```

- [ ] **Step 5: Create `index.html`, `src/vite-env.d.ts`, `src/main.tsx` (placeholder), `src/App.tsx` (placeholder), `src/styles/theme.css`, `src/test/setup.ts`**

`index.html`:
```html
<!doctype html>
<html lang="it">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Bussola — Portale operatore</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```
`src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_BASE: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
```
`src/main.tsx` (placeholder — replaced in Task 6):
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
`src/App.tsx` (placeholder):
```tsx
export function App() {
  return <div className="app">Bussola — Portale operatore</div>
}
```
`src/styles/theme.css` (baseline; extended in Task 5):
```css
:root {
  --fg: #111827;
  --bg: #ffffff;
  --muted: #6b7280;
  --accent: #2563eb;
  --danger: #b91c1c;
  --border: #e5e7eb;
}
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; color: var(--fg); background: var(--bg); }
```
`src/test/setup.ts` (identical to kiosk):
```ts
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => cleanup())
```

- [ ] **Step 6: Write the failing smoke test**

`src/App.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { App } from './App'

test('renders the operator portal shell', () => {
  render(<App />)
  expect(screen.getByText('Bussola — Portale operatore')).toBeInTheDocument()
})
```

- [ ] **Step 7: Install and run the gate**

Run (from `operator-portal/`):
```bash
npm install
npm test && npm run typecheck && npm run lint && npm run build
```
Expected: `npm install` resolves (react-router-dom within the caret range); all gate commands exit 0; smoke test passes. If a pinned version fails to resolve, use the nearest within the same major and note it.

- [ ] **Step 8: Update root `.gitignore` and commit**

Append to repo-root `.gitignore`:
```
operator-portal/node_modules/
operator-portal/dist/
operator-portal/.env
```
Create `operator-portal/.env.example`:
```
# Leave empty to use the Vite dev proxy / same origin.
VITE_API_BASE=
```
```bash
git add operator-portal/package.json operator-portal/package-lock.json operator-portal/tsconfig*.json operator-portal/vite.config.ts operator-portal/eslint.config.js operator-portal/index.html operator-portal/.env.example operator-portal/src .gitignore
git commit -m "feat(operator-portal): scaffold Vite+React+TS+react-router with test gate"
```

---

## Task 2: types + `operatorClient` + i18n catalog

**Files:**
- Create: `src/types.ts`, `src/api/operatorClient.ts`, `src/i18n/index.ts`, `src/i18n/locales/it.ts`, `src/test/fakeClient.ts`
- Test: `src/api/operatorClient.test.ts`, `src/i18n/i18n.test.ts`

**Interfaces:**
- Produces:
  - `type Role = 'operator' | 'supervisor' | 'admin' | 'auditor'`
  - `interface Operator { id: number; username: string; display_name: string; role: Role; is_active: boolean; must_change_password: boolean }`
  - `type LoginResult = { status: 'ok'; token: string; operator: Operator; mustChangePassword: boolean } | { status: 'invalid' } | { status: 'error' }`
  - `type MeResult = { status: 'ok'; operator: Operator } | { status: 'unauthorized' } | { status: 'error' }`
  - `type ChangeResult = { status: 'ok' } | { status: 'unauthorized' } | { status: 'error' }`
  - `interface OperatorClient { login(u,p): Promise<LoginResult>; me(): Promise<MeResult>; logout(): Promise<void>; changePassword(oldP,newP): Promise<ChangeResult> }`
  - `const operatorClient: OperatorClient`
  - i18n default instance + `makeFakeClient(...)`

- [ ] **Step 1: Write the failing tests**

`src/api/operatorClient.test.ts`:
```ts
import { afterEach, expect, test, vi } from 'vitest'
import { operatorClient } from './operatorClient'
import { setToken } from '../auth/session'

afterEach(() => {
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

function res(status: number, body?: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response
}

const OP = { id: 1, username: 'mrossi', display_name: 'M. Rossi', role: 'operator', is_active: true, must_change_password: false }

test('login maps 200 to ok with token+operator', async () => {
  const fetchMock = vi.fn().mockResolvedValue(res(200, { token: 'tok', operator: OP, must_change_password: true }))
  vi.stubGlobal('fetch', fetchMock)
  const r = await operatorClient.login('mrossi', 'pw')
  expect(r).toEqual({ status: 'ok', token: 'tok', operator: OP, mustChangePassword: true })
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/auth/login')
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ username: 'mrossi', password: 'pw' })
})

test('login maps 401 to invalid and 5xx/throw to error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.login('x', 'y')).toEqual({ status: 'invalid' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(500)))
  expect(await operatorClient.login('x', 'y')).toEqual({ status: 'error' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.login('x', 'y')).toEqual({ status: 'error' })
})

test('me sends the Bearer token from sessionStorage and maps 200/401', async () => {
  setToken('tok')
  const fetchMock = vi.fn().mockResolvedValue(res(200, OP))
  vi.stubGlobal('fetch', fetchMock)
  expect(await operatorClient.me()).toEqual({ status: 'ok', operator: OP })
  expect((fetchMock.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.me()).toEqual({ status: 'unauthorized' })
})

test('changePassword maps 204 to ok, 401 to unauthorized, other to error', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(204)))
  expect(await operatorClient.changePassword('old', 'newpassword')).toEqual({ status: 'ok' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.changePassword('old', 'newpassword')).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(400)))
  expect(await operatorClient.changePassword('old', 'x')).toEqual({ status: 'error' })
})
```

`src/i18n/i18n.test.ts`:
```ts
import { expect, test } from 'vitest'
import i18n from './index'

test('italian catalog resolves core auth/shell keys', async () => {
  await i18n.changeLanguage('it')
  expect(i18n.t('login.submit')).toBe('Entra')
  expect(i18n.t('shell.logout')).toBe('Esci')
  expect(i18n.t('errors.sessionExpired')).toBe('Sessione scaduta. Accedi di nuovo.')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- operatorClient i18n`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement `types.ts`**

```ts
export type Role = 'operator' | 'supervisor' | 'admin' | 'auditor'

export interface Operator {
  id: number
  username: string
  display_name: string
  role: Role
  is_active: boolean
  must_change_password: boolean
}

export type LoginResult =
  | { status: 'ok'; token: string; operator: Operator; mustChangePassword: boolean }
  | { status: 'invalid' }
  | { status: 'error' }

export type MeResult = { status: 'ok'; operator: Operator } | { status: 'unauthorized' } | { status: 'error' }

export type ChangeResult = { status: 'ok' } | { status: 'unauthorized' } | { status: 'error' }

export interface OperatorClient {
  login(username: string, password: string): Promise<LoginResult>
  me(): Promise<MeResult>
  logout(): Promise<void>
  changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult>
}
```

- [ ] **Step 4: Implement `operatorClient.ts`** (reads the token from `session.getToken()` — created in Task 3; this task creates `session.ts`'s getToken/setToken/clearToken too, since the client depends on them)

First create `src/auth/session.ts`:
```ts
const KEY = 'bussola.operator.token'
export function getToken(): string | null {
  return sessionStorage.getItem(KEY)
}
export function setToken(token: string): void {
  sessionStorage.setItem(KEY, token)
}
export function clearToken(): void {
  sessionStorage.removeItem(KEY)
}
```
Then `src/api/operatorClient.ts`:
```ts
import { getToken } from '../auth/session'
import type { ChangeResult, LoginResult, MeResult, Operator, OperatorClient } from '../types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

function headers(json: boolean): Record<string, string> {
  const h: Record<string, string> = {}
  if (json) h['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

async function login(username: string, password: string): Promise<LoginResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'invalid' }
  if (!res.ok) return { status: 'error' }
  try {
    const data = (await res.json()) as { token: string; operator: Operator; must_change_password: boolean }
    return { status: 'ok', token: data.token, operator: data.operator, mustChangePassword: data.must_change_password }
  } catch {
    return { status: 'error' }
  }
}

async function me(): Promise<MeResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/auth/me`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', operator: (await res.json()) as Operator }
  } catch {
    return { status: 'error' }
  }
}

async function logout(): Promise<void> {
  try {
    await fetch(`${BASE}/auth/logout`, { method: 'POST', headers: headers(false) })
  } catch {
    // best-effort: the caller clears the local session regardless
  }
}

async function changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/auth/change-password`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 204 || res.ok) return { status: 'ok' }
  return { status: 'error' }
}

export const operatorClient: OperatorClient = { login, me, logout, changePassword }
```

- [ ] **Step 5: Implement `i18n/locales/it.ts` and `i18n/index.ts`**

`src/i18n/locales/it.ts`:
```ts
export const it = {
  common: { loading: 'Caricamento…', comingSoon: 'in arrivo' },
  login: {
    title: 'Portale operatore',
    username: 'Nome utente',
    password: 'Password',
    submit: 'Entra',
  },
  changePassword: {
    title: 'Cambia la password',
    intro: 'Per continuare devi impostare una nuova password.',
    old: 'Password attuale',
    new: 'Nuova password',
    submit: 'Salva la nuova password',
  },
  home: { welcome: 'Benvenuto/a, {{name}}' },
  shell: {
    logout: 'Esci',
    role: { operator: 'Operatore', supervisor: 'Supervisore', admin: 'Amministratore', auditor: 'Auditor' },
  },
  nav: {
    jobRequests: 'Richieste di lavoro',
    profiles: 'Profili',
    export: 'Export',
    metrics: 'Metriche',
    activity: 'Attività operatori',
    operators: 'Gestione utenze',
    config: 'Configurazione',
    audit: 'Log di audit',
  },
  unauthorized: { text: 'Non hai i permessi per questa sezione.' },
  errors: {
    invalidCredentials: 'Credenziali non valide.',
    sessionExpired: 'Sessione scaduta. Accedi di nuovo.',
    generic: 'Si è verificato un errore. Riprova.',
  },
}
```
`src/i18n/index.ts`:
```ts
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { it } from './locales/it'

void i18n.use(initReactI18next).init({
  resources: { it: { translation: it } },
  lng: 'it',
  fallbackLng: 'it',
  interpolation: { escapeValue: false },
})

export default i18n
```

- [ ] **Step 6: Implement `test/fakeClient.ts`**

```ts
import type { ChangeResult, LoginResult, MeResult, Operator, OperatorClient, Role } from '../types'

export const OPERATOR: Operator = {
  id: 1,
  username: 'mrossi',
  display_name: 'M. Rossi',
  role: 'operator',
  is_active: true,
  must_change_password: false,
}

export function operatorWith(overrides: Partial<Operator> = {}): Operator {
  return { ...OPERATOR, ...overrides }
}

// Deterministic fake; each method returns its canned result and records calls.
export function makeFakeClient(opts: {
  login?: LoginResult
  me?: MeResult
  change?: ChangeResult
} = {}): OperatorClient & { calls: { login: number; me: number; logout: number; change: number } } {
  const calls = { login: 0, me: 0, logout: 0, change: 0 }
  return {
    calls,
    async login() {
      calls.login++
      return opts.login ?? { status: 'ok', token: 'tok', operator: OPERATOR, mustChangePassword: false }
    },
    async me() {
      calls.me++
      return opts.me ?? { status: 'unauthorized' }
    },
    async logout() {
      calls.logout++
    },
    async changePassword() {
      calls.change++
      return opts.change ?? { status: 'ok' }
    },
  }
}

export const ROLES: Role[] = ['operator', 'supervisor', 'admin', 'auditor']
```

- [ ] **Step 7: Run the tests and the gate**

Run: `npm test -- operatorClient i18n && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/types.ts operator-portal/src/api operator-portal/src/auth/session.ts operator-portal/src/i18n operator-portal/src/test/fakeClient.ts operator-portal/src/api/operatorClient.test.ts operator-portal/src/i18n/i18n.test.ts
git commit -m "feat(operator-portal): typed operatorClient (Bearer, fail-closed) + session + i18n"
```

---

## Task 3: `AuthProvider` / `useAuth` + test render helper

**Files:**
- Create: `src/auth/AuthContext.tsx`, `src/test/utils.tsx`
- Test: `src/auth/AuthContext.test.tsx`

**Interfaces:**
- Consumes: `operatorClient`/`OperatorClient` (Task 2), `session.ts` (Task 2), `Operator` (Task 2).
- Produces:
  - `interface AuthValue { operator: Operator | null; loading: boolean; mustChangePassword: boolean; login(u,p): Promise<LoginResult>; logout(): Promise<void>; changePassword(oldP,newP): Promise<ChangeResult>; clearMustChangePassword(): void; onUnauthorized(): void }`
  - `AuthProvider(props: { client?: OperatorClient; children: ReactNode })` — on mount, if a token exists in sessionStorage, validates via `client.me()`. `changePassword` delegates to `client.changePassword` (so the injected client drives it in tests).
  - `useAuth(): AuthValue`
  - `renderWithProviders(ui, opts?: { client?: OperatorClient; route?: string })` in `test/utils.tsx` (wraps `MemoryRouter` + `I18nextProvider` + `AuthProvider`)

- [ ] **Step 1: Write the failing test**

`src/auth/AuthContext.test.tsx`:
```tsx
import { render, screen, waitFor, act } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { setToken, getToken } from './session'

afterEach(() => sessionStorage.clear())

function Probe() {
  const { operator, loading, mustChangePassword, login, logout } = useAuth()
  return (
    <div>
      <span>loading:{String(loading)}</span>
      <span>op:{operator ? operator.username : 'none'}</span>
      <span>mcp:{String(mustChangePassword)}</span>
      <button onClick={() => void login('mrossi', 'pw')}>login</button>
      <button onClick={() => void logout()}>logout</button>
    </div>
  )
}

test('no token on mount → not loading, no operator (no me() call needed)', async () => {
  const client = makeFakeClient({})
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('loading:false')).toBeInTheDocument())
  expect(screen.getByText('op:none')).toBeInTheDocument()
  expect(client.calls.me).toBe(0)
})

test('existing token on mount → me() populates the operator', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ username: 'gverdi' }) } })
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('op:gverdi')).toBeInTheDocument())
  expect(client.calls.me).toBe(1)
})

test('me() 401 on mount → token cleared, no operator', async () => {
  setToken('stale')
  const client = makeFakeClient({ me: { status: 'unauthorized' } })
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('op:none')).toBeInTheDocument())
  expect(getToken()).toBeNull()
})

test('login ok saves token + operator; logout clears them', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'newtok', operator: operatorWith({ username: 'mrossi' }), mustChangePassword: false },
  })
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('loading:false')).toBeInTheDocument())
  await act(async () => {
    screen.getByText('login').click()
  })
  await waitFor(() => expect(screen.getByText('op:mrossi')).toBeInTheDocument())
  expect(getToken()).toBe('newtok')
  await act(async () => {
    screen.getByText('logout').click()
  })
  await waitFor(() => expect(screen.getByText('op:none')).toBeInTheDocument())
  expect(getToken()).toBeNull()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- AuthContext`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `AuthContext.tsx`**

```tsx
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { operatorClient } from '../api/operatorClient'
import { clearToken, getToken, setToken } from './session'
import type { ChangeResult, LoginResult, Operator, OperatorClient } from '../types'

interface AuthValue {
  operator: Operator | null
  loading: boolean
  mustChangePassword: boolean
  login(username: string, password: string): Promise<LoginResult>
  logout(): Promise<void>
  changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult>
  clearMustChangePassword(): void
  onUnauthorized(): void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ client = operatorClient, children }: { client?: OperatorClient; children: ReactNode }) {
  const [operator, setOperator] = useState<Operator | null>(null)
  const [mustChangePassword, setMcp] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    let active = true
    void client.me().then((r) => {
      if (!active) return
      if (r.status === 'ok') {
        setOperator(r.operator)
        setMcp(r.operator.must_change_password)
      } else {
        clearToken()
        setOperator(null)
      }
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [client])

  const login = useCallback(
    async (username: string, password: string): Promise<LoginResult> => {
      const r = await client.login(username, password)
      if (r.status === 'ok') {
        setToken(r.token)
        setOperator(r.operator)
        setMcp(r.mustChangePassword)
      }
      return r
    },
    [client],
  )

  const logout = useCallback(async () => {
    await client.logout()
    clearToken()
    setOperator(null)
    setMcp(false)
  }, [client])

  const changePassword = useCallback(
    (oldPassword: string, newPassword: string) => client.changePassword(oldPassword, newPassword),
    [client],
  )

  const clearMustChangePassword = useCallback(() => setMcp(false), [])
  const onUnauthorized = useCallback(() => {
    clearToken()
    setOperator(null)
    setMcp(false)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        operator,
        loading,
        mustChangePassword,
        login,
        logout,
        changePassword,
        clearMustChangePassword,
        onUnauthorized,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
```

- [ ] **Step 4: Implement `test/utils.tsx`**

```tsx
import { render, type RenderResult } from '@testing-library/react'
import { type ReactElement } from 'react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import i18n from '../i18n'
import { AuthProvider } from '../auth/AuthContext'
import { makeFakeClient } from './fakeClient'
import type { OperatorClient } from '../types'

export function renderWithProviders(
  ui: ReactElement,
  opts: { client?: OperatorClient; route?: string } = {},
): RenderResult {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[opts.route ?? '/']}>
        <AuthProvider client={opts.client ?? makeFakeClient({})}>{ui}</AuthProvider>
      </MemoryRouter>
    </I18nextProvider>,
  )
}
```

- [ ] **Step 5: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add operator-portal/src/auth/AuthContext.tsx operator-portal/src/auth/AuthContext.test.tsx operator-portal/src/test/utils.tsx
git commit -m "feat(operator-portal): AuthProvider (session bootstrap via /me) + test helper"
```

---

## Task 4: `Login` + `ChangePassword` screens

**Files:**
- Create: `src/screens/Login.tsx`, `src/screens/ChangePassword.tsx`
- Test: `src/screens/Login.test.tsx`, `src/screens/ChangePassword.test.tsx`

**Interfaces:**
- Consumes: `useAuth` (Task 3), `operatorClient.changePassword` (Task 2), react-router `useNavigate`/`Navigate`, i18n.
- Produces:
  - `Login()` — username/password form → `useAuth().login`; on `ok` navigates (`/change-password` if `mustChangePassword`, else `/`); on `invalid` shows `errors.invalidCredentials`; on `error` shows `errors.generic`. If already authenticated, redirects away.
  - `ChangePassword()` — old/new form → `changePassword`; on `ok` calls `clearMustChangePassword()` + navigates `/`; on `unauthorized` → `onUnauthorized()` + `/login`; on `error` shows `errors.generic`.

- [ ] **Step 1: Write the failing tests**

`src/screens/Login.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { Login } from './Login'

afterEach(() => sessionStorage.clear())

function LoginHarness() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<div>HOME</div>} />
      <Route path="/change-password" element={<div>CHANGE</div>} />
    </Routes>
  )
}

test('successful login navigates to home', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'tok', operator: operatorWith(), mustChangePassword: false },
  })
  renderWithProviders(<LoginHarness />, { client, route: '/login' })
  await userEvent.type(screen.getByLabelText('Nome utente'), 'mrossi')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  await waitFor(() => expect(screen.getByText('HOME')).toBeInTheDocument())
})

test('login with must_change_password navigates to change-password', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'tok', operator: operatorWith({ must_change_password: true }), mustChangePassword: true },
  })
  renderWithProviders(<LoginHarness />, { client, route: '/login' })
  await userEvent.type(screen.getByLabelText('Nome utente'), 'mrossi')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  await waitFor(() => expect(screen.getByText('CHANGE')).toBeInTheDocument())
})

test('invalid credentials show a generic message and do not navigate', async () => {
  const client = makeFakeClient({ login: { status: 'invalid' } })
  renderWithProviders(<LoginHarness />, { client, route: '/login' })
  await userEvent.type(screen.getByLabelText('Nome utente'), 'x')
  await userEvent.type(screen.getByLabelText('Password'), 'y')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  expect(await screen.findByText('Credenziali non valide.')).toBeInTheDocument()
  expect(screen.queryByText('HOME')).not.toBeInTheDocument()
})
```

`src/screens/ChangePassword.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient } from '../test/fakeClient'
import { ChangePassword } from './ChangePassword'

afterEach(() => sessionStorage.clear())

function Harness() {
  return (
    <Routes>
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/" element={<div>HOME</div>} />
    </Routes>
  )
}

test('successful change navigates home', async () => {
  const client = makeFakeClient({ change: { status: 'ok' } })
  renderWithProviders(<Harness />, { client, route: '/change-password' })
  await userEvent.type(screen.getByLabelText('Password attuale'), 'oldpw')
  await userEvent.type(screen.getByLabelText('Nuova password'), 'newpassword')
  await userEvent.click(screen.getByRole('button', { name: 'Salva la nuova password' }))
  await waitFor(() => expect(screen.getByText('HOME')).toBeInTheDocument())
})

test('error shows a message and stays on the form', async () => {
  const client = makeFakeClient({ change: { status: 'error' } })
  renderWithProviders(<Harness />, { client, route: '/change-password' })
  await userEvent.type(screen.getByLabelText('Password attuale'), 'oldpw')
  await userEvent.type(screen.getByLabelText('Nuova password'), 'x')
  await userEvent.click(screen.getByRole('button', { name: 'Salva la nuova password' }))
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- screens/Login screens/ChangePassword`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement `Login.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function Login() {
  const { t } = useTranslation()
  const { operator, mustChangePassword, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (operator) return <Navigate to={mustChangePassword ? '/change-password' : '/'} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    const r = await login(username, password)
    setBusy(false)
    if (r.status === 'ok') navigate(r.mustChangePassword ? '/change-password' : '/', { replace: true })
    else if (r.status === 'invalid') setError(t('errors.invalidCredentials'))
    else setError(t('errors.generic'))
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <h1>{t('login.title')}</h1>
      <label>
        {t('login.username')}
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
      </label>
      <label>
        {t('login.password')}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || !username || !password}>
        {t('login.submit')}
      </button>
    </form>
  )
}
```
Note: the `<label>{text}<input/></label>` wrapping makes `getByLabelText` resolve the input by its label text.

- [ ] **Step 4: Implement `ChangePassword.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function ChangePassword() {
  const { t } = useTranslation()
  const { changePassword, clearMustChangePassword, onUnauthorized } = useAuth()
  const navigate = useNavigate()
  const [oldPassword, setOld] = useState('')
  const [newPassword, setNew] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    const r = await changePassword(oldPassword, newPassword)
    setBusy(false)
    if (r.status === 'ok') {
      clearMustChangePassword()
      navigate('/', { replace: true })
    } else if (r.status === 'unauthorized') {
      onUnauthorized()
      navigate('/login', { replace: true })
    } else {
      setError(t('errors.generic'))
    }
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <h1>{t('changePassword.title')}</h1>
      <p>{t('changePassword.intro')}</p>
      <label>
        {t('changePassword.old')}
        <input type="password" value={oldPassword} onChange={(e) => setOld(e.target.value)} autoComplete="current-password" />
      </label>
      <label>
        {t('changePassword.new')}
        <input type="password" value={newPassword} onChange={(e) => setNew(e.target.value)} autoComplete="new-password" />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || !oldPassword || !newPassword}>
        {t('changePassword.submit')}
      </button>
    </form>
  )
}
```
Note: `ChangePassword` calls `useAuth().changePassword` (which delegates to the injected client, added in Task 3) — NOT `operatorClient` directly — so the fake client drives the result in tests.

- [ ] **Step 5: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add operator-portal/src/screens/Login.tsx operator-portal/src/screens/ChangePassword.tsx operator-portal/src/screens/Login.test.tsx operator-portal/src/screens/ChangePassword.test.tsx
git commit -m "feat(operator-portal): login + forced change-password screens"
```

---

## Task 5: `ProtectedRoute` + RBAC nav + `AppShell`/`Nav` + `Home`/`Unauthorized`

**Files:**
- Create: `src/auth/ProtectedRoute.tsx`, `src/rbac/nav.ts`, `src/shell/AppShell.tsx`, `src/shell/Nav.tsx`, `src/screens/Home.tsx`, `src/screens/Unauthorized.tsx`
- Modify: `src/styles/theme.css` (shell/form styles)
- Test: `src/auth/ProtectedRoute.test.tsx`, `src/shell/Nav.test.tsx`

**Interfaces:**
- Consumes: `useAuth` (Task 3), `Role` (Task 2), react-router (`Navigate`, `Outlet`, `Link`, `useLocation`), i18n.
- Produces:
  - `ProtectedRoute(props: { children: ReactNode; allowMustChange?: boolean })` — loading → spinner; `!operator` → `<Navigate to="/login">`; `mustChangePassword && !allowMustChange` → `<Navigate to="/change-password">`; else children.
  - `NAV_BY_ROLE: Record<Role, { path: string; labelKey: string }[]>`
  - `AppShell()` — header (operator name + role + logout) + `<Nav>` + `<Outlet/>`
  - `Nav()` — role-appropriate items as DISABLED placeholders ("in arrivo")
  - `Home()` — `home.welcome` with the operator's display_name
  - `Unauthorized()` — `unauthorized.text`

- [ ] **Step 1: Write the failing tests**

`src/auth/ProtectedRoute.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { ProtectedRoute } from './ProtectedRoute'
import { setToken } from './session'

afterEach(() => sessionStorage.clear())

function Harness() {
  return (
    <Routes>
      <Route path="/login" element={<div>LOGIN</div>} />
      <Route path="/change-password" element={<div>CHANGE</div>} />
      <Route path="/" element={<ProtectedRoute><div>PROTECTED</div></ProtectedRoute>} />
    </Routes>
  )
}

test('no operator → redirected to login', async () => {
  renderWithProviders(<Harness />, { client: makeFakeClient({ me: { status: 'unauthorized' } }), route: '/' })
  await waitFor(() => expect(screen.getByText('LOGIN')).toBeInTheDocument())
})

test('authenticated, no gate → renders the protected content', async () => {
  setToken('tok')
  renderWithProviders(<Harness />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ must_change_password: false }) } }),
    route: '/',
  })
  await waitFor(() => expect(screen.getByText('PROTECTED')).toBeInTheDocument())
})

test('must_change_password → redirected to change-password (gate not bypassable)', async () => {
  setToken('tok')
  renderWithProviders(<Harness />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ must_change_password: true }) } }),
    route: '/',
  })
  await waitFor(() => expect(screen.getByText('CHANGE')).toBeInTheDocument())
  expect(screen.queryByText('PROTECTED')).not.toBeInTheDocument()
})
```

`src/shell/Nav.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { setToken } from '../auth/session'
import { Nav } from './Nav'

afterEach(() => sessionStorage.clear())

test('operator sees operator sections, not admin ones', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } }),
  })
  await waitFor(() => expect(screen.getByText('Richieste di lavoro')).toBeInTheDocument())
  expect(screen.getByText('Profili')).toBeInTheDocument()
  expect(screen.queryByText('Gestione utenze')).not.toBeInTheDocument()
})

test('admin sees admin sections', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } }),
  })
  await waitFor(() => expect(screen.getByText('Gestione utenze')).toBeInTheDocument())
  expect(screen.queryByText('Richieste di lavoro')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- ProtectedRoute Nav`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement `rbac/nav.ts`**

```ts
import type { Role } from '../types'

export interface NavItem {
  path: string
  labelKey: string
}

// UX-only nav skeleton (§6). The server remains the authority (403). Section
// pages arrive in later sub-projects; here the items render as disabled
// placeholders.
export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  operator: [
    { path: '/job-requests', labelKey: 'nav.jobRequests' },
    { path: '/profiles', labelKey: 'nav.profiles' },
    { path: '/export', labelKey: 'nav.export' },
  ],
  supervisor: [
    { path: '/metrics', labelKey: 'nav.metrics' },
    { path: '/activity', labelKey: 'nav.activity' },
  ],
  admin: [
    { path: '/operators', labelKey: 'nav.operators' },
    { path: '/config', labelKey: 'nav.config' },
  ],
  auditor: [{ path: '/audit', labelKey: 'nav.audit' }],
}
```

- [ ] **Step 4: Implement `ProtectedRoute.tsx`**

```tsx
import { type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function ProtectedRoute({ children, allowMustChange = false }: { children: ReactNode; allowMustChange?: boolean }) {
  const { t } = useTranslation()
  const { operator, loading, mustChangePassword } = useAuth()
  if (loading) return <p>{t('common.loading')}</p>
  if (!operator) return <Navigate to="/login" replace />
  if (mustChangePassword && !allowMustChange) return <Navigate to="/change-password" replace />
  return <>{children}</>
}
```

- [ ] **Step 5: Implement `Nav.tsx`, `AppShell.tsx`, `Home.tsx`, `Unauthorized.tsx`**

`src/shell/Nav.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import { NAV_BY_ROLE } from '../rbac/nav'

export function Nav() {
  const { t } = useTranslation()
  const { operator } = useAuth()
  if (!operator) return null
  const items = NAV_BY_ROLE[operator.role]
  return (
    <nav className="nav" aria-label="Sezioni">
      <ul>
        {items.map((item) => (
          <li key={item.path}>
            {/* disabled placeholder — the section arrives in a later sub-project */}
            <span className="nav-item disabled" aria-disabled="true">
              {t(item.labelKey)} <em className="coming">({t('common.comingSoon')})</em>
            </span>
          </li>
        ))}
      </ul>
    </nav>
  )
}
```
`src/shell/AppShell.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Nav } from './Nav'

export function AppShell() {
  const { t } = useTranslation()
  const { operator, logout } = useAuth()
  return (
    <div className="shell">
      <header className="shell-header">
        <span className="brand">Bussola</span>
        {operator && (
          <span className="who">
            {operator.display_name} · {t(`shell.role.${operator.role}`)}
          </span>
        )}
        <button className="logout" onClick={() => void logout()}>
          {t('shell.logout')}
        </button>
      </header>
      <div className="shell-body">
        <Nav />
        <main className="shell-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```
`src/screens/Home.tsx`:
```tsx
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'

export function Home() {
  const { t } = useTranslation()
  const { operator } = useAuth()
  return <h1>{t('home.welcome', { name: operator?.display_name ?? '' })}</h1>
}
```
`src/screens/Unauthorized.tsx`:
```tsx
import { useTranslation } from 'react-i18next'

export function Unauthorized() {
  const { t } = useTranslation()
  return <p role="alert">{t('unauthorized.text')}</p>
}
```

- [ ] **Step 6: Extend `theme.css`** (append)

```css
.auth-form { max-width: 360px; margin: 10vh auto; display: flex; flex-direction: column; gap: 12px; padding: 24px; }
.auth-form label { display: flex; flex-direction: column; gap: 4px; font-weight: 600; }
.auth-form input { padding: 10px; border: 1px solid var(--border); border-radius: 8px; font: inherit; }
.auth-form button { padding: 12px; border: 0; border-radius: 8px; background: var(--accent); color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
.auth-form button:disabled { opacity: 0.5; cursor: not-allowed; }
.error { color: var(--danger); font-weight: 600; }
.shell-header { display: flex; align-items: center; gap: 16px; padding: 12px 20px; border-bottom: 1px solid var(--border); }
.shell-header .who { margin-left: auto; color: var(--muted); }
.shell-header .logout { border: 1px solid var(--border); background: #fff; border-radius: 8px; padding: 8px 14px; font: inherit; cursor: pointer; }
.shell-body { display: flex; }
.nav { min-width: 220px; border-right: 1px solid var(--border); padding: 16px; }
.nav ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.nav-item.disabled { color: var(--muted); }
.nav-item .coming { font-size: 0.85em; }
.shell-main { flex: 1; padding: 24px; }
```

- [ ] **Step 7: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add operator-portal/src/auth/ProtectedRoute.tsx operator-portal/src/auth/ProtectedRoute.test.tsx operator-portal/src/rbac operator-portal/src/shell operator-portal/src/screens/Home.tsx operator-portal/src/screens/Unauthorized.tsx operator-portal/src/styles/theme.css
git commit -m "feat(operator-portal): protected routes + RBAC nav shell + home/unauthorized"
```

---

## Task 6: App composition + routing + full-flow tests

**Files:**
- Modify (replace placeholders): `src/App.tsx`, `src/main.tsx`
- Test: `src/App.test.tsx` (replace the Task 1 smoke test)

**Interfaces:**
- Consumes: all screens/shell/guards/AuthProvider; react-router `Routes`/`Route`/`Navigate`.
- Produces: `App()` — the route table; `main.tsx` wraps `<App/>` in `BrowserRouter` + `I18nextProvider` + `AuthProvider`.

- [ ] **Step 1: Write the failing test**

`src/App.test.tsx` (replaces the Task 1 smoke test):
```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import i18n from './i18n'
import { AuthProvider } from './auth/AuthContext'
import { App } from './App'
import { makeFakeClient, operatorWith } from './test/fakeClient'
import { setToken } from './auth/session'
import type { OperatorClient } from './types'

afterEach(() => sessionStorage.clear())

function renderApp(client: OperatorClient, route = '/') {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider client={client}>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </I18nextProvider>,
  )
}

test('unauthenticated visit to / lands on login', async () => {
  renderApp(makeFakeClient({ me: { status: 'unauthorized' } }), '/')
  expect(await screen.findByRole('button', { name: 'Entra' })).toBeInTheDocument()
})

test('happy path: login → shell home with the operator name', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'tok', operator: operatorWith({ display_name: 'M. Rossi' }), mustChangePassword: false },
  })
  renderApp(client, '/login')
  await userEvent.type(screen.getByLabelText('Nome utente'), 'mrossi')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  expect(await screen.findByText('Benvenuto/a, M. Rossi')).toBeInTheDocument()
})

test('must_change_password gate: login forces the change screen, home not reachable', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'tok', operator: operatorWith({ must_change_password: true }), mustChangePassword: true },
  })
  renderApp(client, '/login')
  await userEvent.type(screen.getByLabelText('Nome utente'), 'mrossi')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  expect(await screen.findByRole('button', { name: 'Salva la nuova password' })).toBeInTheDocument()
  expect(screen.queryByText(/Benvenuto/)).not.toBeInTheDocument()
})

test('logout returns to login', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  renderApp(client, '/')
  await userEvent.click(await screen.findByRole('button', { name: 'Esci' }))
  expect(await screen.findByRole('button', { name: 'Entra' })).toBeInTheDocument()
})

test('deep link to a protected route while unauthenticated → login', async () => {
  renderApp(makeFakeClient({ me: { status: 'unauthorized' } }), '/')
  expect(await screen.findByRole('button', { name: 'Entra' })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- App`
Expected: FAIL (App is still the placeholder).

- [ ] **Step 3: Implement `App.tsx`**

```tsx
import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppShell } from './shell/AppShell'
import { Login } from './screens/Login'
import { ChangePassword } from './screens/ChangePassword'
import { Home } from './screens/Home'
import { Unauthorized } from './screens/Unauthorized'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/change-password"
        element={
          <ProtectedRoute allowMustChange>
            <ChangePassword />
          </ProtectedRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Home />} />
        <Route path="unauthorized" element={<Unauthorized />} />
        {/* later sub-projects add nested section routes here */}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
```

- [ ] **Step 4: Replace `main.tsx`** with the real providers

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import { App } from './App'
import i18n from './i18n'
import { AuthProvider } from './auth/AuthContext'
import './styles/theme.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nextProvider i18n={i18n}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </I18nextProvider>
  </StrictMode>,
)
```

- [ ] **Step 5: Run the full suite and the gate**

Run: `npm test && npm run typecheck && npm run lint && npm run build`
Expected: all PASS / exit 0; output pristine.

- [ ] **Step 6: Commit**

```bash
git add operator-portal/src/App.tsx operator-portal/src/main.tsx operator-portal/src/App.test.tsx
git commit -m "feat(operator-portal): compose routes + providers (login→gate→shell→logout)"
```

---

## After all tasks

- Update `STATO_TECNICO.md`: the `operator-portal/` app (Vite+React+TS+react-router+react-i18next), the `operatorClient` (Bearer), sessionStorage, the must-change-password gate (closes the S5 follow-up), the RBAC shell, the dev port 5174/proxy; revise the §10 layout note (portal as a sibling app); record the operator-portal decomposition roadmap (sub-projects 2–5). Note follow-ups: a global 401→logout interceptor for the feature sub-projects (the `onUnauthorized` hook exists); wrong-old-password UX in change-password (currently generic error).
- Run the final whole-branch review (opus), then `superpowers:finishing-a-development-branch`.
```
