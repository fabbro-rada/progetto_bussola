# Spec di design — Sottosistema 20: Attività operatori (Supervisore)

**Progetto «Bussola»** · Sottosistema 20 (portale operatore · ruolo Supervisore · attività operatori) · *Design di riferimento per il piano collegato* · 2026-07-27

---

## 0. Cos'è questo documento

Spec di design della vista **attività operatori** per il ruolo **Supervisore** (§6): «vede lo stato di avanzamento e l'attività degli operatori; organizza il lavoro». È una **fetta verticale** (backend nuovo + frontend) come S15 (metriche). Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*. Si conforma a `CLAUDE.md` §2 (misura l'attività dello staff per il coordinamento, **non** è sorveglianza sulle persone detenute), §3 (locale, open source, solo azioni previste, fail-closed), §6 (ruolo **Supervisore**, `VIEW_OPERATOR_ACTIVITY`, privilegio minimo, **distinto dall'Auditor**; server autorità), §7.3 (accesso auditato), §9 (TDD, dati sintetici), §11 (codice inglese, stringhe UI esternalizzate).

Il registro di audit (S2) accumula fin dall'inizio le azioni di lavoro degli operatori. Il supervisore **non** ha `READ_AUDIT` (esclusivo dell'Auditor, §6): non può quindi riusare `/audit`. Questo sottosistema fornisce un endpoint **distinto**, gated da `VIEW_OPERATOR_ACTIVITY`, che deriva dall'audit un **riepilogo aggregato per operatore** — di coordinamento, non forense.

## 1. Contesto e scopo

Il supervisore coordina il reinserimento (§6): oltre alle metriche di qualità (S15), deve vedere **chi sta lavorando e quanto** per organizzare il lavoro. Questa vista risponde: per ciascun operatore, quante azioni di lavoro ha svolto (profili consultati, ricerche, matching eseguiti, export richiesti/scaricati) e quando è stato attivo l'ultima volta. È un riepilogo **aggregato** — non il log grezzo (quello è dell'Auditor).

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Backend `activity`**: `compute_operator_activity(conn)` che **aggrega** `audit.audit_log` per `actor`, contando le **azioni di lavoro**; endpoint `GET /operator-activity` dietro `VIEW_OPERATOR_ACTIVITY` (solo `supervisor`), con accesso **auditato** (`operator_activity_viewed`).
- **Le voci di attività:** per ogni attore — `profiles_viewed`, `profiles_searched`, `matchings_run`, `exports_requested`, `exports_downloaded` (conteggi) + `last_active` (ultima attività). Aggregato, anonimo rispetto alle persone detenute.
- **Frontend**: sezione `/activity` sotto la shell S11, dietro `ProtectedRoute` + ruolo supervisore; la voce di nav (placeholder S11) diventa **link reale** (`built`); pannello **sola-lettura** (tabella per-operatore); degrado 401/403/error; `operatorClient` esteso fail-closed.
- **i18n** italiano esternalizzato.

**Non-obiettivi (rimandati):**
- **Feed cronologico / drill-down per singolo operatore**: non ora (YAGNI; è più vicino al ruolo Auditor). Qui: riepilogo aggregato.
- **Accesso al log grezzo o alla tamper-verify**: **vietato** al supervisore — resta esclusivo dell'Auditor (§6). Questo endpoint **non** espone le voci di audit né la verifica catena.
- **Metriche di qualità dei profili** (n. colloqui, completezza): già S15 (sezione «Metriche»). Qui si misura l'**attività dello staff**, non la qualità dei profili.
- **Filtri/paginazione**: non previsti ora (il numero di operatori è piccolo per costruzione); un riepilogo completo sta in una schermata. Eventuali filtri = follow-up.

## 3. Decisioni di design (con motivazione)

