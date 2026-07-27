# Amministrazione utenze (portale operatore) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere al portale operatore la sezione **Amministrazione utenze** (§6 Amministratore): elenco operatori, creazione (con password temporanea una-tantum), disabilita/riabilita e reset-password — con conferme e guardia anti-auto-lockout.

**Architecture:** App React separata `operator-portal/` (scheletro S11, pattern S12/S13). Consuma l'API S5 `operators` (permesso `MANAGE_OPERATORS` → solo ruolo `admin`; il server resta l'autorità → 403). `operatorClient` esteso fail-closed col Bearer; `useApiError` per il 401; sezione coesa `/operators` sotto `ProtectedRoute`/`AppShell`. La password temporanea (credenziale restituita da create/reset) è mostrata in una modale una-tantum, mai persistita né loggata.

**Tech Stack:** React 18 + Vite 5 + TypeScript (strict) + react-i18next + react-router-dom. Test: Vitest + @testing-library/react + jsdom. **Nessuna nuova dipendenza.**

## Global Constraints

- **Estendere solo `operator-portal/`.** `frontend/` (kiosk) NON si tocca. Nessuna nuova dipendenza.
- **TDD** (RED → GREEN), **solo dati sintetici**. Output dei test **pristine** (nessun warning act()/router).
- **Client fail-closed**, mai un throw: Bearer via `headers()`; `401→'unauthorized'`, `403→'forbidden'`, `404` dove previsto, rete/5xx/JSON-invalido → `'error'`.
- **Degrado UI**: `401`→`useApiError` (`onUnauthorized()` + `/login`); `403`→`t('errors.forbidden')`; rete/5xx→`t('errors.generic')` (ritentabile).
- **Il server resta l'autorità (RBAC).** Le rotte sono solo **auth-gated** (`ProtectedRoute`); l'RBAC è imposto dal server (403). La nav mostra la voce solo all'admin.
- **temp_password = credenziale**: vive solo nello stato del componente finché la modale è aperta, **azzerata alla chiusura**, **mai** salvata in storage né passata a `console`/log.
- **i18n**: ogni stringa rivolta all'utente via `t(...)`. Le **etichette dei ruoli** riusano `shell.role.<role>` (già esistenti). Codice in inglese.
- **Guardia anti-auto-lockout**: sulla riga dell'admin loggato (`useAuth().operator.id === op.id`), «Disabilita» e «Reset password» sono `disabled` con `title` esplicativo. È difesa-in-profondità UX; la sicurezza vive lato server.
- **Contratto S5** (verificato): `GET /operators`→`Operator[]`; `POST /operators`→**201** `{operator, temp_password}`; `POST /operators/{id}/disable`→**204**; `POST /operators/{id}/enable`→**204**; `POST /operators/{id}/reset-password`→**200** `{temp_password}`. `Operator = {id, username, display_name, role, is_active, must_change_password}`.
- **Gate di qualità** (da `operator-portal/`): `npm test && npm run typecheck && npm run lint && npm run build` — tutto verde.

---

### Task 1: Client `operators` + tipi + i18n + fake

**Files:**
- Modify: `operator-portal/src/types.ts` (append)
- Modify: `operator-portal/src/api/operatorClient.ts` (aggiungi 5 metodi + export)
- Modify: `operator-portal/src/test/fakeClient.ts` (fixtures + opts + counters + metodi)
- Modify: `operator-portal/src/i18n/locales/it.ts` (nuovo gruppo `operators`)
- Test: `operator-portal/src/api/operatorClient.test.ts` (append)

**Interfaces:**
- Consumes: `Operator`, `Role` (già in `types.ts`); `headers(json)`, `BASE`, `getToken` (già in `operatorClient.ts`); pattern del fake S13.
- Produces (usati da Task 2–4):
  - `types.ts`: `CreateOperatorRequest {username, display_name, role}`, `CreatedOperator {operator, temp_password}`, `ResetResponse {temp_password}`, e le union `ListOperatorsResult` (`ok{operators}`), `CreateOperatorResult` (`ok{created:CreatedOperator}`), `MutateOperatorResult` (`ok`), `ResetPasswordResult` (`ok{temp_password}`) — tutte con `unauthorized|forbidden|error`.
  - `OperatorClient`: `listOperators()`, `createOperator(body)`, `disableOperator(id)`, `enableOperator(id)`, `resetPassword(id)`.
  - `fakeClient.ts`: fixtures `ADMIN`, `OPERATORS`; `makeFakeClient` accetta `operators/createOp/disable/enable/reset`, espone counters `lops/opcreate/opdisable/openable/opreset` e array `createdOperators/disabledIds/enabledIds/resetIds`.
  - i18n: gruppo `operators.*` (chiavi elencate sotto).

- [ ] **Step 1: Scrivi i test del client (append a `operatorClient.test.ts`)**

