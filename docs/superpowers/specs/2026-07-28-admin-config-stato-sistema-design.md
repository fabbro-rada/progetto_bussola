# Spec di design — Sottosistema 21: Stato sistema / configurazione (Amministratore)

**Progetto «Bussola»** · Sottosistema 21 (portale operatore · ruolo Amministratore · stato sistema / configurazione, **sola lettura**) · *Design di riferimento per il piano collegato* · 2026-07-28

---

## 0. Cos'è questo documento

Spec di design della vista **stato del sistema / configurazione corrente** per il ruolo **Amministratore** (§6: «configura il sistema, ne cura il funzionamento»). È l'ultimo pannello del portale. **Fetta verticale** (backend + frontend) come S15/S20. Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*. Si conforma a `CLAUDE.md` §2 (nessun controllo di sicurezza esposto o indebolibile), §3 (locale, open source, budget-zero, solo azioni previste, fail-closed, nessun segreto in uscita), §6 (ruolo **Amministratore**, `CONFIGURE_SYSTEM`, privilegio minimo, ruolo tecnico-gestionale; server autorità), §7.3 (accesso auditato, filtro dati sensibili in uscita), §9 (nessun indebolimento delle garanzie di sicurezza; TDD, dati sintetici), §11 (codice inglese, stringhe UI esternalizzate).

**Decisione di scoping (approvata).** Tutta la configurazione del sistema è **deployment env-var** (DSN DB, modelli, device, voci, policy sessione), caricata all'avvio; i **guardrail/controllo-ambito/filtro-PII non sono configurabili** (sono in codice/prompt, sempre attivi) e **non devono** diventarlo (§2/§9). Un editor di config a runtime sarebbe over-engineering (§3/YAGNI), in parte inefficace (valori import-time) e rischioso. Perciò «configura il sistema, ne cura il funzionamento» per il pilota si realizza come **vista di sola lettura** dello stato: la configurazione non-segreta corrente + un check live di raggiungibilità dell'LLM. **Nessuna modifica**, per costruzione.

## 1. Contesto e scopo

L'Amministratore gestisce già le utenze (S14). Questo pannello gli dà la **visione d'insieme del funzionamento**: quale modello è in uso e se è raggiungibile, quali lingue sono supportate, la disponibilità della voce per lingua, e la policy di sessione — così può «curare il funzionamento» del pilota. È una pagina di **supervisione tecnica**, non una console di editing: sicura per costruzione (non può rompere nulla né toccare la sicurezza).

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Backend**: `compute_system_config(*, llm_reachable=…) -> SystemConfig` che assembla i **valori configurati non-segreti** (LLM, lingue, voce, policy sessione) e un **check live** della raggiungibilità dell'LLM dietro un **seam iniettabile** (default: ping HTTP breve e fail-safe; test ermetici via stub). Endpoint `GET /system-config` dietro `CONFIGURE_SYSTEM` (solo `admin`), **auditato** (`system_config_viewed`).
- **Frontend**: sezione `/config` sotto la shell S11, dietro `ProtectedRoute` + ruolo admin; la voce di nav (placeholder S11) diventa **link reale** (`built`); pannello **sola-lettura** (LLM + badge raggiungibilità, lingue, voce per lingua, policy sessione); degrado 401/403/error; `operatorClient` esteso fail-closed.
- **i18n** italiano esternalizzato.

