# Spec di design — Sottosistema 17: Export con autorizzazione — Frontend

**Progetto «Bussola»** · Sottosistema 17 (portale operatore, sotto-progetto 5b/5 · export — **parte frontend**) · *Design di riferimento per il piano collegato* · 2026-07-27

---

## 0. Cos'è questo documento

Spec di design della **parte frontend** dell'export con autorizzazione: le due superfici del portale (**operatore** che richiede e scarica; **supervisore** che approva/nega) sul contratto `/exports` costruito dal backend S16. Completa il sotto-progetto 5b (5b-backend = S16). Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (solo dati solo-lavoro), §3 (locale, open source, solo azioni previste, fail-closed, flussi autorizzativi), §5 (pseudonimo, nessuna PII), §6 (ruoli operatore/supervisore, privilegio minimo, **il server resta l'autorità**), §7.2 (esportazione di base), §7.3 (**autorizzazione per le condivisioni esterne**, audit — imposti dal server), §9 (TDD, dati sintetici), §11 (stringhe UI esternalizzate i18n). Si innesta sullo scheletro S11 (`operator-portal/`) e riusa i pattern S12–S15 (`operatorClient` esteso fail-closed, `useApiError`, nav-link `built`, dialoghi S14).

## 1. Contesto e scopo

S16 ha costruito il backend del workflow (richiesta → approvazione → download). Questa parte gli dà un volto nel portale: l'**operatore** descrive un export (filtri + motivo) e, una volta approvato, lo **scarica**; il **supervisore** vede la **coda delle richieste pendenti** e le **approva o nega** con cognizione di causa. È l'ultimo pezzo del ciclo operatore del portale e l'unico punto in cui i dati escono, sotto controllo.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora — frontend):**
- **`operatorClient` esteso** (fail-closed, Bearer): `createExport(filters, reason)`, `listExports()` (proprie), `listPendingExports()`, `approveExport(id)`, `denyExport(id, reason)`, `downloadExport(id)`. Mapping: 401→`unauthorized`, 403→`forbidden`, 404→`not-found`, 409→`not-approved` (solo download), rete/5xx→`error`.
- **Superficie operatore** (nav «Export» → link reale, rotta `/export`, ruolo operatore): «Le mie richieste» (lista con stato) + «Nuova richiesta» (filtri stile S13 + **motivo obbligatorio**) + **Download** (abilitato solo su `approved`).
- **Superficie supervisore** (nuova voce nav «Approvazioni export» → link reale, rotta `/export-approvals`, ruolo supervisore): **coda pending** con contesto (richiedente, filtri leggibili, motivo, data) + **Approva** (con conferma) / **Nega** (con motivo obbligatorio).
- **Download nel browser**: il payload JSON (`list[WorkProfile]`) viene scaricato come file `export-{id}.json`.
- **i18n** italiano esternalizzato.

**Non-obiettivi (rimandati):**
- **Backend** dell'export → **S16** (già fatto): tabella, workflow a stati, endpoint, generazione on-demand, audit. Qui si consuma soltanto.
- **Formati diversi da JSON, reportistica aggregata, esiti del matching** → Fase 2 (§8).
- **Revoca/scadenza di un'approvazione, storicizzazione** → follow-on (come da S16).
- **Anteprima del contenuto dell'export** nel browser: no — si scarica il file. Mostrare molti profili a schermo non serve allo scopo (raccordo aziende) e amplierebbe inutilmente la superficie.

## 3. Decisioni di design (con motivazione)

