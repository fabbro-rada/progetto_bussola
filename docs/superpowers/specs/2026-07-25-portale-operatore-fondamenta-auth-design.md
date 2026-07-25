# Spec di design — Sottosistema 11: Portale operatore — Fondamenta + Auth

**Progetto «Bussola»** · Sottosistema 11 (portale operatore, sotto-progetto 1/5) · *Design di riferimento per il piano collegato* · 2026-07-25

---

## 0. Cos'è questo documento

Spec di design del **primo sotto-progetto del portale operatore**: le **fondamenta e l'autenticazione**. Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (linee rosse, ambito, accesso vincolato allo scopo), §3 (locale, open source permissivo, prevenzione abusi, azioni solo tra quelle previste), §6 (ruoli e accesso a privilegio minimo), §7.2 (accesso per ruoli, utenza autorizzata dalla Direzione), §7.3 (audit, resistenza agli abusi), §9 (TDD, dati sintetici), §11 (codice inglese, stringhe UI esternalizzate i18n). Consuma l'**API auth di S5**: `POST /auth/login` → `{token, operator, must_change_password}`; `GET /auth/me` → `Operator`; `POST /auth/logout` (204); `POST /auth/change-password` (204). Autenticazione via header `Authorization: Bearer <token>` (S5 `current_operator`/`raw_bearer`).

**Il portale operatore è ampio** ed è stato scomposto in sotto-progetti, ciascuno con il proprio ciclo spec→piano→TDD: **(1) Fondamenta + Auth (questo)**, (2) flusso matching (richieste di lavoro + matching spiegabile), (3) consultazione profili, (4) amministrazione utenze, (5) metriche + export (con il follow-on backend). Questo documento copre **solo (1)**.

## 1. Contesto e scopo

Il backend operatore (S5 auth/RBAC, S6 richieste/matching/profili) è pronto ma **senza volto per l'operatore**. Questo sotto-progetto costruisce le **fondamenta dell'app operatore**: l'app separata, l'autenticazione (login, sessione, cambio password obbligatorio, logout), e la **shell autenticata con navigazione per ruolo** su cui i sotto-progetti successivi innesteranno le sezioni. È l'accesso «vincolato allo scopo e tracciabile» del §7.2: nessuno vede né fa nulla senza login e senza il ruolo adatto.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **App operatore separata**: nuovo progetto Vite+React+TS, distinto dal kiosk (modelli di sicurezza/deployment diversi — vedi §3.1), con **react-router** (multi-vista, deep-link).
- **Login**: `POST /auth/login` → token Bearer in **sessionStorage**; `operatorClient` isolato lo inietta su ogni richiesta.
- **Gate «cambia password obbligatorio»**: se `must_change_password`, si forza il cambio (`POST /auth/change-password`) prima di qualunque altra vista — *chiude il follow-up S5* (il server non lo impone).
- **Sessione al reload**: `GET /auth/me` riallinea l'operatore se il token in sessionStorage è ancora valido; altrimenti → login.
- **Logout**: `POST /auth/logout` + pulizia del token.
- **Shell RBAC (§6)**: navigazione mostrata in base al `role` dell'operatore (scheletro; le pagine delle sezioni arrivano nei sotto-progetti successivi).
- **Degrado/errori come segnali**: 401 → logout + login con avviso «sessione scaduta»; 403 → «non autorizzato»; rete/5xx → errore ritentabile. Nessuna azione fuori da quelle previste (§3).
- **i18n** (§11): stringhe UI esternalizzate in un catalogo **italiano**, predisposto a estendersi.

**Non-obiettivi (rimandati ai sotto-progetti successivi):**
- **Sezioni feature**: richieste di lavoro, matching spiegabile, consultazione profili, gestione utenze, metriche, export → sotto-progetti 2–5.
- **Endpoint metriche/export**: non esistono ancora (follow-on backend, sotto-progetto 5).
- **TLS interno / deployment LAN** → produzione (STATO_TECNICO §12).
- **Cookie httpOnly per il token** → richiederebbe una modifica a S5 (oggi il login restituisce il token nel body e il server legge il Bearer); eventuale hardening futuro.