Aggiungi in coda al file (riusa l'helper `res()` e `setToken` già presenti):

```ts
const OPS = [
  { id: 1, username: 'm.rossi', display_name: 'Maria Rossi', role: 'operator', is_active: true, must_change_password: false },
  { id: 3, username: 'a.verdi', display_name: 'Aldo Verdi', role: 'operator', is_active: false, must_change_password: false },
]

test('listOperators: 200→ok with Bearer; 401→unauthorized; 403→forbidden', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, OPS))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.listOperators()).toEqual({ status: 'ok', operators: OPS })
  expect(String(f.mock.calls[0][0])).toMatch(/\/operators$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.listOperators()).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.listOperators()).toEqual({ status: 'forbidden' })
})

test('createOperator: POSTs the body, maps 201→ok{created}', async () => {
  setToken('tok')
  const created = { operator: OPS[0], temp_password: '7Kq9-mZ2t-Rf4x' }
  const f = vi.fn().mockResolvedValue(res(201, created))
  vi.stubGlobal('fetch', f)
  const body = { username: 'm.rossi', display_name: 'Maria Rossi', role: 'operator' as const }
  expect(await operatorClient.createOperator(body)).toEqual({ status: 'ok', created })
  const [url, init] = f.mock.calls[0]
  expect(String(url)).toMatch(/\/operators$/)
  expect((init as RequestInit).method).toBe('POST')
  expect(JSON.parse((init as RequestInit).body as string)).toEqual(body)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.createOperator(body)).toEqual({ status: 'forbidden' })
})

test('disableOperator/enableOperator: POST to the right path, 204→ok', async () => {
  setToken('tok')
  const fd = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', fd)
  expect(await operatorClient.disableOperator(3)).toEqual({ status: 'ok' })
  expect(String(fd.mock.calls[0][0])).toMatch(/\/operators\/3\/disable$/)
  expect((fd.mock.calls[0][1] as RequestInit).method).toBe('POST')
  const fe = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', fe)
  expect(await operatorClient.enableOperator(3)).toEqual({ status: 'ok' })
  expect(String(fe.mock.calls[0][0])).toMatch(/\/operators\/3\/enable$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.disableOperator(3)).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.enableOperator(3)).toEqual({ status: 'error' })
})

test('resetPassword: 200→ok{temp_password}; 403→forbidden', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, { temp_password: 'NEW-pw-123' }))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.resetPassword(1)).toEqual({ status: 'ok', temp_password: 'NEW-pw-123' })
  expect(String(f.mock.calls[0][0])).toMatch(/\/operators\/1\/reset-password$/)
  expect((f.mock.calls[0][1] as RequestInit).method).toBe('POST')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.resetPassword(1)).toEqual({ status: 'forbidden' })
})
```

- [ ] **Step 2: Esegui i test — devono fallire**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: FAIL (`listOperators`/`createOperator`/… non esistono su `operatorClient`; errori di tipo).

- [ ] **Step 3: Aggiungi i tipi (`types.ts`)**

Append in fondo a `operator-portal/src/types.ts` (NON ridichiarare `Operator`/`Role`):

```ts
export interface CreateOperatorRequest {
  username: string
  display_name: string
  role: Role
}
export interface CreatedOperator {
  operator: Operator
  temp_password: string
}
export interface ResetResponse {
  temp_password: string
}
export type ListOperatorsResult =
  | { status: 'ok'; operators: Operator[] }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type CreateOperatorResult =
  | { status: 'ok'; created: CreatedOperator }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type MutateOperatorResult =
  | { status: 'ok' }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type ResetPasswordResult =
  | { status: 'ok'; temp_password: string }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
```

Estendi l'interfaccia `OperatorClient` (aggiungi le 5 firme dopo `getProfile`):

```ts
  listOperators(): Promise<ListOperatorsResult>
  createOperator(body: CreateOperatorRequest): Promise<CreateOperatorResult>
  disableOperator(id: number): Promise<MutateOperatorResult>
  enableOperator(id: number): Promise<MutateOperatorResult>
  resetPassword(id: number): Promise<ResetPasswordResult>
```

- [ ] **Step 4: Implementa i 5 metodi (`operatorClient.ts`)**

Aggiungi ai tipi importati in cima: `CreateOperatorRequest, CreatedOperator, CreateOperatorResult, ListOperatorsResult, MutateOperatorResult, ResetPasswordResult, ResetResponse`. Poi, prima dell'export `operatorClient`, aggiungi:

```ts
async function listOperators(): Promise<ListOperatorsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operators`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', operators: (await res.json()) as Operator[] }
  } catch {
    return { status: 'error' }
  }
}

