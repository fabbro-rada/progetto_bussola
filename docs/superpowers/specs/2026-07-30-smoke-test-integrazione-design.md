# Smoke test di integrazione — design

**Data:** 2026-07-30 · **Sottosistema:** infrastruttura di test/verifica · **Fase:** 1 (trasversale)

## Obiettivo

Dare fiducia che, **spostando il progetto su un PC nuovo partendo da zero**, tutto
si accenda e funzioni *insieme*. Non è un test di logica di dominio (già coperta
dalle suite esistenti), ma una verifica **trasversale del provisioning e del
cablaggio**: DB → migrazioni → bootstrap → autenticazione → operazione → audit → RBAC.

Due deliverable complementari, con divisione del lavoro netta, più un piccolo
endpoint di liveness a supporto:

0. **Endpoint `GET /health`** (nuovo, pubblico, senza auth né DB) — sonda di
   *liveness* convenzionale: `200 {"status": "ok"}`. Serve sia all'harness sia a
   `run-stack.sh` per sapere quando il backend accetta richieste.
1. **Harness full-stack** (`scripts/smoke-full-stack.sh`) — la fedeltà «PC nuovo».
   Avvia l'intero stack come farebbe una macchina appena clonata e **sonda
   attivamente** i percorsi critici. Lo esegue l'operatore sul PC nuovo.
2. **Smoke di integrazione in-process** (`backend/tests/test_smoke_integration.py`) —
   la verifica **profonda e continua** del cablaggio auth/DB/audit/RBAC, eseguibile
   nel gate `pytest` e in CI.

## Perché due strumenti

Coprono guasti diversi di un PC nuovo:

| Guasto tipico su PC nuovo | Lo prende l'harness | Lo prende lo smoke in-process |
|---|---|---|
| Dipendenze mancanti (venv, node_modules, Docker) | ✅ (preflight run-stack) | ❌ |
| DB non parte / migrazioni non applicate | ✅ | parziale (usa lo schema migrato) |
| Bootstrap admin fallisce | ✅ | ✅ (usa il modulo bootstrap reale) |
| Servizi non si legano alle porte (backend/kiosk/portale) | ✅ | ❌ |
| Cablaggio auth/DB/audit/RBAC errato | superficiale (via HTTP) | ✅ (a fondo) |
| Servizio che dimentica il `commit` | ✅ (server reale) | ✅ (connessione reale, vedi sotto) |

L'harness è più **fedele** ma **superficiale** sulla logica e **non eseguibile nel
gate**; lo smoke in-process è **profondo** e **gate-runnable** ma non avvia server
reale né frontend. Insieme coprono il quadro.

## Deliverable 1 — Harness full-stack (`scripts/smoke-full-stack.sh`)

**Cosa fa (in sequenza, `set -euo pipefail`):**

1. Avvia lo stack riusando `scripts/run-stack.sh` (che già fa: preflight dipendenze
   → `docker compose up -d db` + attesa `pg_isready` → migrazioni → bootstrap admin
   idempotente → avvio backend :8000, kiosk :5173, portale :5174). **Senza LLM**:
   lo smoke non copre il colloquio (che richiede il modello); resta fuori scope.
2. **Attende la prontezza del backend**: polling di `GET /health` finché risponde
   `200 {"status":"ok"}` (server su e pronto ad accettare richieste). `run-stack.sh`
   fa già la stessa attesa dopo aver avviato il backend, così non stampa gli URL
   prima che il backend accetti connessioni.
3. **Sonda i frontend**: `curl -fsS` su `:5173` e `:5174` → attende `200` con HTML.
4. **Sonda funzionale via HTTP** (prova reale del cablaggio, non solo «risponde»):
   - `POST /auth/login` con l'admin di bootstrap → attende `200` + `token`
     (+ `must_change_password: true`);
   - `POST /auth/change-password` (Bearer) → `204`;
   - `POST /auth/login` con la nuova password → `200`, `must_change_password: false`;
   - una **chiamata autenticata** con il token (es. `GET /metrics`) → `200`.
   Il parsing JSON usa il Python del venv del backend (nessuna dipendenza extra).
5. **Ferma lo stack** (`run-stack.sh stop`) in una `trap … EXIT`, così i servizi
   vengono spenti anche in caso di fallimento.
6. **Esito esplicito**: stampa `OK`/`FAIL` per ogni sonda; `exit 1` al primo
   fallimento (per via di `pipefail` e controlli espliciti), `exit 0` se tutto passa.