## 3. Decisioni di design (con motivazione)

1. **App separata in `operator-portal/` (sibling di `frontend/` e `backend/`).** Il kiosk occupa già `frontend/`; il portale è un'app Vite indipendente con proprio `package.json`/bundle. *Perché §3/§6:* il kiosk è anonimo, token-dispositivo, localhost blindato; il portale è **autenticato** (login Bearer, ruoli), su LAN/TLS in produzione — due modelli che non devono coabitare nello stesso bundle. *Alternativa scartata:* ristrutturare `frontend/` in workspace `frontend/{kiosk,operator}` — invasiva sul kiosk già mergiato, non giustificata per il pilota. *Riuso:* i pattern (setup i18n, gate di test) sì; il bundle no.

2. **react-router-dom (MIT), non la macchina a stati del kiosk.** Il portale è multi-vista con deep-link/back/bookmark; il router è lo strumento adatto. *Perché §3:* MIT, permissivo; nuova dipendenza giustificata (il kiosk non ne aveva bisogno perché era un flusso lineare monouso). Rotte: `/login`, `/change-password` (gate), `/` (home), e — nei sotto-progetti successivi — `/job-requests`, `/profiles`, ecc. Un `ProtectedRoute` verifica autenticazione + gate.

3. **Token Bearer in sessionStorage, `operatorClient` isolato.** Il login restituisce il token nel body; la SPA lo conserva in **sessionStorage** (sopravvive al reload della scheda, sparisce alla chiusura) e lo invia come `Authorization: Bearer`. *Perché §3/§6:* equilibrio sicurezza/UX per staff su LAN, con scadenza assoluta+idle e revoca lato S5; i componenti non conoscono `fetch`, solo il client.

4. **Gate «cambia password obbligatorio» — chiude il follow-up S5.** Su `must_change_password` (dal login o da `/me`), il `ProtectedRoute` reindirizza a `/change-password` e blocca ogni altra vista finché il cambio non riesce. *Perché §4/§7.3:* la temp password ad alta entropia va cambiata prima di operare; il server non lo impone (follow-up S5), quindi lo impone la UI.

5. **Degrado come segnali chiari.** `operatorClient` mappa: **401** (sessione scaduta/revocata) → pulisce il token, `sessione scaduta`, torna al login; **403** (permesso mancante) → «non autorizzato»; rete/5xx → errore ritentabile. *Perché §3:* il portale esegue solo azioni previste e non lascia stati ambigui.

