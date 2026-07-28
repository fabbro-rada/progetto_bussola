# Stato sistema / configurazione (Amministratore) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La vista **stato sistema / configurazione corrente** (sola lettura) per l'Amministratore (§6): endpoint `GET /system-config` (`CONFIGURE_SYSTEM`, config non-segreta + check live LLM, auditato) + pannello admin sola-lettura.

**Architecture:** Fetta verticale (come S15/S20). Backend nuovo: `bussola.system` (`compute_system_config` legge i moduli `llm/auth/voice/config` + un check live LLM dietro seam iniettabile) + router `GET /system-config` dietro `CONFIGURE_SYSTEM` con `append_audit("system_config_viewed")`. Frontend: `operatorClient.getSystemConfig()` fail-closed + `SystemConfigPanel` (nav «Configurazione» `built`). Nessuna nuova tabella.

**Tech Stack:** Backend Python 3.12 (FastAPI, Pydantic, psycopg3, httpx), pytest/ruff/mypy. Frontend React 18 + Vite 5 + TS + react-i18next, Vitest + @testing-library/react. **Nessuna nuova dipendenza** (`httpx` già presente).

## Global Constraints

- **Backend task** estende `backend/`; **frontend task** estendono `operator-portal/`. `frontend/` (kiosk) NON si tocca. Nessuna nuova dipendenza. **Nessuna nuova tabella/migrazione.**
- **TDD** (RED → GREEN), **solo dati sintetici**. Output test pristine.
- **Sola lettura + nessun segreto (linee rosse §3/§7.3):** `SystemConfig` espone SOLO valori non-sensibili (modello/endpoint-loopback/timeout, lingue, STT, disponibilità TTS per lingua, policy sessione). **MAI** password DB, DSN, token. Nessun editing.
- **Nessun controllo di sicurezza esposto/indebolibile (§2/§9):** guardrail/ambito/PII non compaiono nel DTO e non sono toccabili.
- **Check live LLM dietro seam iniettabile, fail-safe:** `compute_system_config(*, llm_reachable=…)`; default = `httpx.get({BASE_URL}/health, timeout breve)`, qualsiasi errore/timeout → `False`. I test iniettano uno stub (nessuna chiamata LLM reale).
- **`GET /system-config` dietro `require_permission(CONFIGURE_SYSTEM)`** (solo `admin` → 403 altri); ogni lettura emette `append_audit(action="system_config_viewed", actor=<username>)` (§7.3).
- **Frontend fail-closed**, mai un throw: Bearer via `headers(false)`; `401→'unauthorized'`, `403→'forbidden'`, rete/5xx/JSON-invalido → `'error'`. Degrado: `401`→`useApiError`; `403`→`t('errors.forbidden')`; rete/5xx→`t('errors.generic')`; loading gated `config === null && !error`.
- **i18n**: ogni stringa via `t(...)`; `nav.config` = «Configurazione» esiste già. Nav-label == titolo pagina → test d'integrazione per contenuto proprio (non per il titolo).
- **DB attivo** per i test backend: `docker compose up -d db`.
- **Gate backend** (da `backend/`, `.venv`): `pytest -q && ruff check . && mypy src`. **Gate frontend** (da `operator-portal/`): `npm test && npm run typecheck && npm run lint && npm run build`.

---

### Task 1: Backend — servizio `system` + endpoint `GET /system-config`

**Files:**
- Create: `backend/src/bussola/system/__init__.py`
- Create: `backend/src/bussola/system/service.py`
- Create: `backend/src/bussola/api/routers/system.py`
- Modify: `backend/src/bussola/api/app.py`
- Create: `backend/tests/system/__init__.py`
- Create: `backend/tests/system/test_service.py`
- Create: `backend/tests/api/test_system_router.py`

