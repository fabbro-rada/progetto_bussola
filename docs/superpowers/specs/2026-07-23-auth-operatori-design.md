# Spec di design — Sottosistema 5: Auth & operatori

**Progetto «Bussola»** · Sottosistema 5 · *Design di riferimento per il piano collegato* · 2026-07-23

---

## 0. Cos'è questo documento

Spec di design del quinto sottosistema, nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (linee rosse), §3 (vincoli: locale, open source permissivo, budget nullo, privacy by design, prevenzione abusi), §6 (ruoli e accesso a privilegio minimo), §7.2 (accesso per ruoli, utenza autorizzata dalla Direzione), §7.3 (audit immutabile, autorizzazione), §9 (TDD, dati sintetici). Poggia su S2 (ruoli DB, schema segregati, audit append-only con hash-chain, `append_audit`).

## 1. Contesto e scopo

Realizza l'**autenticazione degli operatori e il controllo d'accesso basato sui ruoli (RBAC)**, con il **primo layer HTTP** del sistema. È il prerequisito del portale operatore (§7.2): un operatore è un *principal autenticato*; la persona detenuta resta solo uno pseudonimo, senza account. Da oggi ogni operazione rilevante ha un **attore identificato** che alimenta il campo `actor` del log di audit (S2).

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Account operatore**: modello, ciclo di vita (creazione, disabilitazione, riabilitazione, reset password), provisioning **dall'Amministratore** (nessuna auto-registrazione — §7.2).
- **Autenticazione a password** con hashing robusto; **sessioni server-side** con revoca immediata.
- **RBAC** sui quattro ruoli (§6): Operatore, Supervisore, Amministratore, Auditor.
- **Layer HTTP (FastAPI)** che espone **solo** endpoint di autenticazione/sessione/gestione account + middleware RBAC.
- **Audit di ogni evento auth** (login riuscito/fallito, logout, cambio password, creazione/disabilitazione/riabilitazione/reset account), con `details` **vincolato** (nessun testo libero, nessun PII) e **atomico** con l'operazione.
- **Bootstrap** del primo Amministratore via CLI, senza credenziali di default nel repo.

