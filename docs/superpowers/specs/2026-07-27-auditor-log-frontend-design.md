# Spec di design — Sottosistema 19: Vista del log di audit (Auditor) — Frontend

**Progetto «Bussola»** · Sottosistema 19 (ruolo Auditor · visore del log di audit — **parte frontend**) · *Design di riferimento per il piano collegato* · 2026-07-27

---

## 0. Cos'è questo documento

Spec di design della **parte frontend** della vista del log di audit: il **visore** per il ruolo **Auditor** (§6), sul contratto `/audit` + `/audit/verify` costruito dal backend S18. Completa il ruolo Auditor. Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*. Si conforma a `CLAUDE.md` §2 (accountability, **non** sorveglianza), §3 (locale, open source, solo azioni previste, fail-closed), §6 (ruolo **Auditor**, **sola lettura**, «non modifica nulla e non partecipa all'operatività», privilegio minimo; server autorità), §7.3 (registro immutabile, tamper-evidence verificabile), §9 (TDD, dati sintetici), §11 (stringhe UI esternalizzate i18n). Si innesta sullo scheletro S11 (`operator-portal/`) e riusa i pattern S12–S17 (`operatorClient` esteso fail-closed, `useApiError`, nav-link `built`).

## 1. Contesto e scopo

Con S18 esiste il contratto HTTP per leggere il registro di audit (`GET /audit` paginato a cursore + filtri; `GET /audit/verify` per la tamper-evidence). Questa parte gli dà un volto: l'**Auditor** apre la sezione «Log di audit», scorre le voci (chi/cosa/quando), le filtra, ne carica altre all'indietro nel tempo, e può **verificare l'integrità** della catena hash con un clic. È l'ultimo pezzo del ruolo Auditor — la garanzia §2/§7.3 resa operativa nel portale.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora — frontend):**
- **`operatorClient` esteso** (fail-closed, Bearer): `listAudit(filters)` → voci (con cursore `before`); `verifyAudit()` → esito della catena. Mapping: 401→`unauthorized`, 403→`forbidden`, rete/5xx→`error`.
- **Superficie «Log di audit»** (nav → link reale, rotta `/audit`, ruolo auditor): **pannello filtri** (attore, azione, da/a); **tabella voci** (data/ora, attore, azione, pseudonimo, `details`); **«Carica altri»** (append incrementale via cursore `before`); **«Verifica integrità»** (su richiesta) con badge di esito.
- **i18n** italiano esternalizzato.

**Non-obiettivi (rimandati):**
- **Backend** dell'audit → **S18** (già fatto). Qui si consuma soltanto.
- **Attività operatori del Supervisore** (§6): vista aggregata/filtrata → sotto-progetto successivo, costruibile sopra lo stesso contratto.
- **Azioni dell'auditor** (annotazioni, export del log): nessuna — l'auditor «non modifica nulla» (§6). La verifica è una lettura.
- **Ricerca full-text sui `details`, grafici/timeline**: fuori scope (YAGNI); filtri chi/cosa/quando bastano allo scopo §6.

## 3. Decisioni di design (con motivazione)

