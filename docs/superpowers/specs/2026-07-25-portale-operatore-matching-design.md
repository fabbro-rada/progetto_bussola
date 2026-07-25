# Spec di design — Sottosistema 12: Portale operatore — Richieste di lavoro + matching spiegabile

**Progetto «Bussola»** · Sottosistema 12 (portale operatore, sotto-progetto 2/5) · *Design di riferimento per il piano collegato* · 2026-07-25

---

## 0. Cos'è questo documento

Spec di design del **secondo sotto-progetto del portale operatore**: la sezione **Richieste di lavoro + matching spiegabile**. Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (linee rosse, ambito, «mai una scatola nera»), §3 (locale, open source, prevenzione abusi, solo azioni previste), §5 (profilo minimo, pseudonimo, minimizzazione), §6 (ruolo operatore), §7.2 (inserimento richieste, **matching spiegabile con gap formativi**), §7.3 (audit, filtro PII), §9 (TDD, dati sintetici), §11 (codice inglese, stringhe UI esternalizzate). Si innesta sullo scheletro S11 (`operator-portal/`: `AuthProvider`/`useAuth`, `ProtectedRoute`, `AppShell`/`Nav`, `operatorClient`). Consuma l'API S6: `POST /job-requests`, `GET /job-requests`, `GET /job-requests/{id}`, `POST /job-requests/{id}/match`.

## 1. Contesto e scopo

S11 ha dato al portale login + shell RBAC. Questo sotto-progetto realizza il **cuore del valore per l'operatore** (§7.2): inserire le richieste di lavoro delle aziende e ottenere un **matching spiegabile** con le persone — per-requisito soddisfatto/no, **evidenza citata dal profilo**, e **gap formativi con formazione consigliata**. È l'antitesi della «scatola nera» (§2/§10): l'operatore vede *perché* un abbinamento è proposto.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora):**
- **Sezione «Richieste di lavoro»**: lista (`GET /job-requests`), creazione (`POST`), dettaglio (`GET /{id}`), sotto la shell S11, dietro `ProtectedRoute` + ruolo operatore (§6). La voce di nav (placeholder S11) diventa un **link reale**.
- **Creazione richiesta**: form sui campi *solo-lavoro* dello schema `JobRequestCreate` (titolo, settore, descrizione, competenze richieste, lingue richieste con livello, disponibilità, turni notturni, prerequisiti formativi). Per costruzione non può contenere criteri discriminatori o non-lavorativi (schema `extra="forbid"`).
- **Matching spiegabile on-demand**: dal dettaglio, un **clic esplicito** «Esegui matching» → `POST /{id}/match` → rendering dei `MatchResult` compatibili, ordinati per punteggio: pseudonimo, **punteggio come frazione** (X/Y requisiti), verdetti per-requisito **con evidenza**, box **gap→formazione**. Stato di attesa durante la chiamata (LLM lento, §10).
- **Estensione `operatorClient`**: metodi feature fail-closed col Bearer; 401→`unauthorized` (→ logout + «sessione scaduta»), 403→`forbidden` (→ «non autorizzato»), rete/5xx→`error` ritentabile. Chiude in pratica il follow-up S11 dell'interceptor 401 per le chiamate feature.
- **i18n** italiano esternalizzato; pseudonimo opaco, nessuna PII (§5).

**Non-obiettivi (rimandati):**
- **Candidati esclusi dal gate**: l'API `/match` restituisce **solo i compatibili** (gli esclusi sono scartati per minimizzazione, scelta deliberata S6). La UI **non** mostra una lista esclusi e non richiede modifiche al backend. *(Se in futuro si volesse esporre gli esclusi col motivo, sarebbe una modifica deliberata a S6 — fuori da questo sotto-progetto.)*
- **Persistenza/storicizzazione degli esiti di matching** → Fase 2 (S6 li calcola on-demand).
- **Modifica/eliminazione richieste** → non nell'API S6 attuale (solo create/list/get); eventuale estensione futura.
- **Consultazione profili autonoma, amministrazione utenze, metriche, export** → sotto-progetti 3–5.

## 3. Decisioni di design (con motivazione)

1. **Sezione coesa richieste+matching, innestata sulla shell S11.** Rotte `/job-requests`, `/job-requests/new`, `/job-requests/:id` sotto `/` (AppShell). *Perché §7.2:* il matching si lancia dal dettaglio di una richiesta; tenerli insieme dà una feature completa end-to-end.

2. **La voce di nav diventa un link reale.** In S11 le voci erano placeholder disabilitati; qui «Richieste di lavoro» diventa un `<Link>`, le altre restano «in arrivo». *Perché:* pattern «ogni sotto-progetto registra la propria sezione», senza toccare le altre.

3. **Matching on-demand con clic esplicito.** Nessun run automatico all'apertura del dettaglio. *Perché §10/S6:* l'LLM è lento su hardware modesto; l'operatore controlla quando eseguire; coerente con «on-demand, non persistito» di S6.

4. **Rendering spiegabile: card espandibile per candidato.** Lista compatta (pseudonimo, badge vincoli-ok, **frazione** X/Y); espansione → verdetti per-requisito con **evidenza citata** + box gap→formazione. *Perché §2/§10:* «mai una scatola nera»; il punteggio è una **frazione trasparente**, non una percentuale opaca; l'evidenza mostra *perché*.

5. **Solo compatibili (rispetto della minimizzazione S6).** La UI rende ciò che l'API dà (tutti compatibili). *Perché §5:* non si espone perché una persona è stata scartata; nessuna modifica al backend.

