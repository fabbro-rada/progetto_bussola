# Spec di design — Sottosistema 14: Portale operatore — Amministrazione utenze

**Progetto «Bussola»** · Sottosistema 14 (portale operatore, sotto-progetto 4/5) · *Design di riferimento per il piano collegato* · 2026-07-27

---

## 0. Cos'è questo documento

Spec di design del **quarto sotto-progetto del portale operatore**: l'**amministrazione delle utenze** operatore. Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (nessun dato solo-lavoro qui; solo azioni previste), §3 (locale, open source, prevenzione abusi, solo azioni previste), §6 (ruolo **Amministratore** «gestisce la piattaforma, non il merito»; privilegio minimo), §7.2 (accesso per ruoli, utenza autorizzata dalla Direzione), §7.3 (audit immutabile, resistenza abusi), §9 (TDD, dati sintetici), §11 (codice inglese, stringhe UI esternalizzate). Si innesta sullo scheletro S11 (`operator-portal/`) e riusa i pattern S12/S13 (`operatorClient` esteso fail-closed, `useApiError`, nav-link `built`, sezione coesa sotto la shell). Consuma l'API S5: `GET /operators` → `Operator[]`, `POST /operators` → `{operator, temp_password}` (201), `POST /operators/{id}/disable` → 204, `POST /operators/{id}/enable` → 204, `POST /operators/{id}/reset-password` → `{temp_password}` (200). Tutti gli endpoint richiedono il permesso `MANAGE_OPERATORS` (solo ruolo `admin`).

## 1. Contesto e scopo

Con S11–S13 l'operatore accede, gestisce le richieste di lavoro con matching spiegabile e consulta i profili. Questo sotto-progetto aggiunge il pannello dell'**Amministratore** (§6): provisioning e gestione degli account operatore. È il modo in cui la Direzione «crea e disattiva le utenze» (§6, §7.2 «utenza autorizzata dalla Direzione»). L'Amministratore è un ruolo **tecnico-gestionale, distinto dall'uso dei profili per il lavoro**: qui non compaiono profili né dati solo-lavoro, solo account.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Sezione «Operatori»** sotto la shell S11, dietro `ProtectedRoute` + ruolo admin (`MANAGE_OPERATORS`), rotta `/operators`. La voce di nav (placeholder S11) diventa un **link reale** (flag `built`).
- **Elenco** operatori: utente, nome, ruolo, stato (attivo/disattivo), indicatore «deve cambiare password».
- **Creazione** operatore: soli campi `CreateOperatorRequest` (username, display_name, role). Alla creazione (201) il server restituisce una **password temporanea in chiaro**, mostrata **una sola volta** in una **modale** (vedi §3.3).
- **Disabilita/Riabilita** operatore (cambio stato, 204) e **Reset-password** (200 → nuova temp-password nella stessa modale una-tantum).
- **Conferma esplicita** (con nome operatore) prima di disabilita/riabilita e reset-password.
- **Guardia anti-auto-lockout**: sulla riga dell'admin loggato, «Disabilita» e «Reset password» sono disattivate (il backend non ha una guardia propria: disable/reset revocano subito le sessioni → auto-lockout immediato).
- **`operatorClient` esteso** fail-closed col Bearer; 401→`unauthorized` (→ logout via `useApiError`), 403→`forbidden`, rete/5xx→`error`.
- **i18n** italiano esternalizzato, incluse le **etichette dei ruoli** e i testi di modale/conferme/avvisi.

**Non-obiettivi (rimandati):**
- **Modifica di un operatore esistente** (rinomina display_name, cambio ruolo): **nessun endpoint backend** → decisione di prodotto (utente) di restare dentro gli endpoint esistenti. Correzione di un ruolo errato = disabilita + ricrea. Un endpoint di aggiornamento è un **follow-on backend** annotato in §14.
- **Cancellazione** di un account: per §7.3 (accountability) non si cancella, si **disabilita** (reversibile). Nessun endpoint di delete.
- **Metriche, attività operatori, export, config di sistema, audit**: altri ruoli/sotto-progetti (5) e follow-on backend.
- **Gestione della propria password**: già coperta da S11 (`ChangePassword`); qui non si duplica.

## 3. Decisioni di design (con motivazione)

1. **Sezione coesa elenco+crea+azioni, innestata sulla shell S11.** Rotta `/operators`; nessuna vista di dettaglio per-operatore (le azioni vivono sulla riga). *Perché §6/§7.2:* «crea e disattiva le utenze»; superficie piccola, stesso pattern coeso di S12/S13.