async function createOperator(body: CreateOperatorRequest): Promise<CreateOperatorResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operators`, { method: 'POST', headers: headers(true), body: JSON.stringify(body) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', created: (await res.json()) as CreatedOperator }
  } catch {
    return { status: 'error' }
  }
}

async function mutateOperator(id: number, action: 'disable' | 'enable'): Promise<MutateOperatorResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operators/${id}/${action}`, { method: 'POST', headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 204 || res.ok) return { status: 'ok' }
  return { status: 'error' }
}

function disableOperator(id: number): Promise<MutateOperatorResult> {
  return mutateOperator(id, 'disable')
}

function enableOperator(id: number): Promise<MutateOperatorResult> {
  return mutateOperator(id, 'enable')
}

async function resetPassword(id: number): Promise<ResetPasswordResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operators/${id}/reset-password`, { method: 'POST', headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', temp_password: ((await res.json()) as ResetResponse).temp_password }
  } catch {
    return { status: 'error' }
  }
}
```

Aggiungi al literal `export const operatorClient` le 5 proprietà: `listOperators, createOperator, disableOperator, enableOperator, resetPassword`.

- [ ] **Step 5: Esegui i test del client — devono passare**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: PASS.

- [ ] **Step 6: Estendi il fake (`test/fakeClient.ts`)**

Aggiungi i tipi importati: `CreateOperatorRequest, CreateOperatorResult, ListOperatorsResult, MutateOperatorResult, ResetPasswordResult`. Aggiungi le fixtures (dopo `operatorWith`):

```ts
export const ADMIN: Operator = {
  id: 9, username: 'admin', display_name: 'Amministratore', role: 'admin', is_active: true, must_change_password: false,
}
export const OPERATORS: Operator[] = [
  { id: 1, username: 'm.rossi', display_name: 'Maria Rossi', role: 'operator', is_active: true, must_change_password: false },
  { id: 2, username: 'g.bianchi', display_name: 'Giulia Bianchi', role: 'supervisor', is_active: true, must_change_password: true },
  { id: 3, username: 'a.verdi', display_name: 'Aldo Verdi', role: 'operator', is_active: false, must_change_password: false },
]
```

Estendi la firma `opts` di `makeFakeClient` con:
```ts
  operators?: ListOperatorsResult
  createOp?: CreateOperatorResult
  disable?: MutateOperatorResult
  enable?: MutateOperatorResult
  reset?: ResetPasswordResult
```
Estendi il tipo di ritorno: nei `calls` aggiungi `lops: number; opcreate: number; opdisable: number; openable: number; opreset: number`; aggiungi gli array `createdOperators: CreateOperatorRequest[]; disabledIds: number[]; enabledIds: number[]; resetIds: number[]`.
Inizializza: `const calls = { ...esistenti, lops: 0, opcreate: 0, opdisable: 0, openable: 0, opreset: 0 }` e i 4 array; includili nel return. Aggiungi i metodi:

```ts
    async listOperators() {
      calls.lops++
      return opts.operators ?? { status: 'ok', operators: OPERATORS }
    },
    async createOperator(body) {
      calls.opcreate++
      createdOperators.push(body)
      return opts.createOp ?? { status: 'ok', created: { operator: { id: 10, ...body, is_active: true, must_change_password: true }, temp_password: '7Kq9-mZ2t-Rf4x' } }
    },
    async disableOperator(id) {
      calls.opdisable++
      disabledIds.push(id)
      return opts.disable ?? { status: 'ok' }
    },
    async enableOperator(id) {
      calls.openable++
      enabledIds.push(id)
      return opts.enable ?? { status: 'ok' }
    },
    async resetPassword(id) {
      calls.opreset++
      resetIds.push(id)
      return opts.reset ?? { status: 'ok', temp_password: 'NEW-pw-123' }
    },
```

- [ ] **Step 7: Aggiungi le stringhe i18n (`i18n/locales/it.ts`)**

Aggiungi un nuovo gruppo `operators` all'oggetto `it` (dopo `pl`):

```ts
  operators: {
    title: 'Gestione utenze',
    new: 'Nuovo operatore',
    createTitle: 'Nuovo operatore',
    username: 'Nome utente',
    displayName: 'Nome visualizzato',
    role: 'Ruolo',
    rolePlaceholder: '— seleziona —',
    create: 'Crea operatore',
    cancel: 'Annulla',
    empty: 'Nessun operatore.',
    colUsername: 'Utente',
    colName: 'Nome',
    colRole: 'Ruolo',
    colStatus: 'Stato',
    colActions: 'Azioni',
    active: 'Attivo',
    disabled: 'Disattivo',
    mustChange: 'Deve cambiare password',
    disable: 'Disabilita',
    enable: 'Riabilita',
    resetPassword: 'Reset password',
    selfActionBlocked: 'Non puoi agire sul tuo account',
    confirm: 'Conferma',
    confirmDisable: 'Disabilitare l’operatore «{{name}}»? Verrà disconnesso subito.',
    confirmEnable: 'Riabilitare l’operatore «{{name}}»?',
    confirmReset: 'Reimpostare la password di «{{name}}»? Verrà disconnesso e dovrà impostarne una nuova.',
    tempPasswordTitle: 'Password temporanea',
    tempPasswordWarning: 'Mostrata una sola volta. Consegnala ora all’operatore: non sarà più visibile.',
    createdSubtitle: 'Operatore «{{name}}» creato.',
    resetSubtitle: 'Password reimpostata per «{{name}}».',
    copy: 'Copia',
    copied: 'Copiato',
    close: 'Ho copiato, chiudi',
  },
```