6. **`operatorClient` esteso, fail-closed, con gestione 401 centralizzata.** I metodi feature mappano gli esiti in risultati tipizzati; il 401 innesca `onUnauthorized()` (già in S11) + redirect a `/login` con «sessione scaduta». *Perché §3/S11:* solo azioni previste; nessuno stato autenticato ambiguo; realizza il follow-up 401 per le chiamate feature.

7. **Filtro PII già a monte (S4/S6).** I profili e le evidenze arrivano già filtrati dal backend (PiiRedactor nel percorso S6); la UI non reintroduce PII. *Perché §7.3:* nessuna fuoriuscita.

## 4. Unità e confini

Sotto `operator-portal/src/`:
- **`api/operatorClient`** (estensione) — `listJobRequests()`, `getJobRequest(id)`, `createJobRequest(body)`, `runMatch(id)`; risultati tipizzati (`ok | unauthorized | forbidden | error`), Bearer, fail-closed.
- **`types.ts`** (estensione) — `JobRequest`, `JobRequestCreate`, `RequiredLanguage`, `MatchResult`, `RequirementVerdict`, `ConstraintOutcome`, `GapItem`, gli enum `LanguageLevel`/`Availability` (mirror del backend).
- **`screens/jobRequests/`** — `JobRequestList`, `JobRequestCreate` (form), `JobRequestDetail` (riepilogo + «Esegui matching»).
- **`screens/jobRequests/MatchResults`** — rendering dei `MatchResult` (card espandibili con evidenza + gap).
- **`shell/Nav`** (modifica) — «jobRequests» come link reale.
- **`App`** (modifica) — rotte annidate della sezione.
- **`rbac`** — la voce jobRequests è dell'operatore (già in `NAV_BY_ROLE`).
- **`i18n/locales/it`** (estensione) — stringhe della sezione.

Confine: dipende solo dal contratto HTTP S6 e dallo scheletro S11. Il server resta l'autorità (RBAC/403).

## 5. Flusso (una sessione di matching)

```
[operatore loggato] Nav → «Richieste di lavoro» → /job-requests
   GET /job-requests → tabella (titolo, settore, creata-da)
[Nuova richiesta] /job-requests/new → form (campi solo-lavoro) → POST /job-requests
   201 → /job-requests/:id (dettaglio)
[Dettaglio] riepilogo requisiti → clic «Esegui matching»
   POST /job-requests/:id/match  [stato: sto calcolando…]
      → MatchResult[] (compatibili, ordinati per punteggio) → card espandibili:
           pseudonimo · frazione X/Y · [espandi] verdetti per-requisito (✓/✗ + evidenza) · gap→formazione
   401 → onUnauthorized() + /login («sessione scaduta») ; 403 → «non autorizzato» ; rete/5xx → errore ritentabile
```

## 6. Strategia di test (§9)

TDD; **solo dati sintetici** (richieste e profili finti). Vitest + @testing-library/react; `operatorClient` fake iniettato. Priorità:
- **Lista/dettaglio**: rendono i dati; riga → dettaglio.
- **Creazione**: il form invia il body corretto (incl. `required_languages` come coppie lingua+livello, availability, night shifts, liste competenze/prerequisiti); 201 → dettaglio.
- **Matching spiegabile**: «Esegui matching» chiama `runMatch`; i risultati mostrano pseudonimo, frazione, verdetti per-requisito **con evidenza**, e i **gap→formazione**; stato di attesa durante la chiamata; nessun candidato «escluso» mostrato.
- **Degrado**: 401 → logout + «sessione scaduta»; 403 → «non autorizzato»; error → messaggio ritentabile.
- **Nav/RBAC**: «Richieste di lavoro» è un link reale; le altre voci restano disabilitate; la sezione è dietro `ProtectedRoute`.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Matching lento blocca la UI | clic esplicito + stato «sto calcolando…»; nessun run automatico |
| Fuga di PII nelle evidenze | il backend filtra la PII a monte (S4/S6); la UI non reintroduce |
| Esporre perché una persona è esclusa | non esposto (l'API dà solo compatibili; §5) |
| Punteggio percepito come «scatola nera» | frazione trasparente + verdetti con evidenza (§2/§10) |
| 401 su una chiamata feature lascia stato ambiguo | `unauthorized` → onUnauthorized + redirect coerente |
| Form con criteri non-lavorativi | lo schema backend è `extra="forbid"` (solo-lavoro per costruzione); il form espone solo quei campi |

## 8. Criteri di accettazione

- Unit (fake client) verdi e deterministici: lista/dettaglio rendono; il form crea con il body corretto; «Esegui matching» rende i risultati spiegabili (frazione + verdetti + evidenza + gap); degrado 401/403/error; nav link reale; sezione protetta.
- Il flusso `lista → crea → dettaglio → esegui matching → risultati` è percorribile col fake client.
- `vitest`, typecheck, lint, build verdi. Solo dipendenze open source permissive (nessuna nuova prevista).

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§5/§6/§7.2/§7.3/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con la sezione richieste+matching del portale, l'estensione `operatorClient` (metodi feature + gestione 401 che chiude il follow-up S11), il rendering spiegabile, e la conferma della scelta «solo compatibili» (minimizzazione S6). Avanzare la roadmap (sotto-progetti 3–5).
- **Piano collegato:** scomposizione TDD (types + client feature; poi lista; poi form di creazione; poi dettaglio + esegui-matching; poi rendering dei risultati spiegabili; infine nav-link + composizione rotte).