2. **Layout: tabella al centro + «Nuovo operatore» a comparsa (opzione A approvata).** L'elenco è la vista primaria; la creazione è un'azione occasionale, tenuta fuori dai piedi finché non serve (pannello inline che si apre/chiude). *Perché:* coerenza con le altre sezioni; l'admin di solito guarda/gestisce l'elenco esistente.

3. **Password temporanea in una modale una-tantum (opzione A approvata).** Create e reset restituiscono una **credenziale in chiaro**. La UI la mostra in una **finestra modale** con password in evidenza (monospazio), pulsante **Copia**, avviso «mostrata una sola volta — consegnala ora», e chiusura con gesto esplicito («Ho copiato, chiudi»). *Perché §3/§7.3:* impossibile da mancare, richiede un'azione consapevole; la credenziale **non è persistita né loggata**, vive solo nello stato del componente finché la modale è aperta ed è **azzerata alla chiusura**; il copy usa `navigator.clipboard` dietro un **seam mockabile**, con degrado (la password resta comunque leggibile a schermo se la clipboard non è disponibile).

4. **Conferma per disabilita/riabilita e reset (opzione approvata).** Un dialog di conferma con il nome dell'operatore precede queste azioni. *Perché §3 (prevenzione abusi/errori):* disable e reset **revocano immediatamente le sessioni** dell'operatore (lo disconnettono); un clic accidentale sulla riga sbagliata ha conseguenze reali.

5. **Guardia anti-auto-lockout lato UI (opzione approvata).** Sulla riga dell'admin loggato (match per `id` da `useAuth().operator`), «Disabilita» e «Reset password» sono **disattivate** con tooltip esplicativo. *Perché:* il backend non ha guardia propria (disable/reset di sé → revoca delle proprie sessioni → auto-lockout); la UI toglie il footgun ovvio. **Il server resta l'autorità**: questa è difesa-in-profondità UX, non un controllo di sicurezza (che vive lato server).

6. **`operatorClient` esteso fail-closed + `useApiError`.** Come S12/S13: risultati tipizzati, Bearer, 401→onUnauthorized+/login, 403→forbidden, error ritentabile, mai un throw. *Perché §3:* solo azioni previste, nessuno stato autenticato ambiguo.

7. **Rotta auth-gated, RBAC lato server.** `/operators` è dietro `ProtectedRoute` (sessione valida + gate cambio-password S11) ma non ha un role-gate client-side; il **server impone `MANAGE_OPERATORS`** (403→«non hai i permessi») e la nav mostra la voce solo all'admin. *Perché §6:* «il server resta l'autorità»; coerente con S13. Un role-gate client-side sarebbe solo UX (follow-up §14).

8. **Re-fetch dopo ogni mutazione.** Dopo create/disable/enable/reset la UI ri-carica l'elenco, così stato e indicatore «deve cambiare password» restano coerenti col server. *Perché:* fonte di verità unica (il server), nessuno stato ottimistico divergente.

## 4. Unità e confini

Sotto `operator-portal/src/`:
- **`api/operatorClient`** (estensione) — `listOperators()`, `createOperator(body)`, `disableOperator(id)`, `enableOperator(id)`, `resetPassword(id)`; risultati tipizzati; Bearer; fail-closed.
- **`types.ts`** (estensione) — `CreateOperatorRequest`, `CreatedOperator`, `ResetResponse`, e le result-union (`ListOperatorsResult`, `CreateOperatorResult`, `MutateOperatorResult`, `ResetPasswordResult`). `Operator`/`Role` già esistono e combaciano col backend (`id, username, display_name, role, is_active, must_change_password`).
- **`screens/operators/OperatorList`** — tabella + pannello di creazione a comparsa + azioni per riga; orchestrazione fetch/re-fetch, apertura modale/conferme.
- **`screens/operators/CreateOperatorForm`** — form dei soli campi `CreateOperatorRequest`.
- **`screens/operators/TempPasswordModal`** — modale una-tantum per la temp-password (crea + reset).
- **`screens/operators/ConfirmDialog`** — conferma azione con nome operatore (annulla/conferma).
- **`rbac/nav`** — `operators` marcato `built`.
- **`App`** — rotta `/operators` annidata sotto `ProtectedRoute`/`AppShell`.
- **`i18n/locales/it`** (estensione) — stringhe della sezione + etichette ruolo + testi modale/conferme/avvisi.

Confine: dipende solo dal contratto HTTP S5 e dallo scheletro S11/pattern S12–S13. Il server resta l'autorità (RBAC/403; audit di ogni azione).

## 5. Flusso (una gestione utenze)

