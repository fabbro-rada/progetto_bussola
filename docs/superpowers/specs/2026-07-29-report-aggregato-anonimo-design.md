# Spec di design — Sottosistema 28: Reportistica aggregata e anonima (Fase 2·B)

**Progetto «Bussola»** · Sottosistema 28 (Fase 2, §8 — «esportazione avanzata e reportistica aggregata e anonima») · *Design di riferimento per il piano collegato* · 2026-07-29

---

## 0. Cos'è questo documento

Spec di design del **primo sotto-progetto della Fase 2**: una **reportistica aggregata e anonima** a supporto del report finale del pilota (§7.2/§8). Estende le metriche (S15) e l'export con autorizzazione (S16). **Non introduce alcun dato per-persona nuovo**: i report sono aggregati e anonimi *per costruzione* (§2/§5). Conforme a `CLAUDE.md` §2 (nessun punteggio/profilazione della persona), §5 (minimizzazione, pseudonimizzazione), §6 (ruolo supervisore, privilegio minimo), §7.2 (metriche/report), §7.3 (autorizzazione per le condivisioni esterne + audit), §9 (TDD, solo dati sintetici), §11 (codice inglese, i18n). **Nessuna linea rossa toccata**; anzi, il design *rafforza* §5 (soppressione delle celle piccole, persistenza matching solo aggregata).

## 1. Contesto e scopo

Il pilota ha bisogno di un **report finale** che mostri, in forma aggregata e anonima, com'è andato: chi sono le persone sul piano lavorativo (distribuzioni), quanto sono completi i profili, quante richieste di lavoro e quanti matching, con quali esiti e come è progredito nel tempo. Oggi esistono metriche scalari (S15) ma non un report ricco; e gli **esiti del matching non sono persistiti** (S6 è on-demand — §14). Questo sottosistema colma entrambe le cose, mantenendo l'anonimato come proprietà strutturale.

## 2. Obiettivi e non-obiettivi

**Obiettivi:**
- **Motore report** che calcola aggregati **marginali** anonimi con **soppressione k-anonima (k=5)**: distribuzioni sui campi *enumerati*, copertura/completezza, aggregati richieste, **esiti matching**, **serie storiche** settimanali.
- **Persistenza aggregata degli esiti matching** (nuova tabella `matching.match_run`), scritta ad ogni run nel flusso S6 — **senza pseudonimo né righe per-persona**.
- **Vista supervisore** in-portale (sola lettura, senza approvazione) + **export del file report** (CSV+JSON) attraverso il **workflow di approvazione S16** (§7.3).
- Accesso **supervisore** (§6), auditato.

**Non-obiettivi (esclusi):**
- **Report o storie per-persona / per-pseudonimo.** Mai. Solo aggregati.
- **Cross-tabulazioni fini** (es. lingua × disponibilità × vincolo): aumentano il rischio di ri-identificazione → solo distribuzioni **marginali**.
- **Distribuzioni su testo libero** (nomi competenze, settori, ruoli): nessuna tassonomia (§6) → per questi campi solo **conteggi/top-N** con la stessa soppressione, non categorie normalizzate.
- **Colloqui di follow-up** (Fase 2·A) — sotto-progetto separato.
- **Persistenza per-persona del matching** (storia match per detenuto): esclusa per §5/§2.

## 3. Decisioni di design (con motivazione)

1. **Aggregato/anonimo per costruzione + soppressione k=5 (§2/§5).** Il motore produce solo distribuzioni marginali; ogni cella/gruppo con **< 5 profili** è soppressa (resa come `"<5"`), sia nella vista sia nell'export. *Perché:* su una popolazione piccola (un reparto) anche un aggregato può ri-identificare («l'unica persona che parla lingua X»). k=5 è la soglia prudente approvata dalla Direzione. La soppressione è calcolata **una volta** nel motore e riusata da vista ed export (nessuna via che bypassi la soppressione).

2. **Persistenza matching *aggregata per-run*, non per-persona (§5 minimizzazione).** Nuova tabella `matching.match_run(id, created_at, job_request_id?, evaluated_count, compatible_count, gaps jsonb)`: per ogni esecuzione si salva **quanti** candidati valutati/compatibili e le **frequenze dei gap→formazione**, **mai** quale persona per quale posto. *Perché:* per l'aggregato bastano i conteggi; una storia match per-pseudonimo sfiorerebbe §2 (giudizio persistito sulla persona) e violerebbe la minimizzazione §5. Si scrive ad ogni `matching_run` nel flusso S6, in transazione col suo audit.