1. **Endpoint distinto gated da `VIEW_OPERATOR_ACTIVITY`, non riuso di `/audit` (vincolo §6).** Il supervisore non ha `READ_AUDIT`; l'accesso al log grezzo resta dell'Auditor. *Perché §6:* i ruoli sono a privilegio minimo e separati; il supervisore ottiene solo ciò che gli serve (un riepilogo), non la traccia forense.

2. **Riepilogo aggregato per operatore (opzione approvata), non un feed.** Per attore: conteggi delle azioni di lavoro + ultima attività. *Perché §6:* «stato di avanzamento / organizza il lavoro» è una domanda di coordinamento («chi fa quanto»), non forense; un feed duplicherebbe il visore dell'Auditor. La forma aggregata tiene i due ruoli distinti.

3. **Solo le azioni di lavoro (opzione approvata).** Si contano `profile_viewed`, `profiles_searched`, `matching_run`, `export_requested`, `export_downloaded`. Si **escludono** login/logout/`password_changed` (auth, non lavoro), le azioni admin (`operator_created/…`) e supervisore (`metrics_viewed`, `export_approved/denied`), e gli eventi kiosk (`interview_section_confirmed`, `actor="kiosk"`). *Perché:* la vista misura il lavoro di reinserimento degli operatori; raggruppare su queste azioni esclude per costruzione kiosk e auth.

4. **Aggregato e anonimo per le persone (linea rossa §2/§5).** Le voci contengono **solo** username dello staff + conteggi + timestamp; **nessuno pseudonimo, nessuna PII, nessun dato o inferenza sulla persona detenuta**. *Perché §2:* misurare l'attività dello staff per coordinare **non** è sorveglianza sulle persone; il confine è netto.

5. **Accesso auditato (`operator_activity_viewed`).** La lettura emette un evento di audit (attore = username del supervisore), coerente con `metrics_viewed` (S15) e `profiles_searched`/`profile_viewed`. *Perché §7.3:* accountability sull'accesso ai dati aggregati. (Diversamente dall'Auditor, il cui read-only non si audita, §6: qui il supervisore è un principal operativo, non la garanzia stessa.)

6. **`operatorClient` esteso fail-closed + `useApiError`.** Come S12–S19: risultato tipizzato, 401→onUnauthorized+/login, 403→messaggio, error ritentabile, mai un throw. *Perché §3.*

7. **Fetta verticale in un'unica spec (opzione approvata).** Endpoint + pannello insieme (superficie piccola, come S15). Nessuna nuova tabella/migrazione.

## 4. Unità e confini

**Backend** (`backend/src/bussola/`):
- **`activity/service.py`** — `OperatorActivity` (pydantic: `actor, profiles_viewed, profiles_searched, matchings_run, exports_requested, exports_downloaded, last_active`) + `compute_operator_activity(conn) -> list[OperatorActivity]` (SQL `GROUP BY actor` con `COUNT(*) FILTER (WHERE action=…)` e `MAX(occurred_at)`, sulle sole azioni di lavoro, ordinato per `last_active DESC`).
- **`api/routers/activity.py`** — `GET /operator-activity` → `list[OperatorActivity]`, `Depends(require_permission(VIEW_OPERATOR_ACTIVITY))`, `append_audit(action="operator_activity_viewed", actor=<username>)`.
- **`api/app.py`** — include il router.

**Frontend** (`operator-portal/src/`):
- **`types.ts`** (estensione) — `OperatorActivity` + `OperatorActivityResult` (`ok{activity}` | unauthorized | forbidden | error).
- **`api/operatorClient`** (estensione) — `getOperatorActivity()` fail-closed.
- **`screens/activity/OperatorActivityPanel`** — tabella per-operatore sola-lettura; empty-state; degrado.
- **`rbac/nav`** — `activity` marcato `built`.
- **`App`** — rotta `/activity` annidata sotto `ProtectedRoute`/`AppShell`.
- **`i18n/locales/it`** (estensione) — gruppo `activity` (titolo, etichette colonne).