- [ ] **Step 8: Gate completo**

Run: `cd operator-portal && npm test && npm run typecheck && npm run lint`
Expected: tutto verde, pristine.

- [ ] **Step 9: Commit**

```bash
git add operator-portal/src/types.ts operator-portal/src/api/operatorClient.ts operator-portal/src/api/operatorClient.test.ts operator-portal/src/test/fakeClient.ts operator-portal/src/i18n/locales/it.ts
git commit -m "feat(operator-portal): operators client (list/create/disable/enable/reset) + types + i18n"
```

---

### Task 2: Componenti presentazionali — `TempPasswordModal` + `ConfirmDialog`

**Files:**
- Create: `operator-portal/src/screens/operators/TempPasswordModal.tsx`
- Create: `operator-portal/src/screens/operators/TempPasswordModal.test.tsx`
- Create: `operator-portal/src/screens/operators/ConfirmDialog.tsx`
- Create: `operator-portal/src/screens/operators/ConfirmDialog.test.tsx`
- Modify: `operator-portal/src/styles/theme.css` (classi modale)

**Interfaces:**
- Consumes: i18n `operators.*` (Task 1); `renderWithProviders` (`test/utils`).
- Produces (usati da Task 3):
  - `TempPasswordModal({ password: string, subtitle: string, onClose: () => void, copy?: (text: string) => Promise<void> })` — modale una-tantum; il copy default usa `navigator.clipboard` in modo sicuro (no throw se assente).
  - `ConfirmDialog({ message: string, confirmLabel: string, onConfirm: () => void, onCancel: () => void })`.

- [ ] **Step 1: Scrivi i test dei due componenti**

`TempPasswordModal.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { TempPasswordModal } from './TempPasswordModal'

test('shows the password + warning, copy calls the seam, close fires onClose', async () => {
  const copy = vi.fn().mockResolvedValue(undefined)
  const onClose = vi.fn()
  renderWithProviders(<TempPasswordModal password="7Kq9-mZ2t-Rf4x" subtitle="Operatore «x» creato." onClose={onClose} copy={copy} />)
  expect(screen.getByText('7Kq9-mZ2t-Rf4x')).toBeInTheDocument()
  expect(screen.getByText(/Mostrata una sola volta/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Copia' }))
  expect(copy).toHaveBeenCalledWith('7Kq9-mZ2t-Rf4x')
  expect(await screen.findByRole('button', { name: 'Copiato' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Ho copiato, chiudi' }))
  expect(onClose).toHaveBeenCalledOnce()
})
```

`ConfirmDialog.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { ConfirmDialog } from './ConfirmDialog'

test('confirm and cancel fire the right callbacks', async () => {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  renderWithProviders(<ConfirmDialog message="Disabilitare «x»?" confirmLabel="Conferma" onConfirm={onConfirm} onCancel={onCancel} />)
  expect(screen.getByText('Disabilitare «x»?')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Annulla' }))
  expect(onCancel).toHaveBeenCalledOnce()
  await userEvent.click(screen.getByRole('button', { name: 'Conferma' }))
  expect(onConfirm).toHaveBeenCalledOnce()
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/screens/operators/TempPasswordModal.test.tsx src/screens/operators/ConfirmDialog.test.tsx`
Expected: FAIL (moduli inesistenti).

- [ ] **Step 3: Implementa `TempPasswordModal.tsx`**

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

function defaultCopy(text: string): Promise<void> {
  return navigator.clipboard?.writeText(text) ?? Promise.resolve()
}

export function TempPasswordModal({
  password,
  subtitle,
  onClose,
  copy = defaultCopy,
}: {
  password: string
  subtitle: string
  onClose: () => void
  copy?: (text: string) => Promise<void>
}) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  async function doCopy() {
    await copy(password)
    setCopied(true)
  }
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={t('operators.tempPasswordTitle')}>
      <div className="modal">
        <h2>{t('operators.tempPasswordTitle')}</h2>
        <p className="modal-sub">{subtitle}</p>
        <p className="warn" role="alert">{t('operators.tempPasswordWarning')}</p>
        <div className="pw-row">
          <code className="pw">{password}</code>
          <button type="button" onClick={doCopy}>{copied ? t('operators.copied') : t('operators.copy')}</button>
        </div>
        <div className="modal-actions">
          <button type="button" className="primary" onClick={onClose}>{t('operators.close')}</button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Implementa `ConfirmDialog.tsx`**