3. **Riuso del workflow di approvazione S16 per l'export del report (§7.3).** La *vista* (dati nel sistema, mostrati al supervisore) **non** è una condivisione esterna → nessuna approvazione (come le metriche S15). Il *file* (esce dal sistema) → approvazione §7.3. Si aggiunge `kind` a `export.export_request` (`'profiles'|'report'`, default `'profiles'` per retro-compatibilità); lo stato-macchina `ExportService` (pending→approved/denied, transizioni guardate, audit) resta **kind-agnostico**; la materializzazione del download **si dirama sul kind** (profiles → lista WorkProfile come oggi; report → aggregati CSV/JSON on-demand). *Perché:* un solo workflow di approvazione (una sola coda per il supervisore), nessuna duplicazione della logica di stato.

4. **Approvatore del report = supervisore stesso (scelta approvata).** A differenza di S16 (richiedente operatore / approvatore supervisore, ruoli distinti anti-auto-approvazione), per il report il **supervisore richiede e approva**. *Perché:* il payload è **anonimo/aggregato** (soppresso k=5), rischio molto minore del per-profilo; il gate di approvazione esplicito + l'audit soddisfano comunque §7.3 (c'è un atto deliberato «sì, esporta» tracciato). Documentato come rilassamento consapevole del doppio-controllo, limitato agli export anonimi.

5. **I timestamp esistono già → nessuna migrazione per le serie storiche.** `profiles.work_profile.created_at` e `matching.job_request.created_at` sono già presenti (timestamptz). Il motore li aggrega per settimana. *Perché:* nessuna modifica non necessaria alle tabelle esistenti.

6. **Motore report separato da metriche (`bussola.report`), non un ampliamento di `Metrics`.** Le metriche S15 (scalari, `GET /metrics`) restano invariate; il report è un modulo/DTO nuovo. *Perché:* responsabilità distinte, nessuna modifica al contratto S15.

## 4. Unità e confini