6. **Shell RBAC guidata dal ruolo (§6).** La navigazione riflette il `role`: **operator** → Richieste di lavoro · Matching · Profili · Export; **supervisor** → Metriche · Attività operatori; **admin** → Gestione utenze · Configurazione; **auditor** → Log di audit (sola lettura). *Perché §6:* privilegio minimo, accesso vincolato allo scopo; è UX (il server resta l'autorità e risponde 403). In #1 le voci sono lo scheletro; ogni sotto-progetto successivo registra la propria pagina.

7. **i18n italiano esternalizzato (§11).** Stringhe UI in un catalogo `it` (react-i18next), nessuna stringa hard-coded; gli operatori sono staff (l'italiano basta per il pilota) ma l'infrastruttura resta estendibile.

## 4. Unità e confini

Nuova cartella `operator-portal/` (Vite+React+TS). Unità con responsabilità singola:
- **`src/api/operatorClient`** — chiamate S5 (`login(username,password)`, `me()`, `logout()`, `changePassword(old,new)`); inietta `Authorization: Bearer`; mappa gli esiti in risultati tipizzati (`ok | unauthorized(401) | forbidden(403) | error`). Non conosce React.
- **`src/auth/session`** — lettura/scrittura/pulizia del token in sessionStorage; `AuthProvider`/`useAuth` (contesto: `operator | null`, `login`, `logout`, `mustChangePassword`, stato di caricamento iniziale via `me()`).
- **`src/auth/ProtectedRoute`** — richiede autenticazione; se `mustChangePassword` reindirizza a `/change-password`.
- **`src/screens/`** — `Login`, `ChangePassword`, `Home` (benvenuto minimo), `Unauthorized` (403).
- **`src/shell/`** — `AppShell` (intestazione con operatore + logout) + `Nav` (voci per ruolo, scheletro estendibile).
- **`src/i18n`** — catalogo `it`.
- **`src/rbac`** — mappa `Role → sezioni di nav` (mirror di §6, sola UX).

Confine: dipende solo dal contratto HTTP auth di S5. Non conosce il kiosk. Espone la shell su cui i sotto-progetti successivi montano le sezioni.

## 5. Flusso (una sessione operatore)

```
[avvio app] token in sessionStorage?
   sì → GET /auth/me  → 200: operator (+ role) → (must_change_password? → /change-password) : shell
                       → 401: pulisci token → /login
   no → /login
[/login] POST /auth/login {username,password}
   200 {token, operator, must_change_password} → salva token
        must_change_password ? → /change-password (gate)  :  → / (shell)
   401 → «credenziali non valide» (messaggio generico, no user-enumeration lato UI)
[/change-password] POST /auth/change-password {old_password,new_password}
   204 → shell ; errore → messaggio
[shell] nav per ruolo (§6) ; ogni richiesta via operatorClient con Bearer
   401 in qualunque momento → pulisci token → /login («sessione scaduta»)
[logout] POST /auth/logout → pulisci token → /login
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**. Vitest + @testing-library/react; `operatorClient` con `fetch` mockato (nessun backend). Priorità sulla tenuta:
- **Login**: credenziali valide → token in sessionStorage + shell; 401 → messaggio, nessun token salvato.
- **Gate cambio password**: `must_change_password` → si finisce su `/change-password` e NON si raggiunge la home finché non si cambia (il gate non si aggira via URL).
- **Sessione**: token presente all'avvio → `me()` popola l'operatore; `me()` 401 → token pulito → login.
- **Degrado**: 401 su una richiesta → logout + redirect con «sessione scaduta»; 403 → «non autorizzato».
- **RBAC nav**: ogni ruolo vede le proprie voci (operator/supervisor/admin/auditor), non le altre.
- **Client**: le chiamate inviano `Authorization: Bearer`; logout pulisce sessionStorage.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Token esfiltrabile via XSS | sessionStorage (non persiste tra riavvii) + scadenza/revoca S5; cookie httpOnly = hardening futuro (richiede S5) |
| Gate cambio-password aggirabile | imposto nel `ProtectedRoute` su ogni rotta protetta + test che verifica il blocco |
| Sessione scaduta lascia stati ambigui | 401 centralizzato nel client → logout+redirect coerente |
| Nav mostra sezioni non permesse | nav per ruolo (mirror §6) + il server resta l'autorità (403) |
| Ristrutturazione del kiosk | evitata: app sibling, `frontend/` intatto |
| Stringhe hard-coded (regressione i18n) | catalogo `it`, nessuna stringa nei componenti |

## 8. Criteri di accettazione

- Unit (fake client) verdi e deterministici: login OK → shell; 401 login → messaggio senza token; gate `must_change_password` non aggirabile; `me()` all'avvio; 401→logout+redirect; 403→non autorizzato; nav corretta per i 4 ruoli; Bearer inviato; logout pulisce sessionStorage.
- Il flusso `login → (gate) → shell → logout` è percorribile col fake client.
- `vitest`, typecheck, lint, build verdi. Solo dipendenze open source permissive (nuova: `react-router-dom`, MIT).

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§6/§7.2/§7.3/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con l'app `operator-portal/` (Vite+React+TS+react-router+react-i18next), l'`operatorClient` (Bearer), sessionStorage, il gate cambio-password (chiude il follow-up S5), la shell RBAC, e la nota di layout (portale come app sibling; §10 «frontend/» rivisto). Aggiungere la roadmap dei sotto-progetti 2–5.
- **Piano collegato:** scomposizione TDD (scaffold app separata + gate di test; poi `operatorClient` + sessione; poi login + gate cambio-password; poi shell RBAC + rotte protette; infine composizione del flusso).
- **Sotto-progetti successivi** (roadmap): matching spiegabile; profili; amministrazione utenze; metriche + export (follow-on backend).