Confine: il backend legge dai dati esistenti (audit); il frontend dipende dal nuovo contratto `GET /operator-activity` e dallo scheletro S11. Server autorità (RBAC/403; audit).

## 5. Flusso e contratto HTTP

```
[supervisore] Nav «Attività operatori» → /activity
   GET /operator-activity  (require VIEW_OPERATOR_ACTIVITY; audit operator_activity_viewed)
      → 200 [OperatorActivity…]  (per attore: conteggi azioni di lavoro + last_active, ordinati per last_active DESC)
      → tabella per-operatore | empty-state
   401 → onUnauthorized + /login ; 403 → «non hai i permessi» ; rete/5xx → errore ritentabile
```

`OperatorActivity` = `{ actor: str, profiles_viewed: int, profiles_searched: int, matchings_run: int, exports_requested: int, exports_downloaded: int, last_active: datetime }`.

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**; backend `pytest` (DB di test, `db`/`app_conn`/`client`/`make_operator`), frontend `Vitest` + @testing-library/react (`operatorClient` fake). Priorità:
- **Backend `compute_operator_activity`**: 0 eventi → lista vuota; eventi misti seminati con `append_audit` → conteggi per attore corretti e `last_active` = ultimo timestamp; le azioni **non di lavoro** (login, `operator_created`, `metrics_viewed`) e gli eventi kiosk (`actor="kiosk"`, `interview_section_confirmed`) **non** compaiono/contano.
- **Endpoint**: `GET /operator-activity` → **200** per un supervisore; **403** per un ruolo senza `VIEW_OPERATOR_ACTIVITY` (es. operatore/auditor); un evento **`operator_activity_viewed`** è stato scritto nell'audit.
- **Privacy**: la risposta non contiene pseudonimi né dati per-persona (verificato dalla struttura di `OperatorActivity`).
- **Frontend**: `getOperatorActivity` mappa 200/401/403/error; il pannello rende le righe per-operatore + empty-state; degrado 401→login/403→forbidden/error→ritentabile, loading gated `!error`; nav «Attività operatori» link reale; sezione dietro `ProtectedRoute`.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Diventa sorveglianza sulle persone (§2) | aggregato per **staff**; nessuno pseudonimo/dato detenuto; verificato dai test |
| Sovrapposizione col ruolo Auditor | forma **aggregata** (conteggi), non feed; nessun accesso al log grezzo né tamper-verify |
| Accesso da ruolo non autorizzato | `require_permission(VIEW_OPERATOR_ACTIVITY)` lato server (403); nav mostra la voce solo al supervisore |
| Accesso non tracciato | `append_audit(action="operator_activity_viewed")` a ogni lettura |
| Conteggio di azioni non pertinenti (login, kiosk) | il GROUP BY è ristretto alle sole azioni di lavoro → esclude auth/admin/kiosk per costruzione |
| 401 lascia stato ambiguo | `useApiError` → onUnauthorized + redirect |

## 8. Criteri di accettazione

- Backend: `compute_operator_activity` corretto (0/misti; esclusioni; `last_active`); `GET /operator-activity` 200 supervisore / 403 non autorizzati / `operator_activity_viewed` auditato. `pytest -q`, `ruff check .`, `mypy src` verdi.
- Frontend: client mappa gli status; pannello rende le righe + empty; degrado 401/403/error; nav link reale; rotta protetta. `vitest`, typecheck, lint, build verdi.
- Solo dipendenze open source permissive (nessuna nuova). `frontend/` (kiosk) intatto. Nessuna nuova tabella/migrazione.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§6/§7.3/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con il modulo `activity` (aggregazione dell'audit per attore), l'endpoint `VIEW_OPERATOR_ACTIVITY` + audit, il pannello supervisore, e l'avanzamento della roadmap (resta solo admin-config, da scopare).
- **Piano collegato:** scomposizione TDD (backend: `compute_operator_activity` + i suoi casi → endpoint RBAC+audit; frontend: tipi+client → pannello → nav-link+rotta+integrazione).