**Non-obiettivi (rimandati):**
- **Endpoint di business del portale** (richieste di lavoro, matching, consultazione profili, metriche, export) → Sottosistema «Portale operatore».
- **Gestione cookie httpOnly + CSRF, kiosk** → S7 (frontend). Qui il contratto API usa **bearer token**.
- **MFA/2FA** → Fase 2.
- **Reset password self-service via email** → Fase 2 (on-prem, nessuna infrastruttura email; il reset è guidato dall'Amministratore).

## 3. Decisioni di design (con motivazione)

1. **Confine: auth engine + API HTTP solo-auth.** Introduce il layer web (FastAPI) ma limitato agli endpoint auth/sessione/account + middleware RBAC. *Perché:* verticale auth completo e testabile (login → sessione → richiesta autorizzata → audit) senza trascinare le funzioni del portale (un sottosistema per piano).

2. **Sessioni server-side (token opaco + hash in DB).** Alla login si conia un token ad alta entropia; in DB si salva **solo l'hash** del token (come per le password); la sessione ha **scadenza assoluta** + **timeout d'inattività**, entrambi configurabili via env (default proposti: assoluta **12h**, idle **30 min**). *Perché §6/§3:* revoca **immediata** (disabilita account → cadono le sessioni; logout), adatta a on-prem single-box e al kiosk; una fuga del DB non consegna sessioni vive. JWT stateless scartato: la revoca richiederebbe una denylist che ne vanifica lo stateless.

3. **Password: argon2id.** Hashing con `argon2-cffi` (MIT). Le password non compaiono mai nei log. *Perché §3:* standard robusto, licenza permissiva.

4. **Provisioning dall'Amministratore, identità = username.** Nessuna auto-registrazione né email: l'Amministratore crea gli account (username assegnato + ruolo + password temporanea), che al primo accesso **devono** cambiare password. *Perché §7.2:* «utenza autorizzata dalla Direzione»; contesto carcerario → identità assegnata, non self-service.

5. **RBAC a privilegio minimo (§6).** Ruoli `operator`/`supervisor`/`admin`/`auditor`; un motore permessi (`ruolo → permessi`) con dipendenze FastAPI `require_role`/`require_permission`. *Perché §6:* accesso vincolato allo scopo. Questo sottosistema **applica** solo `manage_operators` (admin) + self-service; i permessi di business (profili, matching, metriche, audit-read) sono **dichiarati** ma applicati dai sottosistemi successivi.

6. **Fine-grained RBAC nell'app, non nel ruolo DB.** L'app si connette come `bussola_app` (S2) e decide chi-può-cosa a livello applicativo in base al ruolo dell'operatore autenticato. *Perché §6/S2:* i ruoli DB sono coarse (owner/app/auditor); il controllo per-operatore vive nell'app.

7. **Robustezza anti-abuso al login.** Errore **generico** su credenziali errate (nessuna user-enumeration), **verifica fittizia** su utente inesistente per pareggiare i tempi, **lockout** dopo ripetuti fallimenti (default proposti: **5 tentativi** consecutivi → blocco **15 min**; azzerato da reset/enable), configurabile via env. *Perché §3:* prevenzione dell'uso scorretto.

8. **Audit auth vincolato e atomico.** Ogni evento auth è appeso al log S2 con `actor`=username dell'operatore, `target_pseudonym`=null (i target sono operatori, non persone), `details`=whitelist strutturata (`event`, `target_operator`, `role` — mai testo libero/PII). L'operazione sull'account e il suo record di audit **committano nella stessa transazione**. *Perché §7.3/§9:* accountability senza fughe; «nessuna azione senza il suo record». Ciò affronta i follow-up S2 «details da vincolare» e «transazione unità-di-lavoro»: `append_audit` acquisisce una variante che **partecipa alla transazione del chiamante** (senza commit proprio).

9. **Bootstrap via CLI.** Un entrypoint (`python -m bussola.auth.bootstrap`) crea il primo Amministratore da input/variabili d'ambiente; **rifiuta** se un admin esiste già; nessuna credenziale di default nel repo. *Perché §3:* zero segreti versionati, esplicito e auditabile.

## 4. Unità e confini

Nuovo package **`bussola.auth`** (dominio, senza HTTP):
- `models.py` — Pydantic: `Operator`, enum `Role`, DTO di richiesta/risposta (`extra="forbid"`).
- `passwords.py` — `hash_password`/`verify_password` (argon2id) + `dummy_verify` (anti-timing).
- `accounts.py` — `AccountRepository`: create/disable/enable/reset_password/get/list sullo schema `auth`.
- `sessions.py` — `SessionStore`: create/lookup/revoke/revoke_all_for_operator; hashing del token, scadenza/idle.
- `rbac.py` — `Role`, mappa `ROLE_PERMISSIONS`, `has_permission(role, perm)`.
- `service.py` — `AuthService`: `login`, `logout`, `change_password`, `authenticate(token)`, orchestrando account+sessioni+audit **in un'unica transazione**.
- `bootstrap.py` — CLI del primo admin.

Nuovo package **`bussola.api`** (trasporto):
- `app.py` — factory dell'app FastAPI.
- `deps.py` — dipendenze: connessione DB, `current_operator` (dal bearer token), `require_role`/`require_permission`.
- `errors.py` — gestori d'errore uniformi (401/403/409/422) senza fughe.
- `routers/auth.py`, `routers/operators.py`.

Confine: `bussola.auth` dipende da `bussola.data` (connessione, audit). `bussola.api` dipende da `bussola.auth`. Nessuna logica di business del portale. Espone l'app FastAPI (unico ingresso HTTP) e `AuthService`.

## 5. Modello dati — migrazione `0004_auth.sql`

Nuovo schema `auth` (AUTHORIZATION `bussola_owner`):

- `auth.operator`: `id` (identità interna), `username` (unico), `display_name`, `password_hash`, `role`, `is_active`, `must_change_password`, `failed_attempts`, `locked_until`, `created_at`, `created_by`, `disabled_at`, `disabled_by`.
- `auth.session`: `id`, `token_hash` (SHA-256 del token opaco — **il token grezzo non è mai salvato**), `operator_id` (FK), `created_at`, `expires_at`, `last_seen_at`, `revoked_at`.

Privilegi: `bussola_app` → SELECT/INSERT/UPDATE su `auth.operator` e `auth.session` (l'app gestisce account e sessioni; il chi-può-cosa è applicato dall'RBAC dell'app). `bussola_auditor` → **nessun** accesso allo schema `auth`.

## 6. Flusso (login e richiesta autorizzata)

```
POST /auth/login {username, password}
   → cerca operator; se assente → dummy_verify + errore generico
   → se lockato (locked_until nel futuro) → errore generico
   → verifica password (argon2id)
        fallita → failed_attempts++ ; se soglia → locked_until ; audit(login_failed) ; errore generico
        ok → azzera failed_attempts ; crea sessione (token opaco, salva hash) ;
             audit(login_succeeded) ; ritorna token (+ must_change_password)
(ogni richiesta protetta) Authorization: Bearer <token>
   → authenticate(token): hash → lookup sessione valida (non scaduta/idle/revocata) e operator attivo
        no → 401
        sì → aggiorna last_seen_at ; inietta current_operator
   → require_role/require_permission: ruolo non abilitato → 403
POST /auth/logout → revoca la sessione corrente ; audit(logout)
Amministratore disabilita un operatore → is_active=false ; revoke_all_for_operator ; audit(operator_disabled)
```

Ogni mutazione d'account e il suo record di audit avvengono **nella stessa transazione**.

## 7. Strategia di test (§9)

TDD; **solo dati sintetici** (account fittizi vari per ruolo). Priorità alla tenuta:
- **RBAC**: per ogni ruolo, cosa può/non può fare (matrice); `manage_operators` solo admin; self-service per tutti gli autenticati.
- **Revoca**: disabilitare un operatore invalida subito le sue sessioni; logout invalida la sessione.
- **Lockout** dopo N fallimenti; sblocco su reset/enable.
- **No user-enumeration**: errore identico e tempi pareggiati per utente inesistente vs password errata.
- **Auth su ogni endpoint**: nessun endpoint protetto raggiungibile senza sessione valida.
- **Audit di ogni evento** (assert dell'append; `details` whitelist, niente PII; atomicità: fallimento a valle → nessun record parziale).
- **Password**: round-trip argon2id; il token di sessione è salvato solo come hash.
- **Bootstrap**: crea il primo admin; **rifiuta** se un admin esiste.

Via FastAPI `TestClient` + fixture DB condivise (S2, `tests/conftest.py`).

## 8. Criteri di accettazione

- Unit/integration verdi e deterministici: matrice RBAC, revoca su disable/logout, lockout, no-enumeration, auth su ogni endpoint, ogni evento auditato (con `details` vincolato) e atomico, bootstrap idempotente-al-primo-admin.
- Nessuna credenziale di default versionata; password mai nei log; token salvato solo come hash.
- `pytest`, `ruff check`, `ruff format --check`, `mypy` verdi.
- Dipendenze aggiunte solo a licenza permissiva (fastapi MIT, uvicorn BSD, argon2-cffi MIT), verificate al momento dell'aggiunta.

## 9. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Escalation di privilegi tra ruoli | RBAC centralizzato + test di matrice per ogni ruolo/azione |
| Sessione non revocabile alla disabilitazione | Sessioni server-side + `revoke_all_for_operator` su disable; test dedicato |
| User-enumeration / brute force | Errore generico, dummy-verify, lockout; test su tempi e messaggi |
| Fuga del DB → sessioni/password | Solo hash di password (argon2id) e di token di sessione salvati |
| Azione d'account senza audit | Operazione + audit nella stessa transazione; test di atomicità |
| `details` di audit con PII/testo libero | Whitelist strutturata al confine degli eventi auth |
| Credenziali di default nel repo | Bootstrap via CLI, nessun seed con credenziali note |
| Dipendenza a licenza non permissiva | Verifica licenza all'aggiunta (§3) |

## 10. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§6/§7.2/§7.3/§9). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con lo stack HTTP (FastAPI/uvicorn), argon2-cffi, il modello di sessione e RBAC, e i follow-up S2 affrontati (audit `details` vincolato, transazione unità-di-lavoro per gli eventi auth).
- **Piano collegato:** scomposizione eseguibile in TDD (sicurezza-first: RBAC, revoca, lockout, no-enumeration, audit prima di tutto).