```
[admin] Nav → «Operatori» → /operators
   GET /operators → Operator[] → tabella (utente · nome · ruolo · stato · badge «deve cambiare pwd»)
   «+ Nuovo operatore» → pannello inline (username, display_name, role)
      «Crea» → POST /operators → 201 {operator, temp_password}
         → MODALE una-tantum (temp_password + Copia + avviso) → «Ho copiato, chiudi» (azzera) → re-fetch lista
   riga → «Disabilita» → CONFERMA (nome) → POST /operators/{id}/disable → 204 → re-fetch
   riga → «Riabilita»  → CONFERMA (nome) → POST /operators/{id}/enable  → 204 → re-fetch
   riga → «Reset password» → CONFERMA (nome) → POST /operators/{id}/reset-password → 200 {temp_password}
         → MODALE una-tantum (nuova temp_password) → chiudi (azzera) → re-fetch
   riga dell'admin loggato → «Disabilita»/«Reset password» DISATTIVATE (tooltip anti-auto-lockout)
   401 in qualunque momento → onUnauthorized + /login («sessione scaduta») ; 403 → «non hai i permessi» ; rete/5xx → errore ritentabile
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici** (operatori finti). Vitest + @testing-library/react; `operatorClient` fake iniettato; seam clipboard mockabile. Priorità:
- **Client**: i 5 metodi inviano la shape corretta (path/metodo/body) col Bearer; mapping 201→ok, 204→ok, 200→ok{temp_password}, 401→unauthorized, 403→forbidden, rete/5xx→error; mai un throw.
- **Elenco**: rende le righe (utente/nome/ruolo tradotto/stato); l'azione dipende dallo stato (attivo→«Disabilita», disattivo→«Riabilita»); badge «deve cambiare password» quando `must_change_password`.
- **Creazione**: il form invia i soli 3 campi; su 201 apre la **modale** con la temp-password e **ri-carica** la lista.
- **Modale temp-password**: mostra la password; «Copia» chiama il seam clipboard; «Ho copiato, chiudi» chiude e **azzera** lo stato (la password non resta nel DOM).
- **Conferme**: disable/enable/reset chiedono conferma (con nome); **Annulla non chiama il client**; Conferma chiama l'endpoint giusto.
- **Auto-lockout**: sulla riga dell'admin loggato le azioni «Disabilita» e «Reset password» sono disabilitate.
- **Reset**: su 200 apre la modale con la **nuova** temp-password.
- **Degrado**: 401→logout+redirect; 403→«non hai i permessi»; error→messaggio ritentabile.
- **Nav/RBAC**: «Operatori» è un link reale; la sezione è dietro `ProtectedRoute`.
- **Privacy**: nessun dato solo-lavoro/PII in questa sezione (verificato dalla struttura dei dati finti: solo campi account).

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Fuga della temp-password (persistita/loggata/lasciata a schermo) | modale una-tantum; stato locale azzerato alla chiusura; mai in log; copy via seam; nessuna persistenza |
| Clic accidentale che disconnette un operatore | conferma esplicita con nome prima di disable/enable/reset |
| Admin che si auto-blocca (self-disable/reset) | azioni disattivate sulla propria riga (UX); il server resta l'autorità |
| Enumerazione/gestione da non-admin | RBAC lato server (403); nav mostra la voce solo all'admin; rotta dietro `ProtectedRoute` |
| Stato divergente dopo una mutazione | re-fetch dell'elenco dopo ogni azione (fonte di verità = server) |
| 401 su una chiamata lascia stato ambiguo | `useApiError` → onUnauthorized + redirect |

## 8. Criteri di accettazione

- Unit (fake client) verdi e deterministici: i 5 metodi inviano la shape corretta e mappano gli status; elenco con azioni per stato + badge; creazione invia i 3 campi, apre la modale, ricarica; modale mostra/azzera la temp-password e il copy chiama il seam; conferme (annulla non chiama, conferma sì); auto-lockout disattiva le azioni sulla propria riga; reset apre la modale con la nuova pwd; degrado 401/403/error; nav link reale.
- Il flusso `elenco → crea → modale → ricarica` e `elenco → azione → conferma → ricarica` è percorribile col fake client.
- `vitest`, typecheck, lint, build verdi. Solo dipendenze open source permissive (nessuna nuova prevista). `frontend/` (kiosk) intatto.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§6/§7.2/§7.3/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con la sezione amministrazione utenze del portale, l'estensione `operatorClient`, la modale temp-password una-tantum, le conferme, la guardia anti-auto-lockout, e l'avanzamento della roadmap (sotto-progetto 5 + follow-on backend metriche/export/edit-operatore).
- **Piano collegato:** scomposizione TDD (types + client 5 metodi; poi elenco + azioni per stato + guardia auto-lockout; poi form di creazione + modale temp-password + conferme; infine nav-link + composizione rotta + integrazione).