**Non-obiettivi (rimandati / esclusi):**
- **Editing della configurazione**: escluso (scope approvato). Nessun form, nessuno store di config a runtime, nessun reload.
- **Segreti**: password DB, token kiosk, DSN con credenziali, chiavi — **mai** esposti (§3/§7.3). Il DTO non li contiene per costruzione.
- **Controlli di sicurezza (guardrail/ambito/PII)**: **non** esposti e **non** editabili (§2/§9). Non compaiono nel DTO.
- **Health checks pesanti**: niente verifica catena audit (è dell'Auditor, O(n)), niente probe della voce (STT/TTS su CPU, lenti). Solo un check live leggero dell'LLM.
- **Metriche/attività**: già S15/S20; qui è **configurazione + salute**, non metriche di lavoro.

## 3. Decisioni di design (con motivazione)

1. **Sola lettura, nessun editor (scope approvato).** *Perché §2/§3/§9:* la config è deployment env-var (spesso import-time); un editor a runtime è complesso, in parte inefficace e amplia la superficie di rottura; e la sicurezza (guardrail/ambito/PII) non deve mai essere indebolibile da un pannello. Una vista di sola lettura realizza «cura il funzionamento» senza alcun rischio.

2. **Nessun segreto nel payload (linea rossa §3/§7.3).** Il DTO espone solo valori non-sensibili: nome modello, base_url (loopback, non segreto), timeout, lingue, modello STT, disponibilità voce per lingua, e i valori di policy sessione (TTL/idle/lockout/tentativi). **Esclude** password DB, DSN, token. *Perché §7.3:* «filtro dei dati sensibili in uscita»; il pannello non deve diventare un canale di fuga di credenziali.

3. **Check live dell'LLM dietro seam iniettabile (opzione approvata).** `compute_system_config(*, llm_reachable=…)` riceve un callable; il default fa un `GET {BASE_URL}/health` con timeout breve, **fail-safe** (qualsiasi errore/timeout → `False`). *Perché §6 «cura il funzionamento»:* il server modello giù è il guasto più comune; un badge «raggiungibile/non raggiungibile» è il segnale operativo più utile. *Perché §9 (test):* il seam rende i test **ermetici** (nessun LLM reale) e isola la latenza/flakiness del probe.

4. **Voce per lingua come disponibilità booleana.** `tts_voices`: per ognuna delle 5 lingue, se una voce Piper è configurata (l'arabo risulterà assente → «solo testo», coerente con §8). *Perché:* rende visibile il degrado elegante voce→testo senza esporre percorsi di file.

5. **RBAC applicativo, server autorità; accesso auditato.** `require_permission(CONFIGURE_SYSTEM)` (solo admin → 403); `append_audit(action="system_config_viewed", actor=<username>)`, coerente con `metrics_viewed`/`operator_activity_viewed`. *Perché §6/§7.3.*

6. **`operatorClient` esteso fail-closed + `useApiError`.** Come S12–S20. *Perché §3.* Fetta verticale in un'unica spec (superficie piccola). Nessuna nuova tabella/migrazione.

## 4. Unità e confini

**Backend** (`backend/src/bussola/`):
- **`system/service.py`** (nuovo modulo) — `SystemConfig` (pydantic, `extra="forbid"`, campi §5) + `compute_system_config(*, llm_reachable: Callable[[], bool] = _default_llm_reachable) -> SystemConfig` (legge i moduli `llm/auth/voice/config`; nessun segreto); `_default_llm_reachable()` (httpx GET `{BASE_URL}/health`, timeout breve, fail-safe). `SUPPORTED_LANGUAGES = ("it","en","fr","es","ar")` definito qui (o riusato se esiste).
- **`api/routers/system.py`** — `GET /system-config` → `SystemConfig`, `Depends(require_permission(CONFIGURE_SYSTEM))`, `append_audit("system_config_viewed", ...)`.
- **`api/app.py`** — include il router.

**Frontend** (`operator-portal/src/`):
- **`types.ts`** (estensione) — `SystemConfig` + `SystemConfigResult` (`ok{config}` | unauthorized | forbidden | error).
- **`api/operatorClient`** (estensione) — `getSystemConfig()` fail-closed.
- **`screens/system/SystemConfigPanel`** — pannello sola-lettura a sezioni.
- **`rbac/nav`** — `config` marcato `built`.
- **`App`** — rotta `/config` annidata sotto `ProtectedRoute`/`AppShell`.
- **`i18n/locales/it`** (estensione) — gruppo `system` (titolo, etichette sezioni/campi, badge raggiungibilità, «solo testo»).

Confine: il backend legge da moduli di config esistenti + un probe HTTP verso l'LLM; il frontend dipende dal contratto `GET /system-config` e dallo scheletro S11. Server autorità (RBAC/403; audit).

## 5. Flusso e contratto HTTP

```
[admin] Nav «Configurazione» → /config
   GET /system-config  (require CONFIGURE_SYSTEM; audit system_config_viewed; live LLM /health)
      → 200 SystemConfig { llm_model, llm_base_url, llm_timeout, llm_reachable,
                           languages[5], stt_model, tts_voices{lingua→bool},
                           session_ttl_seconds, session_idle_seconds, max_failed_attempts, lockout_seconds }
      → pannello a sezioni (LLM + badge raggiungibilità, lingue, voce, sessione)
   401 → onUnauthorized + /login ; 403 → «non hai i permessi» ; rete/5xx → errore ritentabile
```

`SystemConfig` non contiene alcun segreto (nessuna password/DSN/token).

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**; backend `pytest` (endpoint con `client`/`make_operator`; il servizio con seam stubbato), frontend `Vitest` + @testing-library/react (`operatorClient` fake). Priorità:
- **`compute_system_config`**: assembla i valori attesi dai moduli di config; `llm_reachable` riflette il seam iniettato (True e False); `tts_voices` corretto (l'arabo assente → False); **il DTO non contiene segreti** (nessun campo password/DSN/token — verificato dalla struttura).
- **Check live ermetico**: il servizio usa il seam iniettato nei test (nessuna chiamata HTTP reale all'LLM).
- **Endpoint**: `GET /system-config` → **200** per admin; **403** per un ruolo senza `CONFIGURE_SYSTEM` (es. operatore/supervisore/auditor); un evento **`system_config_viewed`** è stato scritto nell'audit.
- **Frontend**: `getSystemConfig` mappa 200/401/403/error; il pannello rende le sezioni + il badge raggiungibile/non raggiungibile; degrado 401→login/403→forbidden/error→ritentabile, loading gated `!error`; nav «Configurazione» link reale; sezione dietro `ProtectedRoute`.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Fuga di segreti (password/DSN/token) | il DTO espone solo valori non-sensibili; verificato dai test; per costruzione nessun campo segreto |
| Indebolimento della sicurezza da pannello | **sola lettura**; guardrail/ambito/PII non nel DTO e non editabili (§2/§9) |
| Probe LLM lento/flaky blocca la pagina | check dietro seam, timeout breve, **fail-safe** (errore → non raggiungibile, non un 500) |
| Accesso da ruolo non autorizzato | `require_permission(CONFIGURE_SYSTEM)` (solo admin → 403); nav mostra la voce solo all'admin |
| Accesso non tracciato | `append_audit("system_config_viewed")` a ogni lettura |
| Test dipendenti da un LLM reale | seam iniettabile → test ermetici |
| 401 lascia stato ambiguo | `useApiError` → onUnauthorized + redirect |

## 8. Criteri di accettazione

- Backend: `compute_system_config` corretto (valori + `llm_reachable` dal seam + `tts_voices`; nessun segreto); `GET /system-config` 200 admin / 403 non autorizzati / `system_config_viewed` auditato; check live ermetico nei test. `pytest -q`, `ruff check .`, `mypy src` verdi.
- Frontend: client mappa gli status; il pannello rende le sezioni + badge raggiungibilità; degrado 401/403/error; nav link reale; rotta protetta. `vitest`, typecheck, lint, build verdi.
- Solo dipendenze open source permissive (nessuna nuova; `httpx` già presente). `frontend/` (kiosk) intatto. Nessuna nuova tabella/migrazione.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§6/§7.3/§9/§11). **Nessuna modifica al nucleo.** Nessun controllo di sicurezza esposto/indebolibile.
- **`STATO_TECNICO.md`**: da aggiornare con il modulo `system` (config non-segreta + check live LLM), l'endpoint `CONFIGURE_SYSTEM` + audit, il pannello admin, e l'avanzamento della roadmap (con questo il portale operatore copre tutti e quattro i ruoli §6: operatore, supervisore, amministratore, auditor).
- **Piano collegato:** scomposizione TDD (backend: `compute_system_config` + seam + i suoi casi → endpoint RBAC+audit; frontend: tipi+client → pannello → nav-link+rotta+integrazione).