```tsx
import { useTranslation } from 'react-i18next'

export function ConfirmDialog({
  message,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  message: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <p>{message}</p>
        <div className="modal-actions">
          <button type="button" onClick={onCancel}>{t('operators.cancel')}</button>
          <button type="button" className="primary" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Aggiungi le classi CSS (`styles/theme.css`)**

Append in fondo:
```css
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 100; }
.modal { background: var(--bg, #fff); color: var(--fg, #111); border-radius: 12px; padding: 18px; width: 100%; max-width: 420px; box-shadow: 0 10px 30px rgba(0,0,0,.25); }
.modal h2 { margin: 0 0 4px; font-size: 16px; }
.modal-sub { margin: 0 0 8px; color: var(--muted); }
.modal .warn { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; border-radius: 8px; padding: 6px 8px; font-size: 13px; }
.pw-row { display: flex; gap: 8px; align-items: center; margin: 10px 0; }
.pw { flex: 1; background: #f3f4f6; color: #111; border-radius: 6px; padding: 8px; font-size: 15px; letter-spacing: .5px; word-break: break-all; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
.modal-actions .primary { background: var(--accent); color: #fff; border: 0; border-radius: 8px; padding: 8px 14px; font: inherit; font-weight: 700; cursor: pointer; }
```

- [ ] **Step 6: Esegui i test — devono passare, poi gate**

Run: `cd operator-portal && npx vitest run src/screens/operators/ && npm run typecheck && npm run lint`
Expected: PASS, pristine.

- [ ] **Step 7: Commit**

```bash
git add operator-portal/src/screens/operators/TempPasswordModal.tsx operator-portal/src/screens/operators/TempPasswordModal.test.tsx operator-portal/src/screens/operators/ConfirmDialog.tsx operator-portal/src/screens/operators/ConfirmDialog.test.tsx operator-portal/src/styles/theme.css
git commit -m "feat(operator-portal): temp-password modal (one-time) + confirm dialog"
```

---

### Task 3: `OperatorList` + `CreateOperatorForm` (schermata orchestratrice)

**Files:**
- Create: `operator-portal/src/screens/operators/CreateOperatorForm.tsx`
- Create: `operator-portal/src/screens/operators/OperatorList.tsx`
- Create: `operator-portal/src/screens/operators/OperatorList.test.tsx`
- Modify: `operator-portal/src/styles/theme.css` (classi tabella/head/form)

**Interfaces:**
- Consumes: client `listOperators/createOperator/disableOperator/enableOperator/resetPassword` + tipi (Task 1); `TempPasswordModal`, `ConfirmDialog` (Task 2); `useAuth` (espone `client` e `operator`), `useApiError`; i18n `operators.*` + `shell.role.*` + `errors.*` + `common.loading`.
- Produces (usati da Task 4): `OperatorList` (default della rotta `/operators`).

- [ ] **Step 1: Scrivi i test di `OperatorList` (`OperatorList.test.tsx`)**

```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, ADMIN, OPERATORS } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { OperatorList } from './OperatorList'

afterEach(() => sessionStorage.clear())

function admin(overrides = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: ADMIN }, operators: { status: 'ok', operators: OPERATORS }, ...overrides })
}

test('lists operators with role, status, and per-status action', async () => {
  setToken('tok')
  renderWithProviders(<OperatorList />, { client: admin(), route: '/operators' })
  expect(await screen.findByText('Maria Rossi')).toBeInTheDocument()
  // active operator → Disabilita; disabled one → Riabilita
  expect(screen.getAllByRole('button', { name: 'Disabilita' }).length).toBeGreaterThan(0)
  expect(screen.getByRole('button', { name: 'Riabilita' })).toBeInTheDocument()
  // must_change badge present for g.bianchi
  expect(screen.getByText('Deve cambiare password')).toBeInTheDocument()
})

test('create flow: form sends the 3 fields, opens the temp-password modal, reloads', async () => {
  setToken('tok')
  const client = admin()
  renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await userEvent.click(screen.getByRole('button', { name: /Nuovo operatore/ }))
  await userEvent.type(screen.getByLabelText('Nome utente'), 'n.neri')
  await userEvent.type(screen.getByLabelText('Nome visualizzato'), 'Nadia Neri')
  await userEvent.selectOptions(screen.getByLabelText('Ruolo'), 'operator')
  await userEvent.click(screen.getByRole('button', { name: 'Crea operatore' }))
  expect(client.createdOperators[0]).toEqual({ username: 'n.neri', display_name: 'Nadia Neri', role: 'operator' })
  expect(await screen.findByText('7Kq9-mZ2t-Rf4x')).toBeInTheDocument() // modal
  await userEvent.click(screen.getByRole('button', { name: 'Ho copiato, chiudi' }))
  expect(screen.queryByText('7Kq9-mZ2t-Rf4x')).not.toBeInTheDocument() // cleared on close
  await waitFor(() => expect(client.calls.lops).toBe(2)) // reloaded
})