1. **Due superfici coese, una per ruolo, sotto la shell S11.** Operatore: `/export`; supervisore: `/export-approvals` (nuova voce di nav). *Perché §6:* richiedente e approvatore sono ruoli distinti (server autorità); ciascuno vede solo la propria superficie (la nav mostra la voce per ruolo; il server impone l'RBAC → 403). Rotte solo auth-gated, come S13–S15.

2. **Il server resta l'autorità; la UI non aggira il gate (linea rossa §7.3).** Il pulsante Download è mostrato/abilitato solo per le richieste `approved`, ma il **gate reale è lato server** (download di una non-approvata/non-propria → 409/404 gestiti come degrado, mai come dati). La UI è una comodità, non il controllo di sicurezza. *Perché §3/§7.3:* nessuna azione non prevista; il controllo vive dove non è aggirabile.

3. **L'approvatore decide con contesto; Approva con conferma, Nega con motivo (opzione approvata).** La coda mostra richiedente, **filtri resi leggibili** e motivo. «Approva» apre un dialog di **conferma** (ribadisce il contesto); «Nega» apre un dialog con **motivo obbligatorio** (il backend lo richiede). *Perché §7.3:* autorizzare l'uscita dei dati è l'azione più sensibile — merita una pausa consapevole e una motivazione tracciata; riusa i dialoghi di S14.

4. **«Tutti i profili» esplicito quando i filtri sono vuoti (chiude un follow-up §7.3 di S16).** Un export con filtri vuoti corrisponde all'**intera popolazione**; la coda dell'approvatore lo rende esplicito («Tutti i profili») invece di mostrare un filtro vuoto ambiguo. *Perché §7.3:* l'approvatore deve capire senza ambiguità la portata di ciò che autorizza.

5. **Download come file, non anteprima (opzione approvata).** Il client fa un fetch autenticato dell'endpoint di download e ottiene un **Blob** JSON; la UI innesca il salvataggio di `export-{id}.json`. *Perché §7.2:* lo scopo è portare fuori i risultati per le aziende, non consultarli a schermo (già coperto da S13); nessuna re-introduzione di molti profili nel DOM.

6. **`operatorClient` esteso fail-closed + `useApiError`.** Come S12–S15: risultati tipizzati, 401→`onUnauthorized`+`/login`, 403→messaggio, error ritentabile, mai un throw. Il download mappa anche 409 (`not-approved`) e 404 (`not-found`). *Perché §3:* solo azioni previste, nessuno stato ambiguo.

## 4. Unità e confini

Sotto `operator-portal/src/`:
- **`types.ts`** (estensione) — `ExportFilters` (riuso concettuale di `ProfileFilters`), `ExportRequest` (id, requested_by, filters, reason, status, decided_by, decided_at, decision_reason, created_at), `ExportStatus`, e le result-union (`CreateExportResult`, `ListExportsResult`, `MutateExportResult`, `DownloadExportResult`).
- **`api/operatorClient`** (estensione) — i 6 metodi §2; `downloadExport` restituisce un Blob su 200.
- **`screens/exports/ExportRequests`** — superficie operatore: lista «Le mie richieste» + form «Nuova richiesta» a comparsa + azione Download.
- **`screens/exports/NewExportForm`** — form presentazionale (filtri S13 + motivo obbligatorio).
- **`screens/exports/ExportApprovals`** — superficie supervisore: coda pending + Approva/Nega.
- **`screens/exports/ApproveDialog`** / **`DenyDialog`** (o riuso/estensione dei dialoghi S14) — conferma approvazione (con contesto) e motivo di rifiuto (obbligatorio).
- **`screens/exports/filterSummary`** (util) — rende i filtri leggibili, con «Tutti i profili» quando vuoti.
- **`rbac/nav`** — `export` (operatore) → `built`; **nuova** voce supervisore `export-approvals` → `built`.
- **`App`** — rotte `/export` e `/export-approvals` annidate sotto `ProtectedRoute`/`AppShell`.
- **`i18n/locales/it`** (estensione) — gruppo `exports` + `nav.exportApprovals` + etichette stato.

Confine: dipende dal contratto HTTP `/exports` (S16) e dallo scheletro S11. Il server resta l'autorità (RBAC/403, gate di download, audit).

## 5. Flusso

```
[operatore] Nav «Export» → /export
   «Nuova richiesta» (filtri + motivo obbligatorio) → POST /exports → 201 → re-fetch lista
   «Le mie richieste»: riga con stato (pending/approved/denied) + esito
      Download (solo se approved) → GET /exports/{id}/download → Blob JSON → salva export-{id}.json
        409/404 → messaggio di degrado (non dati)
[supervisore] Nav «Approvazioni export» → /export-approvals
   GET /exports/pending → coda: richiedente · filtri leggibili («Tutti i profili» se vuoti) · motivo · data
   «Approva» → dialog conferma (contesto) → POST …/approve → 204 → re-fetch
   «Nega» → dialog motivo obbligatorio → POST …/deny {reason} → 204 → re-fetch
[qualsiasi] 401 → onUnauthorized + /login ; 403 → «non hai i permessi» ; rete/5xx → errore ritentabile
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**; Vitest + @testing-library/react; `operatorClient` fake iniettato; seam per il download (URL/anchor) mockabile. Priorità:
- **Client**: i 6 metodi inviano la shape corretta col Bearer; mapping 201/200(Blob)/204/401/403/404/409/error; `downloadExport` restituisce un Blob su 200 e `not-approved` su 409; mai un throw.
- **Operatore**: il form invia `{filtri impostati, reason}` (motivo obbligatorio → submit disabilitato se vuoto); la lista rende lo stato; **Download presente/abilitato solo su `approved`**; il download innesca il salvataggio del file (seam chiamato).
- **Supervisore**: la coda rende richiedente/filtri leggibili/motivo; **«Tutti i profili» quando i filtri sono vuoti**; «Approva» chiede conferma → chiama approve; «Nega» richiede un motivo (submit disabilitato se vuoto) → chiama deny col motivo; annulla non chiama il client.
- **Degrado**: 401→login; 403→«non hai i permessi»; error→ritentabile; loading gated `!error`.
- **Nav/RBAC**: «Export» (operatore) e «Approvazioni export» (supervisore) sono link reali; le sezioni dietro `ProtectedRoute`.
- **Privacy**: nessuna PII resa; l'approvatore vede solo pseudonimo-less metadati (richiedente operatore, filtri, motivo) — nessun profilo mostrato nella coda.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| La UI sembra «il controllo» dell'autorizzazione | il gate è lato server; la UI gestisce 409/404 come degrado; il Download-abilitato-solo-se-approved è comodità |
| Approvazione affrettata (uscita dati) | dialog di conferma con contesto (richiedente/filtri/motivo) prima di approvare |
| Ambiguità sulla portata (filtri vuoti = tutti) | «Tutti i profili» esplicito nella coda dell'approvatore |
| Nega senza motivazione | dialog con motivo **obbligatorio** (submit disabilitato se vuoto); il backend comunque lo esige |
| 401 lascia stato ambiguo | `useApiError` → onUnauthorized + redirect |
| Molti profili re-introdotti nel DOM | download come **file**, non anteprima a schermo |

## 8. Criteri di accettazione

- Unit (fake client) verdi e deterministici: client mappa gli status (incl. Blob/409/404); operatore invia filtri+motivo, Download gated su `approved`, download innesca il file; supervisore coda con filtri leggibili + «Tutti i profili», Approva(conferma)/Nega(motivo obbligatorio); degrado 401/403/error; nav due link reali; rotte protette.
- Il flusso `richiesta → (approvazione supervisore) → download` è percorribile col fake client.
- `vitest`, typecheck, lint, build verdi. Nessuna nuova dipendenza. `frontend/` (kiosk) intatto; backend non toccato.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§5/§6/§7.2/§7.3/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con le due superfici export del portale, l'estensione `operatorClient` (incl. download come Blob), la resa leggibile dei filtri con «Tutti i profili», e l'avanzamento della roadmap (ciclo operatore concluso; restano attività-operatori, auditor, admin-config).
- **Spec 5b-backend (S16):** fornisce il contratto `/exports` consumato qui.
- **Piano collegato:** scomposizione TDD (tipi + client 6 metodi con download-Blob; poi superficie operatore + form + download; poi superficie supervisore + dialoghi; infine nav-link + rotte + integrazione).