**Backend** (`backend/src/bussola/`):
- **`data/migrations/0007_report.sql`** (nuovo) — tabella `matching.match_run` (grant `bussola_app` SELECT+INSERT; auditor nessun accesso, coerente con S16); `ALTER TABLE export.export_request ADD COLUMN kind text NOT NULL DEFAULT 'profiles' CHECK (kind IN ('profiles','report'))`.
- **`matching/service.py`** (modifica) — dopo un match run, `INSERT` aggregato in `match_run` (evaluated/compatible/gaps), nella stessa transazione dell'audit `matching_run`. Nessun pseudonimo scritto.
- **`report/service.py`** (nuovo) — `compute_report(conn, *, k: int = 5) -> Report`; DTO `Report` (Pydantic, `extra="forbid"`) con le sezioni aggregate; soppressione k centralizzata qui.
- **`report/csv.py`** (nuovo) — serializzazione del `Report` in CSV (una sezione per blocco); il JSON è il dump del DTO.
- **`api/routers/report.py`** (nuovo) — `GET /report` dietro `require_permission(VIEW_METRICS)` (supervisore); audit `report_viewed`. **Nuovo** `POST /report/export` dietro `require_permission(VIEW_METRICS)`: crea una richiesta export `kind='report'`. *(Perché un endpoint dedicato e non `POST /exports`: così la creazione del report-export è gated su `VIEW_METRICS` — permesso che il supervisore già ha — senza dare al supervisore `EXPORT_DATA`, che aprirebbe anche l'export dei profili grezzi. Nessun nuovo permesso, nessun allargamento di ruolo.)*
- **`export/…`** (modifica) — `ExportService` accetta `kind` (default `'profiles'`); lo stato-macchina resta kind-agnostico. Il **download** materializza il report quando `kind='report'` (chiama `compute_report` + serializza CSV/JSON). Endpoint condivisi: **approvazione/rifiuto** restano `require_permission(APPROVE_EXPORTS)` (supervisore) e il **download** resta gated su richiesta `approved` + proprietà (come S16). Per il report, richiedente e approvatore sono **entrambi supervisore** (decisione §3.4): la coda approvazioni (S17) mostrerà anche le richieste `kind='report'`. `POST /exports` (kind implicito `'profiles'`, `EXPORT_DATA`, operatore) **invariato**.

**Frontend** (`operator-portal/src/`):
- **`screens/report/ReportPanel.tsx`** (nuovo) — vista supervisore sola-lettura (`/report`, nav «Report»): distribuzioni (barre/tabelle), istogramma completezza, esiti matching, serie storiche; celle soppresse rese come «<5». Pulsante **«Esporta report»** → crea una richiesta export `kind='report'`.
- **`operatorClient`** (modifica) — `getReport()` (fail-closed) + estensione dei metodi export per `kind='report'`.
- Riuso di `useFetchOnMount`, `saveBlob`, e della coda approvazioni S17 (che mostrerà anche le richieste `kind='report'`).

**Confine:** nessuna modifica a S15 (`/metrics`), al contratto di matching lato risposta (solo un side-effect di persistenza), o al kiosk. Nessuna PII/pseudonimo negli aggregati.

## 5. Interfacce delle nuove astrazioni

- **`Report`** (Pydantic, `extra="forbid"`): sezioni — `coverage` (total/completed/average_completeness/completeness_histogram), `languages` (per lingua×livello, soppresso), `skills` (per kind + per evidence), `availability`, `constraints`, `job_requests` (conteggi), `matching` (runs, evaluated, compatible, compatible_rate, top_gaps), `trends` (profili completati e richieste per settimana). Ogni conteggio soggetto a soppressione k.
- **`compute_report(conn, *, k: int = 5) -> Report`** — letture aggregate; nessun dato per-persona nel risultato.
- **`match_run`** (tabella): `id bigserial`, `created_at timestamptz default now()`, `job_request_id` (nullable, FK logica), `evaluated_count int`, `compatible_count int`, `gaps jsonb` (mappa topic→count). **Nessun** pseudonimo.
- **`export_request.kind`**: `'profiles' | 'report'`.
- **Soppressione:** una cella con conteggio `0 < n < k` è resa come il sentinello `"<5"` (stringa) sia in JSON sia in CSV; `n == 0` resta `0`; `n >= k` resta il numero.

## 6. Strategia di test (§9)

- **Soppressione k (prioritario, §2/§5):** con popolazione sintetica costruita ad hoc, un gruppo con <5 profili è reso `"<5"` in vista, JSON e CSV; un gruppo ≥5 mostra il numero; **nessun conteggio 1..4 trapela** in nessun formato. Test avversario: un profilo con una lingua unica non è ri-identificabile dall'output.
- **Nessuna PII/pseudonimo nell'output:** il `Report` (e il CSV/JSON) non contiene pseudonimi né stringhe di testo libero non aggregate (asserzione sul payload).
- **Persistenza matching aggregata:** dopo un match run, `match_run` ha una riga coi conteggi giusti e **nessun** pseudonimo; il DTO di risposta del matching è invariato (S6 non cambia contratto).
- **Correttezza aggregati:** distribuzioni/serie storiche calcolate su fixture note.
- **RBAC:** `GET /report` e la creazione export `kind='report'` → **403** per non-supervisore; audit `report_viewed` emesso.
- **Export §7.3:** il download del report `kind='report'` è gated dall'approvazione (pending/denied → 404/409); CSV/JSON ben formati; audit dell'export.
- **Retro-compatibilità:** gli export `kind='profiles'` esistenti (S16/S17) restano identici (default `kind`), suite S16/S17 verde **senza modifiche alle asserzioni**.
- Frontend: `ReportPanel` rende le sezioni e le celle «<5»; degrado 401/403/error; export → coda approvazioni.

## 7. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Ri-identificazione da aggregati su popolazione piccola | soppressione k=5 centralizzata; solo distribuzioni marginali; test avversario |
| Deriva verso profilazione (§2) persistendo il matching | si persiste solo l'**aggregato per-run** (conteggi + gap), mai per-persona/pseudonimo |
| Un export non anonimo trapela (§7.3) | payload report = solo aggregati soppressi; download gated da approvazione + audit |
| Regressione degli export profili S16/S17 | `kind` con default `'profiles'`; suite S16/S17 invariata (criterio d'accettazione) |
| Bypass della soppressione via export | soppressione nel motore, riusata da vista ed export (un'unica fonte) |

## 8. Criteri di accettazione

- Suite backend (pytest/ruff/mypy) e frontend (vitest/typecheck/lint/build) **verdi**; suite S15/S16/S17 verdi **senza modifiche alle asserzioni**.
- Il motore produce aggregati **marginali** con **soppressione k=5** verificata (nessun conteggio 1..4 in nessun formato); nessuna PII/pseudonimo nell'output.
- `match_run` persistito **aggregato** ad ogni run (nessun pseudonimo); contratto di risposta del matching invariato.
- Vista supervisore (sola lettura, auditata) + export CSV+JSON gated dall'approvazione §7.3.
- Nessuna modifica a `/metrics`, al kiosk, o alle linee rosse. `kind='profiles'` retro-compatibile.

## 9. Relazione con gli altri documenti

- **`CLAUDE.md`** (nucleo protetto): conforme §2/§5/§6/§7.2/§7.3/§9/§11. **Nessuna modifica al nucleo.** La reportistica aggregata/anonima è esplicitamente Fase 2 (§8).
- **`STATO_TECNICO.md`**: alla conclusione, riga §15 (Sott. 28) + follow-up §14 (chiude «reportistica aggregata = Fase 2» e «persistenza esiti matching = Fase 2»); nota che resta la Fase 2·A (colloqui di follow-up).
- **Piano collegato:** scomposizione TDD — (1) migrazione 0007 + `match_run`; (2) persistenza aggregata nel flusso matching; (3) motore `compute_report` + soppressione k; (4) serializzazione CSV/JSON; (5) `GET /report` + RBAC/audit; (6) export `kind='report'` (riuso S16); (7) `ReportPanel` + export frontend.