**Interfaces:**
- Consumes: `require_permission`, `get_conn` (`bussola.api.deps`); `Permission.CONFIGURE_SYSTEM` (`bussola.auth.rbac`, già mappato all'admin); `append_audit` (`bussola.data.audit`); `Operator` (`bussola.auth.models`); costanti `llm.config` (`BASE_URL`, `MODEL`, `TIMEOUT`), `auth.config` (`SESSION_TTL_SECONDS`, `SESSION_IDLE_SECONDS`, `MAX_FAILED_ATTEMPTS`, `LOCKOUT_SECONDS`), `voice.config` (`STT_MODEL`, `PIPER_VOICES`); fixtures `client`/`make_operator`/`db`.
- Produces (frontend, Task 2): contratto `GET /system-config` → `200 SystemConfig` (campi §Step 4) | 401 | 403; `compute_system_config(*, llm_reachable=…)`.

- [ ] **Step 1: Avvia il DB di test**

Run: `cd backend && docker compose up -d db` (idempotente).

- [ ] **Step 2: Scrivi i test del servizio (`tests/system/test_service.py`)**

Crea `backend/tests/system/__init__.py` (vuoto) e:
```python
from bussola.system.service import SystemConfig, compute_system_config


def test_assembles_config_and_reflects_reachable_seam():
    up = compute_system_config(llm_reachable=lambda: True)
    down = compute_system_config(llm_reachable=lambda: False)
    assert up.llm_reachable is True
    assert down.llm_reachable is False
    assert up.llm_model  # non-empty (from llm.config.MODEL)
    assert up.languages == ["it", "en", "fr", "es", "ar"]
    assert up.stt_model  # from voice.config.STT_MODEL
    assert up.session_ttl_seconds > 0 and up.max_failed_attempts > 0


def test_tts_voices_marks_arabic_as_unavailable():
    cfg = compute_system_config(llm_reachable=lambda: True)
    assert cfg.tts_voices["it"] is True
    assert cfg.tts_voices["ar"] is False  # §8 Arabic = text fallback
    assert set(cfg.tts_voices) == {"it", "en", "fr", "es", "ar"}


def test_config_carries_no_secret_fields():
    # The DTO is a whitelist: no password/DSN/token field may ever exist.
    fields = set(SystemConfig.model_fields)
    assert not any(k in f for f in fields for k in ("password", "secret", "token", "dsn"))
```

- [ ] **Step 3: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/system/test_service.py`
Expected: FAIL (`bussola.system` non esiste).

- [ ] **Step 4: Implementa il servizio (`system/service.py`)**

Crea `backend/src/bussola/system/__init__.py` (vuoto) e `backend/src/bussola/system/service.py`:
```python
"""System status / configuration overview for the admin (§6), READ-ONLY.

Exposes only NON-SECRET config plus a live LLM reachability check. No secrets
(no DB password/DSN/token) and no security controls (guardrails/scope/PII stay
in code and are never exposed or editable, §2/§9)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
from pydantic import BaseModel, ConfigDict

from bussola.auth import config as auth_config
from bussola.llm import config as llm_config
from bussola.voice import config as voice_config

SUPPORTED_LANGUAGES = ("it", "en", "fr", "es", "ar")
_HEALTH_TIMEOUT = 2.0


class SystemConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_model: str
    llm_base_url: str
    llm_timeout: float
    llm_reachable: bool
    languages: list[str]
    stt_model: str
    tts_voices: dict[str, bool]
    session_ttl_seconds: int
    session_idle_seconds: int
    max_failed_attempts: int
    lockout_seconds: int


def _default_llm_reachable() -> bool:
    """Live LLM reachability, fail-safe: any error/timeout → False."""
    try:
        response = httpx.get(f"{llm_config.BASE_URL}/health", timeout=_HEALTH_TIMEOUT)
        return response.status_code == 200
    except Exception:
        return False


def compute_system_config(
    *, llm_reachable: Callable[[], bool] = _default_llm_reachable
) -> SystemConfig:
    return SystemConfig(
        llm_model=llm_config.MODEL,
        llm_base_url=llm_config.BASE_URL,
        llm_timeout=llm_config.TIMEOUT,
        llm_reachable=llm_reachable(),
        languages=list(SUPPORTED_LANGUAGES),
        stt_model=voice_config.STT_MODEL,
        tts_voices={lang: lang in voice_config.PIPER_VOICES for lang in SUPPORTED_LANGUAGES},
        session_ttl_seconds=auth_config.SESSION_TTL_SECONDS,
        session_idle_seconds=auth_config.SESSION_IDLE_SECONDS,
        max_failed_attempts=auth_config.MAX_FAILED_ATTEMPTS,
        lockout_seconds=auth_config.LOCKOUT_SECONDS,
    )
```

- [ ] **Step 5: Esegui i test del servizio — devono passare**

Run: `cd backend && pytest -q tests/system/test_service.py`
Expected: PASS (3 test).

- [ ] **Step 6: Scrivi i test dell'endpoint (`tests/api/test_system_router.py`)**

```python
import psycopg
import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_admin_gets_system_config(client, make_operator):
    user, temp = make_operator("adm1", Role.ADMIN)
    token = _login(client, user, temp)
    r = client.get("/system-config", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["llm_model"]  # non-empty
    assert body["languages"] == ["it", "en", "fr", "es", "ar"]
    assert body["tts_voices"]["ar"] is False
    # no secret leaked
    assert not any(k in body for k in ("db_password", "password", "token", "dsn"))


def test_non_admin_roles_are_forbidden(client, make_operator):
    for name, role in [("op1", Role.OPERATOR), ("sup1", Role.SUPERVISOR), ("aud1", Role.AUDITOR)]:
        user, temp = make_operator(name, role)
        token = _login(client, user, temp)
        assert client.get("/system-config", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_view_is_audited(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("adm1", Role.ADMIN)
    token = _login(client, user, temp)
    client.get("/system-config", headers={"Authorization": f"Bearer {token}"})
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor FROM audit.audit_log WHERE action = 'system_config_viewed' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None and row[0] == user
```
(Nota: nel test l'LLM reale non è attivo → `_default_llm_reachable` fallisce fast → `llm_reachable=False`; l'endpoint resta 200. Nessuno stub necessario a livello endpoint.)

- [ ] **Step 7: Esegui — devono fallire**

Run: `cd backend && pytest -q tests/api/test_system_router.py`
Expected: FAIL (rotta inesistente → 404).

- [ ] **Step 8: Implementa il router (`api/routers/system.py`) e registralo**

Crea `backend/src/bussola/api/routers/system.py`:
```python
"""System status / configuration endpoint (admin role, read-only). §2/§9: no
secrets, no security controls exposed."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.system.service import SystemConfig, compute_system_config

router = APIRouter(prefix="/system-config", tags=["system"])
_configure = require_permission(Permission.CONFIGURE_SYSTEM)


@router.get("", response_model=SystemConfig)
def get_system_config(
    operator: Operator = Depends(_configure),
    conn: psycopg.Connection = Depends(get_conn),
) -> SystemConfig:
    config = compute_system_config()
    append_audit(conn, action="system_config_viewed", actor=operator.username, target_pseudonym=None)
    return config
```
In `backend/src/bussola/api/app.py`: aggiungi `from bussola.api.routers import system as system_router` (in ordine alfabetico) e `app.include_router(system_router.router)`.

- [ ] **Step 9: Esegui i test dell'endpoint — devono passare**

Run: `cd backend && pytest -q tests/api/test_system_router.py`
Expected: PASS (3 test).

- [ ] **Step 10: Gate backend completo**

Run: `cd backend && pytest -q && ruff check . && mypy src`
Expected: tutto verde.

- [ ] **Step 11: Commit**

```bash
git add backend/src/bussola/system backend/src/bussola/api/routers/system.py backend/src/bussola/api/app.py backend/tests/system backend/tests/api/test_system_router.py
git commit -m "feat(system): read-only system config + GET /system-config (CONFIGURE_SYSTEM, audited)"
```

---

### Task 2: Frontend — client `getSystemConfig` + tipi + i18n + fake

**Files:**
- Modify: `operator-portal/src/types.ts` (append)
- Modify: `operator-portal/src/api/operatorClient.ts` (metodo + export)
- Modify: `operator-portal/src/test/fakeClient.ts` (fixture + opt + counter + metodo)
- Modify: `operator-portal/src/i18n/locales/it.ts` (gruppo `system`)
- Modify: `operator-portal/src/api/operatorClient.test.ts` (append)

**Interfaces:**
- Consumes: `headers`/`BASE` (`operatorClient.ts`); pattern fake S15/S20.
- Produces (Task 3/4): `SystemConfig {llm_model, llm_base_url, llm_timeout, llm_reachable, languages, stt_model, tts_voices, session_ttl_seconds, session_idle_seconds, max_failed_attempts, lockout_seconds}`; `SystemConfigResult` (`ok{config}` | unauthorized | forbidden | error); `OperatorClient.getSystemConfig()`; fake `SYSTEM_CONFIG` fixture, opt `systemConfig`, counter `calls.systemConfig`; i18n gruppo `system.*`.

- [ ] **Step 1: Scrivi il test del client (append a `operatorClient.test.ts`)**

```ts
test('getSystemConfig: 200→ok with Bearer; 403→forbidden; network→error', async () => {
  setToken('tok')
  const C = { llm_model: 'qwen2.5-7b-instruct', llm_base_url: 'http://127.0.0.1:8080', llm_timeout: 120, llm_reachable: true, languages: ['it','en','fr','es','ar'], stt_model: 'large-v3-turbo', tts_voices: { it: true, en: true, fr: true, es: true, ar: false }, session_ttl_seconds: 43200, session_idle_seconds: 1800, max_failed_attempts: 5, lockout_seconds: 900 }
  const f = vi.fn().mockResolvedValue(res(200, C))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.getSystemConfig()).toEqual({ status: 'ok', config: C })
  expect(String(f.mock.calls[0][0])).toMatch(/\/system-config$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.getSystemConfig()).toEqual({ status: 'forbidden' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.getSystemConfig()).toEqual({ status: 'error' })
})
```

- [ ] **Step 2: Esegui — deve fallire**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: FAIL (`getSystemConfig` non esiste).

- [ ] **Step 3: Aggiungi i tipi (`types.ts`)**

Append:
```ts
export interface SystemConfig {
  llm_model: string
  llm_base_url: string
  llm_timeout: number
  llm_reachable: boolean
  languages: string[]
  stt_model: string
  tts_voices: Record<string, boolean>
  session_ttl_seconds: number
  session_idle_seconds: number
  max_failed_attempts: number
  lockout_seconds: number
}
export type SystemConfigResult =
  | { status: 'ok'; config: SystemConfig }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
```
Estendi `OperatorClient` (dopo `getOperatorActivity`):
```ts
  getSystemConfig(): Promise<SystemConfigResult>
```

- [ ] **Step 4: Implementa `getSystemConfig` (`operatorClient.ts`)**

Aggiungi ai tipi importati: `SystemConfig, SystemConfigResult`. Prima dell'export `operatorClient`:
```ts
async function getSystemConfig(): Promise<SystemConfigResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/system-config`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', config: (await res.json()) as SystemConfig }
  } catch {
    return { status: 'error' }
  }
}
```
Aggiungi `getSystemConfig` al literal `export const operatorClient`.

- [ ] **Step 5: Esegui il test del client — deve passare**

Run: `cd operator-portal && npx vitest run src/api/operatorClient.test.ts`
Expected: PASS.

- [ ] **Step 6: Estendi il fake (`test/fakeClient.ts`)**

Importa i tipi: `SystemConfig, SystemConfigResult`. Aggiungi la fixture (dopo `ACTIVITY`):
```ts
export const SYSTEM_CONFIG: SystemConfig = {
  llm_model: 'qwen2.5-7b-instruct', llm_base_url: 'http://127.0.0.1:8080', llm_timeout: 120, llm_reachable: true,
  languages: ['it', 'en', 'fr', 'es', 'ar'], stt_model: 'large-v3-turbo',
  tts_voices: { it: true, en: true, fr: true, es: true, ar: false },
  session_ttl_seconds: 43200, session_idle_seconds: 1800, max_failed_attempts: 5, lockout_seconds: 900,
}
```
Nella firma `opts` aggiungi `systemConfig?: SystemConfigResult`; nei `calls` aggiungi `systemConfig: number` (init 0); aggiungi il metodo:
```ts
    async getSystemConfig() {
      calls.systemConfig++
      return opts.systemConfig ?? { status: 'ok', config: SYSTEM_CONFIG }
    },
```

- [ ] **Step 7: Aggiungi le stringhe i18n (`i18n/locales/it.ts`)**

Nuovo gruppo `system` (dopo `activity`):
```ts
  system: {
    title: 'Configurazione',
    llm: 'Modello linguistico',
    llmModel: 'Modello',
    llmEndpoint: 'Endpoint',
    llmTimeout: 'Timeout (s)',
    llmStatus: 'Stato',
    reachable: 'Raggiungibile',
    unreachable: 'Non raggiungibile',
    languages: 'Lingue supportate',
    voice: 'Voce',
    sttModel: 'Riconoscimento vocale (STT)',
    ttsAvailable: 'Sintesi vocale',
    ttsTextOnly: 'solo testo',
    session: 'Policy di sessione',
    sessionTtl: 'Durata sessione (s)',
    sessionIdle: 'Inattività massima (s)',
    maxAttempts: 'Tentativi falliti max',
    lockout: 'Blocco (s)',
  },
```
(`nav.config` = «Configurazione» esiste già.)

- [ ] **Step 8: Gate + commit**

Run: `cd operator-portal && npm test && npm run typecheck && npm run lint`
```bash
git add operator-portal/src/types.ts operator-portal/src/api/operatorClient.ts operator-portal/src/api/operatorClient.test.ts operator-portal/src/test/fakeClient.ts operator-portal/src/i18n/locales/it.ts
git commit -m "feat(operator-portal): system-config client + types + i18n"
```

---

### Task 3: Frontend — `SystemConfigPanel`

**Files:**
- Create: `operator-portal/src/screens/system/SystemConfigPanel.tsx`
- Create: `operator-portal/src/screens/system/SystemConfigPanel.test.tsx`

**Interfaces:**
- Consumes: `useAuth().client.getSystemConfig()`, `useApiError`, i18n `system.*` + `errors.*` + `common.loading`; `SystemConfig`.
- Produces (Task 4): `SystemConfigPanel` (default della rotta `/config`).

- [ ] **Step 1: Scrivi i test (`SystemConfigPanel.test.tsx`)**

```tsx
import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, SYSTEM_CONFIG } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { SystemConfigPanel } from './SystemConfigPanel'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/config" element={<SystemConfigPanel />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function admin(config: unknown) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) }, systemConfig: config as never })
}

test('renders the config with a reachable badge and per-language voice', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: admin({ status: 'ok', config: SYSTEM_CONFIG }), route: '/config' })
  expect(await screen.findByText('qwen2.5-7b-instruct')).toBeInTheDocument()
  expect(screen.getByText('Raggiungibile')).toBeInTheDocument()
  expect(screen.getByText('solo testo')).toBeInTheDocument()  // ar → text-only
})

test('shows the unreachable badge when the LLM is down', async () => {
  setToken('tok')
  const down = { ...SYSTEM_CONFIG, llm_reachable: false }
  renderWithProviders(harness(), { client: admin({ status: 'ok', config: down }), route: '/config' })
  expect(await screen.findByText('Non raggiungibile')).toBeInTheDocument()
})

test('403 shows the forbidden error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: admin({ status: 'forbidden' }), route: '/config' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: admin({ status: 'unauthorized' }), route: '/config' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})

test('network error shows the retryable message', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: admin({ status: 'error' }), route: '/config' })
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})
```

- [ ] **Step 2: Esegui — devono fallire**

Run: `cd operator-portal && npx vitest run src/screens/system/SystemConfigPanel.test.tsx`
Expected: FAIL (modulo inesistente).

- [ ] **Step 3: Implementa `SystemConfigPanel.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useApiError } from '../../hooks/useApiError'
import type { SystemConfig } from '../../types'

export function SystemConfigPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const handleError = useApiError()
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void client.getSystemConfig().then((r) => {
      if (!active) return
      if (r.status === 'ok') setConfig(r.config)
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
    <div className="system-config">
      <h1>{t('system.title')}</h1>
      {error && <p className="error" role="alert">{error}</p>}
      {config === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        config && (
          <div className="config-sections">
            <section>
              <h2>{t('system.llm')}</h2>
              <dl>
                <dt>{t('system.llmModel')}</dt><dd>{config.llm_model}</dd>
                <dt>{t('system.llmEndpoint')}</dt><dd>{config.llm_base_url}</dd>
                <dt>{t('system.llmTimeout')}</dt><dd>{config.llm_timeout}</dd>
                <dt>{t('system.llmStatus')}</dt>
                <dd>
                  <span className={`badge-status ${config.llm_reachable ? 'st-approved' : ''}`.trim()}>
                    {config.llm_reachable ? t('system.reachable') : t('system.unreachable')}
                  </span>
                </dd>
              </dl>
            </section>
            <section>
              <h2>{t('system.languages')}</h2>
              <p>{config.languages.join(', ')}</p>
            </section>
            <section>
              <h2>{t('system.voice')}</h2>
              <dl>
                <dt>{t('system.sttModel')}</dt><dd>{config.stt_model}</dd>
                {config.languages.map((lang) => (
                  <div key={lang}>
                    <dt>{lang}</dt>
                    <dd>{config.tts_voices[lang] ? t('system.ttsAvailable') : t('system.ttsTextOnly')}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section>
              <h2>{t('system.session')}</h2>
              <dl>
                <dt>{t('system.sessionTtl')}</dt><dd>{config.session_ttl_seconds}</dd>
                <dt>{t('system.sessionIdle')}</dt><dd>{config.session_idle_seconds}</dd>
                <dt>{t('system.maxAttempts')}</dt><dd>{config.max_failed_attempts}</dd>
                <dt>{t('system.lockout')}</dt><dd>{config.lockout_seconds}</dd>
              </dl>
            </section>
          </div>
        )
      )}
    </div>
  )
}
```
(Il badge «Raggiungibile» usa `st-approved` verde; «Non raggiungibile» resta neutro. La riga di stato dell'LLM usa la label dedicata `system.llmStatus` = «Stato», già aggiunta al gruppo i18n in Task 2.)

- [ ] **Step 4: Esegui i test + gate**

Run: `cd operator-portal && npx vitest run src/screens/system/SystemConfigPanel.test.tsx && npm run typecheck && npm run lint`
Expected: PASS, pristine. (Il badge verde riusa `.badge-status`/`.st-approved` già in `theme.css`; nessuna nuova CSS necessaria.)

- [ ] **Step 5: Commit**

```bash
git add operator-portal/src/screens/system/SystemConfigPanel.tsx operator-portal/src/screens/system/SystemConfigPanel.test.tsx
git commit -m "feat(operator-portal): admin system-config panel (read-only)"
```

---

### Task 4: Nav «Configurazione» reale + rotta `/config` + integrazione

**Files:**
- Modify: `operator-portal/src/rbac/nav.ts`
- Modify: `operator-portal/src/App.tsx`
- Modify: `operator-portal/src/shell/Nav.test.tsx`
- Modify: `operator-portal/src/App.test.tsx`

**Interfaces:**
- Consumes: `SystemConfigPanel` (Task 3); `NAV_BY_ROLE`.
- Produces: rotta `/config` funzionante per l'admin.

- [ ] **Step 1: Aggiorna il test della Nav (`Nav.test.tsx`)**

Il test admin di S14 asserisce «Gestione utenze» link reale **e** «Configurazione» disabilitato: la seconda asserzione ora è falsa (config diventa `built`). Sostituiscilo con una versione che asserisce entrambe come link reali (rafforzamento legittimo):
```tsx
test('admin sees «Gestione utenze» and «Configurazione» as real links', async () => {
  setToken('tok')
  renderWithProviders(<Nav />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } }),
  })
  expect(await screen.findByRole('link', { name: /Gestione utenze/ })).toHaveAttribute('href', '/operators')
  expect(await screen.findByRole('link', { name: /Configurazione/ })).toHaveAttribute('href', '/config')
})
```
(Se il test S14 aveva un nome diverso, sostituiscilo; mantieni intatti gli altri test.)

- [ ] **Step 2: Aggiungi il test d'integrazione (`App.test.tsx`)**

Append (query per contenuto proprio della schermata, non per il titolo == label nav):
```tsx
test('an authenticated admin can reach the system-config section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } })
  renderApp(client, '/config')
  // «Modello linguistico» is a section heading rendered only by SystemConfigPanel → proves the route mounted
  expect(await screen.findByText('Modello linguistico')).toBeInTheDocument()
})
```

- [ ] **Step 3: Esegui — i test devono fallire**

Run: `cd operator-portal && npx vitest run src/App.test.tsx src/shell/Nav.test.tsx`
Expected: FAIL (rotta `/config` assente; «Configurazione» non ancora link).

- [ ] **Step 4: Marca la voce di nav `built` (`rbac/nav.ts`)**

Nel blocco `admin`, cambia la riga `config`:
```ts
    { path: '/config', labelKey: 'nav.config', built: true },
```

- [ ] **Step 5: Aggancia la rotta (`App.tsx`)**

Import: `import { SystemConfigPanel } from './screens/system/SystemConfigPanel'`. Dentro il blocco `<Route path="/" …>`, dopo `activity`, aggiungi:
```tsx
        <Route path="config" element={<SystemConfigPanel />} />
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
git commit -m "feat(operator-portal): wire system-config route + real nav link"
```

---

## Self-Review

- **Spec coverage:** §2 obiettivi → servizio+endpoint (T1), tipi+client+i18n (T2), pannello (T3), nav+rotta (T4). Sola lettura, nessun segreto (test whitelist campi + endpoint no-secret), no controlli sicurezza, check LLM dietro seam (test ermetici, True/False), CONFIGURE_SYSTEM + 403 + `system_config_viewed`, tts ar False. Tutti coperti.
- **Placeholder scan:** nessun TODO/TBD; ogni step ha codice o comando concreto. La chiave i18n `system.llmStatus: 'Stato'` è nel gruppo `system` (Task 2) e usata dal blocco LLM del pannello (Task 3).
- **Type consistency:** `SystemConfig` ha gli stessi 11 campi in backend (`service.py`), contratto HTTP, `types.ts`, fake e pannello; `SystemConfigResult.config` usato client→fake→pannello; `compute_system_config(*, llm_reachable=…)` consumato dal router (default) e dai test (stub); `Permission.CONFIGURE_SYSTEM` (già mappato all'admin) consumato da T1.
- **Rossa/§2/§3/§9:** nessun segreto nel DTO (test); nessun controllo di sicurezza esposto; sola lettura; seam fail-safe; accesso auditato; nav==titolo → test integrazione per contenuto proprio.
