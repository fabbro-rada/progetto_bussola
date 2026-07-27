# Spec di design — Sottosistema 15: Portale operatore — Metriche di qualità

**Progetto «Bussola»** · Sottosistema 15 (portale operatore, sotto-progetto 5a/5 · metriche) · *Design di riferimento per il piano collegato* · 2026-07-27

---

## 0. Cos'è questo documento

Spec di design del **primo pezzo del quinto sotto-progetto del portale operatore**: le **metriche minime di qualità** (§7.2). Il sotto-progetto 5 è stato **decomposto** in **5a — Metriche** (questo documento) e **5b — Export con autorizzazione** (spec successiva), perché sono funzionalità indipendenti con ruoli e complessità diversi. Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (le metriche misurano il sistema, non le persone: nessun punteggio/profilazione per-persona), §3 (locale, open source, solo azioni previste, fail-closed), §6 (ruolo **Supervisore** «vede lo stato di avanzamento e le metriche di qualità»; privilegio minimo), §7.2 (metriche minime: numero di colloqui completati, completezza dei profili), §7.3 (accesso auditato), §9 (TDD, dati sintetici), §11 (codice inglese, stringhe UI esternalizzate).

È una **fetta verticale sottile**: backend nuovo (servizio metriche + endpoint) **e** frontend (pannello supervisore), in un unico ciclo. Si innesta sul backend esistente (schema `profiles`/`matching`/`audit`, RBAC S5) e sullo scheletro S11 del portale (`operator-portal/`, pattern S12–S14).

## 1. Contesto e scopo