test('disable asks for confirmation; cancel does NOT call the client', async () => {
  setToken('tok')
  const client = admin()
  renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await userEvent.click(screen.getAllByRole('button', { name: 'Disabilita' })[0])
  expect(screen.getByText(/Disabilitare l’operatore «m.rossi»/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Annulla' }))
  expect(client.calls.opdisable).toBe(0)
})

test('disable confirmed calls disableOperator(id) and reloads', async () => {
  setToken('tok')
  const client = admin()
  renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await userEvent.click(screen.getAllByRole('button', { name: 'Disabilita' })[0])
  await userEvent.click(screen.getByRole('button', { name: 'Conferma' }))
  await waitFor(() => expect(client.disabledIds).toEqual([1]))
  await waitFor(() => expect(client.calls.lops).toBe(2))
})

test('reset confirmed opens the modal with the new temp-password', async () => {
  setToken('tok')
  const client = admin()
  renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await userEvent.click(screen.getAllByRole('button', { name: 'Reset password' })[0])
  await userEvent.click(screen.getByRole('button', { name: 'Conferma' }))
  expect(await screen.findByText('NEW-pw-123')).toBeInTheDocument()
  expect(client.resetIds).toEqual([1])
})

test('auto-lockout: the logged-in admin cannot disable/reset their own row', async () => {
  setToken('tok')
  // ADMIN.id = 9; include the admin in the list
  const withSelf = [...OPERATORS, ADMIN]
  renderWithProviders(<OperatorList />, { client: admin({ operators: { status: 'ok', operators: withSelf } }), route: '/operators' })
  await screen.findByText('Amministratore')
  const row = screen.getByText('Amministratore').closest('tr') as HTMLElement
  const { getByRole } = within(row)
  expect(getByRole('button', { name: 'Disabilita' })).toBeDisabled()
  expect(getByRole('button', { name: 'Reset password' })).toBeDisabled()
})

test('403 on mount shows the error, not a stuck loading spinner', async () => {
  setToken('tok')
  renderWithProviders(<OperatorList />, { client: admin({ operators: { status: 'forbidden' } }), route: '/operators' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})
```

Aggiungi l'import mancante in cima: `import { within } from '@testing-library/react'` (unisci a `screen, waitFor`).

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/screens/operators/OperatorList.test.tsx`
Expected: FAIL (moduli inesistenti).

- [ ] **Step 3: Implementa `CreateOperatorForm.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { CreateOperatorRequest, Role } from '../../types'

const ROLES: Role[] = ['operator', 'supervisor', 'admin', 'auditor']

export function CreateOperatorForm({
  onSubmit,
  onCancel,
  busy,
  error,
}: {
  onSubmit: (body: CreateOperatorRequest) => void
  onCancel: () => void
  busy: boolean
  error: string
}) {
  const { t } = useTranslation()
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<Role | ''>('')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !displayName.trim() || !role) return
    onSubmit({ username: username.trim(), display_name: displayName.trim(), role })
  }

  return (
    <form className="op-create" onSubmit={submit}>
      <h2>{t('operators.createTitle')}</h2>
      <label>{t('operators.username')}<input value={username} onChange={(e) => setUsername(e.target.value)} /></label>
      <label>{t('operators.displayName')}<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></label>
      <label>{t('operators.role')}
        <select value={role} onChange={(e) => setRole(e.target.value as Role | '')}>
          <option value="">{t('operators.rolePlaceholder')}</option>
          {ROLES.map((r) => <option key={r} value={r}>{t(`shell.role.${r}`)}</option>)}
        </select>
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="op-create-actions">
        <button type="button" onClick={onCancel}>{t('operators.cancel')}</button>
        <button type="submit" disabled={busy || !username.trim() || !displayName.trim() || !role}>{t('operators.create')}</button>
      </div>
    </form>
  )
}
```

- [ ] **Step 4: Implementa `OperatorList.tsx`**

```tsx
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { CreateOperatorRequest, Operator } from '../../types'
import { CreateOperatorForm } from './CreateOperatorForm'
import { ConfirmDialog } from './ConfirmDialog'
import { TempPasswordModal } from './TempPasswordModal'

type Pending = { kind: 'disable' | 'enable' | 'reset'; op: Operator } | null
type TempPw = { password: string; subtitle: string } | null

export function OperatorList() {
  const { t } = useTranslation()
  const { client, operator: me } = useAuth()
  const handleError = useApiError()
  const [operators, setOperators] = useState<Operator[] | null>(null)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [createError, setCreateError] = useState('')
  const [pending, setPending] = useState<Pending>(null)
  const [tempPw, setTempPw] = useState<TempPw>(null)

  const onErr = useCallback(
    (status: 'unauthorized' | 'forbidden' | 'error', set: (m: string) => void) => {
      const outcome = handleError(status)
      if (outcome !== 'handled') set(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
    },
    [handleError, t],
  )

  const load = useCallback(async () => {
    setError('')
    const r = await client.listOperators()
    if (r.status === 'ok') setOperators(r.operators)
    else onErr(r.status, setError)
  }, [client, onErr])

  useEffect(() => {
    void load()
  }, [load])

  async function create(body: CreateOperatorRequest) {
    setCreateError('')
    setCreateBusy(true)
    const r = await client.createOperator(body)
    setCreateBusy(false)
    if (r.status === 'ok') {
      setShowCreate(false)
      setTempPw({ password: r.created.temp_password, subtitle: t('operators.createdSubtitle', { name: r.created.operator.username }) })
      void load()
    } else onErr(r.status, setCreateError)
  }

  async function runPending() {
    if (!pending) return
    const { kind, op } = pending
    setPending(null)
    if (kind === 'reset') {
      const r = await client.resetPassword(op.id)
      if (r.status === 'ok') {
        setTempPw({ password: r.temp_password, subtitle: t('operators.resetSubtitle', { name: op.username }) })
        void load()
      } else onErr(r.status, setError)
      return
    }
    const r = kind === 'disable' ? await client.disableOperator(op.id) : await client.enableOperator(op.id)
    if (r.status === 'ok') void load()
    else onErr(r.status, setError)
  }

  const confirmMessage = pending
    ? t(
        pending.kind === 'disable'
          ? 'operators.confirmDisable'
          : pending.kind === 'enable'
            ? 'operators.confirmEnable'
            : 'operators.confirmReset',
        { name: pending.op.username },
      )
    : ''

  return (
    <div className="op-admin">
      <div className="op-head">
        <h1>{t('operators.title')}</h1>
        <button type="button" onClick={() => setShowCreate((s) => !s)}>+ {t('operators.new')}</button>
      </div>

      {showCreate && <CreateOperatorForm onSubmit={create} onCancel={() => setShowCreate(false)} busy={createBusy} error={createError} />}

      {error && <p className="error" role="alert">{error}</p>}
      {operators === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        operators &&
        (operators.length === 0 ? (
          <p>{t('operators.empty')}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t('operators.colUsername')}</th>
                <th>{t('operators.colName')}</th>
                <th>{t('operators.colRole')}</th>
                <th>{t('operators.colStatus')}</th>
                <th>{t('operators.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {operators.map((op) => {
                const isSelf = me?.id === op.id
                const selfTitle = isSelf ? t('operators.selfActionBlocked') : undefined
                return (
                  <tr key={op.id}>
                    <td>{op.username}</td>
                    <td>{op.display_name}</td>
                    <td>{t(`shell.role.${op.role}`)}</td>
                    <td>
                      {op.is_active ? (
                        <span className="st-active">● {t('operators.active')}</span>
                      ) : (
                        <span className="st-disabled">○ {t('operators.disabled')}</span>
                      )}
                      {op.must_change_password && <span className="badge-mc">{t('operators.mustChange')}</span>}
                    </td>
                    <td className="op-actions">
                      {op.is_active ? (
                        <button type="button" disabled={isSelf} title={selfTitle} onClick={() => setPending({ kind: 'disable', op })}>
                          {t('operators.disable')}
                        </button>
                      ) : (
                        <button type="button" onClick={() => setPending({ kind: 'enable', op })}>{t('operators.enable')}</button>
                      )}
                      <button type="button" disabled={isSelf} title={selfTitle} onClick={() => setPending({ kind: 'reset', op })}>
                        {t('operators.resetPassword')}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ))
      )}

      {pending && (
        <ConfirmDialog message={confirmMessage} confirmLabel={t('operators.confirm')} onConfirm={runPending} onCancel={() => setPending(null)} />
      )}
      {tempPw && <TempPasswordModal password={tempPw.password} subtitle={tempPw.subtitle} onClose={() => setTempPw(null)} />}
    </div>
  )
}
```

- [ ] **Step 5: Aggiungi le classi CSS (`styles/theme.css`)**

Append:
```css
.op-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.op-head button { padding: 8px 14px; border: 0; border-radius: 8px; background: var(--accent); color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
.op-create { border: 1px solid var(--border); border-radius: 10px; padding: 12px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 8px; max-width: 420px; }
.op-create label { display: flex; flex-direction: column; gap: 4px; font-weight: 600; }
.op-create input, .op-create select { padding: 8px; border: 1px solid var(--border); border-radius: 8px; font: inherit; }
.op-create-actions { display: flex; gap: 8px; justify-content: flex-end; }
.op-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.op-actions button { padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; background: #fff; font: inherit; cursor: pointer; }
.op-actions button:disabled { opacity: .5; cursor: not-allowed; }
.st-active { color: #15803d; font-weight: 600; }
.st-disabled { color: #6b7280; }
.badge-mc { margin-left: 8px; background: #fef3c7; color: #92400e; border-radius: 10px; padding: 2px 8px; font-size: 12px; }
```

- [ ] **Step 6: Esegui i test — devono passare, poi gate**

Run: `cd operator-portal && npx vitest run src/screens/operators/ && npm run typecheck && npm run lint`
Expected: PASS, pristine.

- [ ] **Step 7: Commit**

```bash
git add operator-portal/src/screens/operators/CreateOperatorForm.tsx operator-portal/src/screens/operators/OperatorList.tsx operator-portal/src/screens/operators/OperatorList.test.tsx operator-portal/src/styles/theme.css
git commit -m "feat(operator-portal): operator list + create form (confirm + auto-lockout guard)"
```

---

### Task 4: Nav «Gestione utenze» reale + rotta `/operators` + integrazione

**Files:**
- Modify: `operator-portal/src/rbac/nav.ts` (`operators` → `built: true`)
- Modify: `operator-portal/src/App.tsx` (rotta `/operators`)
- Modify: `operator-portal/src/shell/Nav.test.tsx` (rafforza l'asserzione admin)
- Modify: `operator-portal/src/App.test.tsx` (admin raggiunge la sezione)

**Interfaces:**
- Consumes: `OperatorList` (Task 3); `NAV_BY_ROLE` (`rbac/nav`); `ADMIN` (`test/fakeClient`).
- Produces: rotta pubblica `/operators` funzionante per l'admin.

- [ ] **Step 1: Aggiorna il test della Nav (`Nav.test.tsx`)**

Sostituisci il test «admin sees admin sections» con una versione che verifica il **link reale** (rafforzamento legittimo, come S13):
```tsx
test('admin sees admin sections; «Gestione utenze» is a real link, Config stays disabled', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Gestione utenze/ })).toHaveAttribute('href', '/operators')
  expect(screen.queryByText('Richieste di lavoro')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Configurazione/ })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Aggiungi il test d'integrazione (`App.test.tsx`)**

Append:
```tsx
test('an authenticated admin can reach the operators section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } })
  renderApp(client, '/operators')
  // «+ Nuovo operatore» is rendered only by OperatorList → proves the route mounted
  expect(await screen.findByRole('button', { name: /Nuovo operatore/ })).toBeInTheDocument()
})
```

- [ ] **Step 3: Esegui — il test d'integrazione deve fallire**

Run: `cd operator-portal && npx vitest run src/App.test.tsx src/shell/Nav.test.tsx`
Expected: FAIL (rotta `/operators` assente → redirect a `/`; nav non è ancora un link).

- [ ] **Step 4: Marca la voce di nav `built` (`rbac/nav.ts`)**

Nel blocco `admin`, cambia la riga `operators`:
```ts
    { path: '/operators', labelKey: 'nav.operators', built: true },
```

- [ ] **Step 5: Aggancia la rotta (`App.tsx`)**

Aggiungi l'import: `import { OperatorList } from './screens/operators/OperatorList'`. Dentro il blocco `<Route path="/" …>`, dopo la rotta `profiles/:pseudonym`, aggiungi:
```tsx
        <Route path="operators" element={<OperatorList />} />
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
git commit -m "feat(operator-portal): wire operators section route + real nav link"
```

---

## Self-Review

- **Spec coverage:** §2 obiettivi → elenco (T3), crea+modale (T2/T3), disable/enable/reset (T1/T3), conferme (T3), auto-lockout (T3), client fail-closed (T1), i18n (T1), nav `built` + rotta (T4). Non-obiettivi (no edit/delete) rispettati: nessun endpoint/azione di modifica o cancellazione.
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto.
- **Type consistency:** `ListOperatorsResult.operators`, `CreateOperatorResult.created`, `ResetPasswordResult.temp_password`, `MutateOperatorResult` (solo `ok`) usati coerentemente tra client (T1), fake (T1) e schermata (T3). `CreateOperatorRequest {username, display_name, role}` inviato dal form e registrato dal fake. Fixtures `ADMIN` (id 9), `OPERATORS` (id 1/2/3) coerenti coi test. `shell.role.<role>` riusato per le etichette ruolo.
- **Degrado/privacy:** ramo loading gated da `!error` (come il fix S13); `temp_password` solo in stato locale, azzerato alla chiusura della modale (test lo verifica); nessuna PII/dato solo-lavoro nella sezione.