**Porte configurabili** via env (`SMOKE_BACKEND_PORT`, ecc.) con default allineati a
`run-stack.sh` (8000/5173/5174), così la logica delle sonde è testabile contro un
backend avviato su una porta libera.

**Caveat di onestà (documentato):** in questa sessione l'harness **non è eseguibile
per intero** perché un processo estraneo occupa `:8000` (lo rileva il preflight di
run-stack) e perché il full-stack è pesante. Viene verificato **staticamente**
(`shellcheck`) e la **logica delle sonde auth via curl** viene provata separatamente
contro un backend reale avviato su una porta libera con il DB di test. L'esecuzione
full-stack è dell'operatore, sul PC nuovo, con `:8000` libero — che è esattamente il
contesto d'uso previsto.

## Deliverable 2 — Smoke di integrazione in-process (`backend/tests/test_smoke_integration.py`)

Un unico percorso end-to-end che esercita il **cablaggio reale**, non gli endpoint
isolati come fanno i test dei router.

**Differenza chiave dai test dei router esistenti:** quelli iniettano una
**connessione condivisa** (`app_conn`) via override di `get_conn`, così le scritture
sono visibili anche senza `commit`. Lo smoke invece usa la **gestione connessione
reale dell'app** — `deps.get_conn` apre una connessione fresca per richiesta come
ruolo `bussola_app` e la **chiude senza commit** — puntata al DB di test tramite
`monkeypatch.setattr(config, "_DBNAME", "bussola_test")`. Così un servizio che
dimenticasse il `commit` **fallirebbe qui**, mentre passerebbe nei test a connessione
condivisa. Questo è il valore aggiunto dello smoke.

**Percorso (un test, o pochissimi test coesi):**

1. **Bootstrap** dell'admin col **modulo reale** (`bussola.auth.bootstrap`), non con
   la scorciatoia `make_operator`.
2. `POST /auth/login` admin+temp → `200`, `must_change_password: true`, `token`.
3. `POST /auth/change-password` (Bearer) → `204`.
4. `POST /auth/login` admin+nuova → `200`, `must_change_password: false`.
5. Admin `POST /operators` (crea un operatore, ruolo OPERATOR) → riceve la password
   temporanea dell'operatore.
6. Operatore: login → cambio password → token operatore.
7. Operatore `POST /job-requests` (operazione autenticata rappresentativa che
   **committa** e scrive audit) → `201/200`.
8. **RBAC**: operatore `POST /operators` (azione da admin) → `403`.
9. **Audit**: tramite una connessione di lettura diretta (`auditor_conn`/`owner_conn`)
   si verifica che le azioni HTTP abbiano **persistito** righe nel log di audit
   (login, cambio password, creazione operatore, creazione job request). Prova che
   l'audit trasversale funziona end-to-end (azione HTTP → riga committata nel DB).

**Isolamento:** usa le fixture DB esistenti (`db` per lo schema migrato e la pulizia
tra i test); il DB di test è già migrato **da zero** dalla fixture di sessione
`test_database`, quindi il solo fatto che la suite giri prova che le migrazioni
partono da un DB vuoto.

## Fuori scope

- Il **colloquio** e la **voce** (richiedono LLM/modelli): fuori dallo smoke.
- Prestazioni/carico.
- Il frontend oltre al «serve HTML e risponde 200» (l'a11y e2e del portale e del
  kiosk sono coperti altrove).

## Vincoli (dal nucleo)

- **§9 TDD, solo dati sintetici**: username/password di test sintetici; nessun dato
  reale di persone.
- **§3 open source, locale, budget nullo**: nessuna dipendenza nuova a pagamento;
  il parsing JSON nell'harness usa il Python del venv già presente.
- **§11 codice in inglese**, documenti in italiano.
- L'unica aggiunta al prodotto è l'endpoint `GET /health` (pubblico, senza auth né
  DB): rotta di liveness convenzionale, non espone alcun dato (nessun rischio §2/§5),
  utile oltre allo smoke (readiness di run-stack, probe di ops).

## Criteri di completamento

- `GET /health` risponde `200 {"status":"ok"}` senza auth (test nel gate); cablato in
  `create_app()` e usato da `run-stack.sh` per l'attesa di prontezza del backend.
- `test_smoke_integration.py` verde nel gate (`pytest -q && ruff check . && mypy src`),
  eseguito e verificato in sessione.
- `smoke-full-stack.sh` pulito a `shellcheck`; logica delle sonde auth provata contro
  un backend reale su porta libera; documentato il caveat `:8000`.
- `STATO_TECNICO.md` aggiornato (§11 Comandi + riga di decisione).