Il portale ha oggi le tre sezioni operatore (richieste+matching S12, profili S13, utenze S14). Manca il pannello del **Supervisore** (§6): la visione d'insieme dell'avanzamento e della qualità. Questo sotto-progetto fornisce le **metriche minime** (§7.2): quanti colloqui sono stati completati e quanto sono completi i profili — più pochi conteggi di contesto — per «capire se il sistema funziona e preparare la base per il report» (§7.2). È il primo uso del ruolo Supervisore e la prima superficie che richiede **backend nuovo** (finora S9–S14 erano solo frontend su backend esistente).

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Backend `metrics`**: un servizio che calcola metriche **aggregate e anonime** interrogando i dati esistenti; un endpoint `GET /metrics` dietro il permesso `VIEW_METRICS` (solo `supervisor`), con l'accesso **auditato** (`metrics_viewed`).
- **Le metriche minime (§7.2):**
  - `total_profiles` — numero di profili lavorativi esistenti.
  - `completed_profiles` — numero di profili **completi** (tutte le sezioni-chiave presenti).
  - `average_completeness` — completezza media (frazione 0–1 di sezioni-chiave popolate, mediata su tutti i profili; 0 se non ci sono profili).
  - `total_job_requests` — numero di richieste di lavoro.
  - `matching_runs` — numero di esecuzioni di matching (dagli eventi `matching_run` dell'audit).
- **Frontend**: sezione `/metrics` sotto la shell S11, dietro `ProtectedRoute` + ruolo supervisore; la voce di nav (placeholder S11) diventa **link reale** (`built`); pannello **sola-lettura** con i numeri e la completezza media come percentuale; degrado 401/403/error; `operatorClient` esteso fail-closed.
- **i18n** italiano esternalizzato.

**Non-obiettivi (rimandati):**
- **Export dei dati/esiti** → **sotto-progetto 5b** (spec successiva; export con autorizzazione, §7.3).
- **Attività degli operatori** (§6 «l'attività degli operatori»): pannello supervisore separato / follow-on; qui solo le metriche di qualità.
- **Reportistica aggregata avanzata / serie storiche / grafici** → **Fase 2** (§8 «esportazione avanzata e reportistica aggregata e anonima»). Qui: numeri istantanei, nessun grafico, nessuna storicizzazione.
- **Metriche per-persona / breakdown per pseudonimo**: **vietato** (§2). Solo aggregati.
- **Nuovo evento «interview_completed»**: escluso per scelta (approvata) — «colloqui completati» è **derivato dal profilo**, senza modificare il motore colloquio/kiosk (S4/S8) già mergiato.

## 3. Decisioni di design (con motivazione)

1. **«Colloqui completati» e «completezza» derivati dal profilo, non da un nuovo evento (opzione approvata).** Non esiste un evento persistito «colloquio completato» (il profilo è salvato per-sezione; lo stato «completed» vive solo in memoria nella sessione S8). Invece di modificare S4/S8 (sottosistemi mergiati, regola del nucleo §0), si deriva tutto dal profilo salvato:
   - **Completezza di un profilo** = frazione di **sezioni-chiave popolate** su 5: **lingue, competenze, esperienze, aspirazioni, formazione desiderata**. «Popolata» = array non vuoto; per **aspirazioni** = oggetto con almeno un campo valorizzato (interessi, disponibilità o vincoli). `digital_literacy` e note operative sono **supplementari** ed escluse dal conteggio.
   - **Profilo completo** = completezza 100% (tutte e 5 le sezioni-chiave presenti). `completed_profiles` = quanti profili sono completi.
   *Perché §7.2 + §0:* copre «numero di colloqui completati + completezza» con una definizione onesta e stabile, senza toccare il motore già validato.

2. **Aggregato e anonimo per costruzione (linea rossa §2/§5).** Il servizio produce **solo** conteggi e medie sull'intera popolazione; **nessun** endpoint o campo per-pseudonimo, nessun dato identificante. *Perché §2:* le metriche non devono mai diventare profilazione o punteggio della persona. Con pochissimi profili l'aggregato resta comunque non identificante (nessuno pseudonimo esposto).

3. **Ruolo Supervisore, `VIEW_METRICS`, server autorità.** L'endpoint è dietro `require_permission(VIEW_METRICS)`; la rotta frontend è solo **auth-gated** (RBAC imposto dal server → 403), la nav mostra la voce solo al supervisore. *Perché §6:* il supervisore «vede lo stato di avanzamento, le metriche di qualità»; privilegio minimo; coerente col pattern S13/S14.

4. **Accesso auditato (`metrics_viewed`).** Ogni lettura delle metriche emette un evento di audit (attore = username del supervisore), come per `profiles_searched`/`profile_viewed`. *Perché §7.3:* accountability sull'accesso ai dati aggregati.

5. **Fetta verticale in un'unica spec (opzione approvata).** Backend endpoint + pannello frontend insieme: la superficie è piccola (pochi numeri + un pannello sola-lettura) e sta in un solo ciclo/PR. *Perché:* coesione della funzionalità; niente contratto HTTP «a metà» tra due merge.

6. **Nessuna nuova tabella/migrazione; letture aggregate.** Il servizio interroga `profiles.work_profile`, `matching.job_request` e `audit.audit_log` (grant `SELECT` di `bussola_app` già presenti). *Perché §3 budget/semplicità:* i dati ci sono già; le metriche sono una vista, non nuovo stato.

7. **Numeri istantanei, nessun grafico (YAGNI).** Il pannello mostra i valori correnti come card + la completezza media in percentuale. Serie storiche, grafici e reportistica avanzata sono Fase 2 (§8). *Perché:* «metriche minime» (§7.2).

## 4. Unità e confini

**Backend** (`backend/src/bussola/`):
- **`metrics/service.py`** — `compute_metrics(conn) -> Metrics`: query SQL aggregate (conteggi + completezza calcolata sul JSONB dei profili). Nessuno stato, nessuna scrittura sui dati.
- **`metrics/models.py`** (o nello stesso `service.py`) — `Metrics` (pydantic): `total_profiles`, `completed_profiles`, `average_completeness` (float 0–1), `total_job_requests`, `matching_runs`.
- **`api/routers/metrics.py`** — `GET /metrics` → `Metrics`, `Depends(require_permission(VIEW_METRICS))`, `append_audit(action="metrics_viewed", actor=<username>, commit=...)`.
- **`api/app.py`** — include il router.

**Frontend** (`operator-portal/src/`):
- **`types.ts`** (estensione) — `Metrics` + `MetricsResult` (`ok{metrics}` | `unauthorized` | `forbidden` | `error`); estende `OperatorClient`.
- **`api/operatorClient`** (estensione) — `getMetrics()` fail-closed col Bearer (401→unauthorized, 403→forbidden, else→error).
- **`screens/metrics/MetricsPanel`** — pannello sola-lettura: card coi numeri + completezza media come %; `useApiError` per il 401; loading gated `!error`.
- **`rbac/nav`** — `metrics` marcato `built`.
- **`App`** — rotta `/metrics` annidata sotto `ProtectedRoute`/`AppShell`.
- **`i18n/locales/it`** (estensione) — gruppo `metrics` (titolo, etichette delle 5 metriche, formato percentuale).

Confine: il backend legge dai dati esistenti; il frontend dipende dal nuovo contratto `GET /metrics` e dallo scheletro S11. Il server resta l'autorità (RBAC/403; audit).

## 5. Flusso (una consultazione delle metriche)

```
[supervisore] Nav → «Metriche» → /metrics
   GET /metrics  (require VIEW_METRICS; audit metrics_viewed)
      → 200 Metrics { total_profiles, completed_profiles, average_completeness, total_job_requests, matching_runs }
      → pannello: card coi numeri + «completezza media: NN%»
   401 → onUnauthorized + /login («sessione scaduta») ; 403 → «non hai i permessi» ; rete/5xx → errore ritentabile
```

Calcolo (backend, concettuale): per ogni profilo, `sezioni_popolate / 5`; `average_completeness` = media di questi valori (0 se nessun profilo); `completed_profiles` = quanti hanno valore 1.0; `total_profiles` = righe; `total_job_requests` = righe `job_request`; `matching_runs` = `COUNT` degli eventi audit con `action='matching_run'`.

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**. Backend: `pytest` (servizio + endpoint, DB di test). Frontend: `Vitest` + @testing-library/react, `operatorClient` fake iniettato. Priorità:

**Backend**
- `compute_metrics` con **0 profili** → `total_profiles=0`, `completed_profiles=0`, `average_completeness=0.0` (nessuna divisione per zero).
- `compute_metrics` con profili **misti** (uno completo, uno parziale) → `total_profiles`/`completed_profiles` corretti; `average_completeness` = media attesa; un profilo con tutte e 5 le sezioni conta come completato, uno con alcune vuote no.
- `total_job_requests` e `matching_runs` riflettono le righe/eventi sintetici inseriti.
- Endpoint `GET /metrics`: **200** per un supervisore autorizzato; **403** per un ruolo senza `VIEW_METRICS` (es. operatore); un evento **`metrics_viewed`** è stato scritto nell'audit.

**Frontend**
- `getMetrics()` mappa 200→ok{metrics}, 401→unauthorized, 403→forbidden, rete/5xx→error; mai un throw; Bearer inviato.
- Il pannello rende i cinque numeri e la completezza media come percentuale (es. `0.6` → «60%»).
- Degrado: 401→logout+redirect; 403→«non hai i permessi»; error→messaggio ritentabile; loading gated `!error` (nessuno spinner perenne sotto errore).
- Nav/RBAC: «Metriche» è un link reale; la sezione è dietro `ProtectedRoute`.
- Privacy: la risposta non contiene pseudonimi né dati per-persona (verificato dalla struttura di `Metrics`).

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Le metriche diventano profilazione per-persona (§2) | `Metrics` è solo aggregato; nessun endpoint/campo per-pseudonimo; verificato dai test |
| «Completati» ambiguo senza evento dedicato | definizione esplicita e stabile: completezza 100% sulle 5 sezioni-chiave (documentata qui) |
| Divisione per zero con 0 profili | ramo esplicito → `average_completeness=0.0` (test dedicato) |
| Accesso non autorizzato | `require_permission(VIEW_METRICS)` lato server (403); nav mostra la voce solo al supervisore; rotta dietro `ProtectedRoute` |
| Accesso non tracciato | `append_audit(action="metrics_viewed")` a ogni lettura |
| 401 lascia stato ambiguo | `useApiError` → onUnauthorized + redirect |

## 8. Criteri di accettazione

- Backend: `compute_metrics` corretto sui casi (0 profili; misti; completo vs parziale; conteggi di contesto); `GET /metrics` 200 per supervisore, 403 per ruolo non autorizzato, `metrics_viewed` auditato. `pytest`, `ruff`, `mypy` verdi.
- Frontend: client mappa gli status; il pannello rende numeri + percentuale; degrado 401/403/error; nav link reale; rotta protetta. `vitest`, typecheck, lint, build verdi.
- Solo dipendenze open source permissive (nessuna nuova prevista). `frontend/` (kiosk) intatto. Nessuna nuova tabella/migrazione.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§6/§7.2/§7.3/§9/§11). **Nessuna modifica al nucleo.** «Colloqui completati» derivato dal profilo: nessuna modifica a S4/S8.
- **`STATO_TECNICO.md`**: da aggiornare con il modulo `metrics` (servizio + endpoint + audit `metrics_viewed`), la definizione di completezza (5 sezioni-chiave), il pannello supervisore, e l'avanzamento della roadmap (5b export + follow-on: attività operatori, reportistica Fase 2).
- **Piano collegato:** scomposizione TDD (backend: servizio `compute_metrics` con i suoi casi → endpoint RBAC+audit; frontend: tipi+client → pannello → nav-link+rotta+integrazione).
- **Sotto-progetto 5b (successivo):** Export con autorizzazione (§7.3), spec separata.