1. **Superficie di sola lettura, coesa, sotto la shell S11.** Rotta `/audit`, dietro `ProtectedRoute` + ruolo auditor (server autorità → 403; la nav mostra la voce solo all'auditor). Nessun controllo che muti stato. *Perché §6:* l'auditor «non modifica nulla e non partecipa all'operatività»; la sezione è un visore, non una console operativa.

2. **Paginazione «Carica altri» a cursore (opzione approvata).** Si mostrano le voci più recenti; «Carica altri» aggiunge in coda la pagina successiva con `before` = id dell'ultima voce mostrata; il pulsante sparisce quando l'ultima pagina è più corta del `limit` (fine del log). *Perché §7.3:* il log è append-only e cresce; il cursore per id è stabile e modella «scorrere indietro nel tempo» senza slittamenti; niente conteggio totale o salto-a-pagina (non nel contratto).

3. **Verifica integrità su richiesta (opzione approvata).** Un pulsante «Verifica integrità» chiama `/audit/verify` e mostra un badge: **verde** «catena integra» oppure **rosso** «manomissione rilevata alla riga N» (`broken_at`). *Perché §7.3 + prestazioni:* la verifica è O(n) sull'intero log; eseguirla a ogni apertura peggiorerebbe col crescere del registro. L'auditor la lancia quando serve, e ottiene una risposta netta.

4. **`operatorClient` esteso fail-closed + `useApiError`.** Come S12–S17: risultati tipizzati, 401→onUnauthorized+/login, 403→messaggio, error ritentabile, mai un throw. *Perché §3:* solo azioni previste, nessuno stato ambiguo.

5. **Rendere le voci senza reintrodurre PII (linea rossa §2/§5).** La tabella mostra `occurred_at`, `actor` (username dello staff — accountability), `action`, `target_pseudonym` (pseudonimo **opaco**, «—» se assente), e `details` in forma compatta (metadati disciplinati: nomi-filtro, conteggi, id-richiesta, ruoli). *Perché §2:* la vista serve a impedire il riuso improprio (chi ha fatto cosa), **non** a profilare le persone; nessun dato personale della persona detenuta compare (per costruzione il log non ne contiene).

6. **Titolo pagina vs label nav.** Il titolo della sezione e la voce di nav condividono la stessa stringa («Log di audit»): i test d'integrazione interrogano per **ruolo**/contenuto proprio della schermata (non per testo puro), come da follow-up S17.

## 4. Unità e confini

Sotto `operator-portal/src/`:
- **`types.ts`** (estensione) — `AuditEntry` (`id, occurred_at, actor, action, target_pseudonym, details`), `AuditFilters` (`before?, limit?, actor?, action?, from?, to?`), `AuditVerification` (`ok, broken_at, reason`), e le result-union (`AuditListResult` = `ok{entries}`, `VerifyAuditResult` = `ok{verification}`).
- **`api/operatorClient`** (estensione) — `listAudit(filters)` (query params dai filtri impostati + `before`/`limit`), `verifyAudit()`; fail-closed.
- **`screens/audit/AuditLog`** — superficie orchestratrice: filtri + tabella + «Carica altri» + «Verifica integrità».
- **`screens/audit/AuditFilters`** (o inline) — pannello filtri (attore, azione, da/a).
- **`screens/audit/detailsSummary`** (util) — rende `details` in forma compatta e leggibile.
- **`rbac/nav`** — `audit` marcato `built`.
- **`App`** — rotta `/audit` annidata sotto `ProtectedRoute`/`AppShell`.
- **`i18n/locales/it`** (estensione) — gruppo `audit` (titolo, etichette colonne/filtri, testi verifica, badge esito).

Confine: dipende dal contratto `/audit`+`/audit/verify` (S18) e dallo scheletro S11. Il server resta l'autorità (RBAC/403).

## 5. Flusso

```
[auditor] Nav «Log di audit» → /audit
   (mount) GET /audit?limit=N → voci più recenti (tabella)
   filtri (attore/azione/da/a) → «Cerca» → GET /audit?<filtri> (resetta il cursore)
   «Carica altri» → GET /audit?before=<id ultima voce>&<filtri> → append
        (nascosto quando l'ultima pagina < N)
   «Verifica integrità» → GET /audit/verify → badge {ok | manomissione alla riga N}
   401 → onUnauthorized + /login ; 403 → «non hai i permessi» ; rete/5xx → errore ritentabile
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**; Vitest + @testing-library/react; `operatorClient` fake iniettato. Priorità:
- **Client**: `listAudit` invia i filtri impostati + `before`/`limit` come query params (omette i vuoti); `verifyAudit` colpisce `/audit/verify`; mapping 200/401/403/error; mai un throw.
- **Lista**: rende le voci (data/ora, attore, azione, pseudonimo/«—», details compatti); vuoto → empty-state.
- **Carica altri**: il secondo fetch usa `before` = id dell'ultima voce e **appende**; il pulsante sparisce quando l'ultima pagina è più corta del `limit`.
- **Verifica**: «Verifica integrità» su catena integra → badge verde; su catena rotta → badge rosso con `broken_at`.
- **Degrado**: 401→login; 403→«non hai i permessi»; error→ritentabile; loading gated `!error`.
- **Nav/RBAC**: «Log di audit» è un link reale (auditor); sezione dietro `ProtectedRoute` (query per ruolo/contenuto proprio, non per testo puro — S17).
- **Privacy**: nessuna PII resa (verificato dalla struttura delle voci finte: solo pseudonimi opachi + metadati).

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Accesso al visore da ruolo non autorizzato | RBAC lato server (403); nav mostra la voce solo all'auditor; rotta dietro `ProtectedRoute` |
| Verifica O(n) a ogni apertura | verifica **su richiesta** (pulsante), non automatica |
| Slittamento paginazione su log che cresce | cursore per `id` (append-only), «Carica altri» incrementale |
| Reintroduzione di PII nella UI | si rendono solo pseudonimi opachi + metadati disciplinati; il log non contiene dati personali per costruzione |
| Frainteso come sorveglianza | la sezione mostra **azioni degli operatori** (accountability §2), non profili né inferenze |
| 401 lascia stato ambiguo | `useApiError` → onUnauthorized + redirect |

## 8. Criteri di accettazione

- Unit (fake client) verdi e deterministici: client invia filtri+cursore e mappa gli status; lista rende le voci + empty-state; «Carica altri» appende con `before` e sparisce a fine log; «Verifica integrità» mostra verde/rosso(+riga); degrado 401/403/error; nav link reale; rotta protetta.
- Il flusso `apri → filtra → carica altri → verifica` è percorribile col fake client.
- `vitest`, typecheck, lint, build verdi. Nessuna nuova dipendenza. `frontend/` (kiosk) e `backend/` intatti.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§5/§6/§7.3/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con il visore del log (paginazione «Carica altri», verifica su richiesta, resa compatta dei `details`), l'estensione `operatorClient`, e l'avanzamento della roadmap (ruolo Auditor concluso; restano attività-operatori supervisore e admin-config).
- **Spec 5b/S18 (backend audit):** fornisce il contratto `/audit` + `/audit/verify` consumato qui.
- **Piano collegato:** scomposizione TDD (tipi + client `listAudit`/`verifyAudit`; poi la schermata `AuditLog` con lista + «Carica altri» + «Verifica integrità»; infine nav-link + rotta + integrazione).
