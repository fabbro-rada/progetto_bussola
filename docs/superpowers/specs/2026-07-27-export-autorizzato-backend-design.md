# Spec di design — Sottosistema 16: Export con autorizzazione — Backend

**Progetto «Bussola»** · Sottosistema 16 (portale operatore, sotto-progetto 5b/5 · export — **parte backend**) · *Design di riferimento per il piano collegato* · 2026-07-27

---

## 0. Cos'è questo documento

Spec di design della **parte backend** del quinto sotto-progetto del portale operatore: l'**export dei profili con autorizzazione** (§7.2 «esportazione di base», §7.3 «ogni esportazione passa da un'approvazione»). Il sotto-progetto 5b è stato **decomposto** in **backend** (questo documento: tabella, workflow a stati, endpoint RBAC, audit, generazione JSON on-demand) e **frontend** (spec successiva: superfici operatore + supervisore). Nel flusso: brainstorming → **spec (questo file)** → piano → TDD. Descrive *cosa* e *perché*, non il codice. Si conforma a `CLAUDE.md` §2 (solo dati solo-lavoro; nessun dato non pertinente), §3 (locale, open source, solo azioni previste, fail-closed, **flussi autorizzativi per ogni condivisione verso l'esterno**), §5 (profilo minimo, pseudonimo, nessuna mappa pseudonimo↔persona), §6 (ruoli **operatore** richiedente ed **supervisore** approvatore, privilegio minimo), §7.2 (esportazione di base, estrazione controllata), §7.3 (**autorizzazione per le condivisioni esterne**, **filtro dei dati personali in uscita**, audit immutabile, resistenza abusi), §8 (esiti del matching e reportistica aggregata = Fase 2), §9 (TDD, dati sintetici), §11 (codice inglese).

È il punto **più sensibile** del sistema: l'unica uscita di dati «verso l'esterno». La garanzia non è un singolo controllo ma la loro somma: whitelist strutturale del profilo + autorizzazione obbligatoria imposta dal server + separazione dei ruoli + audit di ogni passo + generazione senza copie persistite.

## 1. Contesto e scopo

Con S12–S15 l'operatore gestisce richieste/matching, consulta profili, e il supervisore vede le metriche. Manca il modo di **portare fuori i risultati per il raccordo con le aziende** (§7.2 «esportazione di base»), che il nucleo vincola a un **flusso di approvazione** (§7.3). Questo backend fornisce il ciclo **richiesta → approvazione → download**: l'operatore richiede un export (descritto da filtri), il supervisore lo approva o nega, e solo allora l'export è scaricabile. È il primo (e unico, in Fase 1) canale di uscita dei dati.

## 2. Obiettivi e non-obiettivi

**Obiettivi (ora — backend):**
- **Tabella delle richieste di export** in un nuovo schema `export` (segregazione §6): `export.export_request` con ambito (filtri), motivo, stato e tracce di decisione. **Nessun payload memorizzato.**
- **Servizio `bussola.export`** col workflow a stati: creare una richiesta (operatore), elencarne le proprie, elencare le pendenti (approvatore), approvare/negare (approvatore), **generare il payload** al download.
- **Generazione on-demand**: al download, si **ri-esegue la ricerca profili** coi filtri approvati e si restituisce `list[WorkProfile]` (JSON). Nessun contenuto sensibile conservato nel DB (minimizzazione §5).
- **Endpoint `/exports`** dietro RBAC: creazione/lista/download per il ruolo **operatore** (`EXPORT_DATA`, già esistente); coda-pendenti/approva/nega per il ruolo **supervisore** (nuovo permesso `APPROVE_EXPORTS`). Gate di download **imposto dal server**: si scarica solo se la richiesta è `approved` ed è propria.
- **Audit di ogni passo** (`export_requested`, `export_approved`, `export_denied`, `export_downloaded`), atomico con la transizione (pattern S5: `append_audit(commit=False)` + un solo commit del servizio).

**Non-obiettivi (rimandati):**
- **Frontend** (superfici operatore/supervisore, download nel browser) → **spec 5b-frontend** (successiva).
- **Export degli esiti del matching**: gli esiti **non sono persistiti** (§14) → Fase 2. Qui si esportano i **profili** (§8).
- **Reportistica aggregata/anonima e formati multipli** (CSV): Fase 2 (§8). Qui: **JSON** dei profili solo-lavoro.
- **Revoca di un'approvazione / scadenza / uso singolo del download**: non ora. Una richiesta approvata resta scaricabile (ogni download è auditato); revoca/scadenza = follow-on.
- **Snapshot del contenuto**: escluso per scelta (approvata) — generazione on-demand, nessuna copia congelata.

## 3. Decisioni di design (con motivazione)

1. **Workflow a stati `pending → approved | denied`, download solo da `approved` (opzione approvata).** *Perché §7.3:* «ogni esportazione passa da un'approvazione»; il gate non è un suggerimento UI ma un **controllo lato server** (il download verifica lo stato e la proprietà). Gli stati sono minimi e terminali (nessuna riapertura in Fase 1).

2. **Richiedente operatore, approvatore supervisore — separati per ruolo (opzione approvata).** *Perché §6:* il supervisore «coordina, ha la visione d'insieme, organizza il lavoro»: valutare cosa esce verso le aziende è nel suo ruolo; l'operatore usa i profili ma non autorizza da solo l'uscita. Poiché un operatore ha un **solo** ruolo, richiedente e approvatore sono **principal distinti per costruzione**: **nessuna auto-approvazione** è possibile. Nuovo `Permission.APPROVE_EXPORTS` sul solo supervisore.

3. **Ambito = filtri (riuso di `ProfileFilters` S13), payload = `list[WorkProfile]` JSON (opzioni approvate).** La richiesta memorizza i **filtri** (disponibilità/lingua/nota/competenza), non i profili; il download ri-esegue `ProfileRepository.search(filters)`. *Perché §7.2/§5:* l'operatore descrive «le persone adatte» come già fa nella consultazione; l'approvazione vale per «i profili che corrispondono al filtro X per lo scopo Y», non per righe congelate; nessuna copia di dati persistita.

4. **Generazione on-demand, nessun blob memorizzato (opzione approvata).** *Perché §5 minimizzazione + §7.3:* conservare un export congelato di molti profili aggiungerebbe una superficie di fuga e diventerebbe stantio. Il contenuto vive solo nel momento del download autorizzato. Il prezzo (i dati possono essere cambiati tra approvazione e download) è accettabile e coerente con la natura «filtro + scopo» dell'approvazione.

5. **Motivo (`reason`) obbligatorio e bounded.** La richiesta porta un motivo/destinatario (testo, 1..500). *Perché §7.3:* un'approvazione ha senso solo se l'approvatore ha **contesto** per decidere; un motivo vuoto renderebbe l'autorizzazione una formalità. È metadato interno (non fa parte del payload esportato), quindi non necessita del filtro PII in uscita, ma è comunque limitato in lunghezza (prevenzione abusi §3).

6. **Payload = soli `WorkProfile`, ri-filtrati PII in uscita (linea rossa §2/§5/§7.3).** Il download restituisce esclusivamente profili solo-lavoro (schema whitelist `extra="forbid"`), attraverso `ProfileRepository` con `PiiRedactor` (come S13): la UI/consumer non riceve mai altro che pseudonimo + dati di lavoro. Non esiste (e non viene esportata) alcuna mappa pseudonimo↔persona. *Perché §7.3:* «filtro dei dati personali in uscita; il modello non decide da solo cosa esporre».

7. **Audit atomico di ogni azione (pattern S5).** `export_requested/approved/denied/downloaded` scritti con `append_audit(commit=False)` nella stessa transazione della transizione, con un solo commit del servizio. `export_downloaded` registra i **nomi-filtro + conteggio** dei profili (mai PII), come `profiles_searched`. *Perché §7.3:* nessuna azione senza il suo record; accountability sull'uscita dei dati.

8. **Transizioni concorrenti guardate a DB.** Approvazione/negazione fanno `UPDATE ... WHERE id=%s AND status='pending'`: se nessuna riga è toccata, la richiesta è già decisa → **409**. *Perché §3:* nessuno stato ambiguo, nessuna doppia decisione.

9. **Nuovo schema `export`, nessun payload, no DELETE.** `export.export_request` con `status` vincolato da un `CHECK ('pending','approved','denied')`. Grant `bussola_app`: `SELECT, INSERT, UPDATE` (le transizioni aggiornano stato/decisione); **niente DELETE** (le richieste restano tracciabili, §7.3). *Perché §6:* segregazione per schema; privilegio minimo.

## 4. Unità e confini

Sotto `backend/src/bussola/`:
- **`data/migrations/0006_exports.sql`** — schema `export` (AUTHORIZATION `bussola_owner`), tabella `export.export_request` (colonne §5 sotto), `CHECK` sullo stato, grant `bussola_app`.
- **`export/models.py`** — `ExportRequest` (pydantic; rispecchia la riga) + enum/Literal degli stati. Riusa `ProfileFilters` dal modulo profili/matching (o un DTO locale coerente con S13).
- **`export/service.py`** — `ExportService(conn)`: `create_request(actor, filters, reason)`, `list_own(actor)`, `list_pending()`, `approve(actor, id)`, `deny(actor, id, reason)`, `generate_payload(actor, id) -> list[WorkProfile]`. Transizioni guardate; audit atomico.
- **`auth/rbac.py`** — nuovo `Permission.APPROVE_EXPORTS`, mappato al solo `Role.SUPERVISOR`.
- **`api/routers/exports.py`** — endpoint `/exports` (dettaglio §5), con `require_permission(EXPORT_DATA)` per richiedente e `require_permission(APPROVE_EXPORTS)` per approvatore; audit.
- **`api/app.py`** — include il router.

**Colonne `export.export_request`:** `id` (identity PK), `requested_by text`, `filters jsonb`, `reason text`, `status text CHECK`, `decided_by text NULL`, `decided_at timestamptz NULL`, `decision_reason text NULL`, `created_at timestamptz DEFAULT now()`.

Confine: dipende dai dati profili esistenti (via `ProfileRepository`), dall'RBAC S5 e dall'audit S2. Nessuna dipendenza dal frontend (contratto HTTP puro). Il server resta l'autorità.

## 5. Flusso e contratto HTTP

```
[operatore EXPORT_DATA]
  POST /exports {filters, reason}      → 201 ExportRequest(status=pending) ; audit export_requested
  GET  /exports                         → 200 [ExportRequest…] (solo le proprie)
  GET  /exports/{id}/download           → 200 [WorkProfile…] (JSON) SE propria e status=approved ; audit export_downloaded
                                          → 404 se non propria/inesistente ; 409 se non approvata
[supervisore APPROVE_EXPORTS]
  GET  /exports/pending                 → 200 [ExportRequest…] (tutte le pending)
  POST /exports/{id}/approve            → 204 (UPDATE … WHERE status='pending') ; audit export_approved
                                          → 404 inesistente ; 409 se già decisa
  POST /exports/{id}/deny {reason}      → 204 ; audit export_denied ; → 404/409 come sopra
[ruolo sbagliato] → 403 (require_permission)
[token assente/scaduto] → 401
```

`generate_payload` (download): carica la richiesta; se `requested_by != actor` → 404; se `status != 'approved'` → 409; altrimenti `ProfileRepository(conn, PiiRedactor()).search(**filters)` → `list[WorkProfile]`; `append_audit(action="export_downloaded", actor, details={filtri, count})`.

## 6. Strategia di test (§9)

TDD; **solo dati sintetici**. `pytest` con DB di test (fixtures `db`/`app_conn`/`client`/`make_operator` esistenti). Priorità (tenuta del sistema per prima, §9):
- **Autorizzazione imposta dal server:** un operatore **non** può scaricare una richiesta non `approved` (409) né una non propria (404); un operatore **non** può approvare (403 su `/pending`,`/approve`); un supervisore **non** può creare/scaricare (403 — non ha `EXPORT_DATA`). Nessuna auto-approvazione possibile (ruoli distinti).
- **Workflow a stati:** `create` → pending; `approve`/`deny` da pending → approved/denied; ri-approvare/negare una già decisa → 409 (guardia `WHERE status='pending'`).
- **Generazione on-demand:** dopo l'approvazione, il download restituisce i `WorkProfile` che corrispondono ai filtri; se i profili cambiano, riflette lo stato corrente; **payload = soli campi WorkProfile** (nessun dato extra, nessuna PII) — verificato dalla struttura.
- **Audit:** ogni azione (`requested/approved/denied/downloaded`) scrive un record col giusto attore; `export_downloaded` registra filtri+conteggio, mai PII; atomicità (nessuna transizione senza il suo audit).
- **Migrazione/DB:** lo schema `export` e la tabella esistono; `status` fuori dall'enum è rifiutato dal `CHECK`; `bussola_app` non può fare DELETE.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Uscita di dati senza approvazione | gate di stato **server-side** sul download (`approved` + proprietà); non aggirabile dalla UI |
| Auto-approvazione | richiedente/approvatore separati **per ruolo** (un operatore ha un solo ruolo); permessi disgiunti |
| Copia sensibile persistita | **nessun payload memorizzato**; generazione on-demand |
| Fuga di PII/dati non pertinenti nell'export | payload = soli `WorkProfile` (whitelist `extra="forbid"`) via `PiiRedactor`; audit senza PII |
| Doppia decisione concorrente | `UPDATE … WHERE status='pending'` → 409 se già decisa |
| Azione non tracciata | `append_audit` atomico per ogni transizione |
| Enumerazione di massa via export | l'export è **autorizzato e auditato** (motivo + approvazione + record); tracciabile, non nascosto |

## 8. Criteri di accettazione

- `ExportService` e gli endpoint corretti su tutti i casi §6 (autorizzazione, stati, generazione, audit, migrazione). `pytest -q`, `ruff check .`, `mypy src` verdi.
- Nessuna azione di uscita dati priva di approvazione o di record di audit. Payload = soli `WorkProfile`.
- Solo dipendenze open source permissive (nessuna nuova prevista). `operator-portal/` e `frontend/` **non toccati** (è la sola parte backend). Nuova migrazione additiva `0006`.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme (§2/§3/§5/§6/§7.2/§7.3/§8/§9/§11). **Nessuna modifica al nucleo.**
- **`STATO_TECNICO.md`**: da aggiornare con lo schema/tabella `export`, il workflow a stati, il permesso `APPROVE_EXPORTS`, la generazione on-demand, e l'avanzamento della roadmap (5b-frontend; poi attività-operatori/auditor/admin-config).
- **Spec 5b-frontend (successiva):** superfici operatore (richiesta + lista + download nel browser) e supervisore (coda approvazioni), sul contratto `/exports` di questa spec.
- **Piano collegato:** scomposizione TDD (migrazione `0006` + `APPROVE_EXPORTS`; poi `ExportService` a stati con audit; infine endpoint `/exports` RBAC + download on-demand).
