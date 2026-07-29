# Reportistica aggregata e anonima (Fase 2·B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un report aggregato e anonimo della popolazione/attività del pilota (distribuzioni, copertura, esiti matching, serie storiche), consultabile dal supervisore in-portale ed esportabile come file CSV/JSON previa approvazione (§7.3).

**Architecture:** Backend `bussola.report` calcola aggregati **marginali** con **soppressione k=5** (celle 1–4 → `"<5"`). Una nuova tabella `matching.match_run` persiste gli esiti di matching **solo in aggregato per-run** (nessun pseudonimo). La vista è `GET /report` (sola lettura, supervisore, auditata); l'export riusa il workflow di approvazione S16 con un discriminante `export_request.kind`. Frontend: `ReportPanel` (vista) + creazione export → coda approvazioni S17 → download.

**Tech Stack:** Python 3.12 (FastAPI, Pydantic v2 `extra="forbid"`, psycopg3, Postgres); operator-portal (React 18 + Vite 5 + TS + react-router-dom + react-i18next).

## Global Constraints

- **Aggregato/anonimo per costruzione (§2/§5):** l'output NON contiene mai pseudonimi, testo libero non aggregato, né dati per-persona. Solo distribuzioni **marginali** (mai cross-tab fini).
- **Soppressione k=5:** ogni conteggio `1 ≤ n < 5` è reso col sentinello `"<5"` (stringa); `0` resta `0`; `n ≥ 5` resta il numero. La soppressione vive **in un solo punto** (il motore report) ed è riusata da vista ed export — nessuna via che la bypassi.
- **Persistenza matching solo aggregata (§5):** `match_run` salva conteggi + frequenze gap, **mai** lo pseudonimo o quale persona per quale posto.
- **RBAC senza allargamenti:** vista e creazione export report gated su `VIEW_METRICS` (già del supervisore); approvazione su `APPROVE_EXPORTS`. Il supervisore **non** ottiene `EXPORT_DATA`. Il server resta l'autorità (403).
- **Retro-compatibilità:** `export_request.kind` default `'profiles'`; gli export profili S16/S17 restano **identici** — le suite S16/S17 restano verdi **senza modifiche alle asserzioni**.
- **Contratto matching invariato:** la persistenza è un side-effect; `MatchingService.match(...)` restituisce la stessa `list[MatchResult]`.
- **§9:** TDD; solo dati sintetici; i test di anonimato/soppressione e no-PII vengono per primi. **§11:** codice inglese; stringhe UI i18n.
- **Gate backend:** `pytest -q && ruff check . && mypy src` (da `backend/`, `.venv` attiva, DB via `docker compose up -d db`). **Gate frontend:** `npm test && npm run typecheck && npm run lint && npm run build` (da `operator-portal/`).

---

## File Structure

**Backend** (`backend/src/bussola/`):
- `data/migrations/0007_report.sql` (nuovo) — `matching.match_run` + `export_request.kind`.
- `matching/match_runs.py` (nuovo) — `record_match_run(conn, ...)` (INSERT aggregato).
- `matching/service.py` (modifica) — chiama `record_match_run` prima del commit.
- `report/__init__.py`, `report/models.py`, `report/service.py`, `report/csv.py` (nuovi) — DTO `Report`, `compute_report`, serializzazione CSV.
- `api/routers/report.py` (nuovo) — `GET /report`, `POST /report/export`.
- `export/service.py`, `export/models.py`, `api/routers/exports.py` (modifica) — `kind`; download che dirama su `kind`.

**Frontend** (`operator-portal/src/`):
- `screens/report/ReportPanel.tsx` (nuovo) — vista + pulsante export.
- `screens/report/ReportPanel.test.tsx` (nuovo).
- `operatorClient` / `types` (modifica) — `getReport()`, `createReportExport()`; `kind` in `ExportRequest`.
- `rbac/nav.ts`, routing, i18n (`locales/it.ts`) (modifica) — voce «Report», rotta `/report`, stringhe.
- `screens/exports/ExportApprovals.tsx` (modifica) — mostra `kind='report'` in modo leggibile.

---

## Task 1: Migrazione 0007 — `match_run` + `export_request.kind`

**Files:**
- Create: `backend/src/bussola/data/migrations/0007_report.sql`
- Test: `backend/tests/data/test_migrations.py` (già esiste — aggiungere un test, NON modificare le asserzioni esistenti)

**Interfaces:**
- Produces: tabella `matching.match_run(id bigserial PK, created_at timestamptz NOT NULL DEFAULT now(), job_request_id bigint, evaluated_count int NOT NULL, compatible_count int NOT NULL, gaps jsonb NOT NULL DEFAULT '{}'::jsonb)`; colonna `export.export_request.kind text NOT NULL DEFAULT 'profiles' CHECK (kind IN ('profiles','report'))`.

- [ ] **Step 1: Scrivi il test (idempotenza + presenza oggetti)**

```python
# in backend/tests/data/test_migrations.py — NUOVO test, non toccare gli esistenti
def test_0007_adds_match_run_and_export_kind(clean_db_conn):
    from bussola.data.migrate import apply_migrations
    apply_migrations(clean_db_conn)
    with clean_db_conn.cursor() as cur:
        cur.execute("SELECT evaluated_count, compatible_count, gaps FROM matching.match_run WHERE false")
        cur.execute("SELECT kind FROM export.export_request WHERE false")
        cur.execute(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_schema='export' AND table_name='export_request' AND column_name='kind'"
        )
        assert "profiles" in (cur.fetchone()[0] or "")
```
(Usa la stessa fixture DB degli altri test in questo file; se il nome differisce, allinealo a quello esistente.)

- [ ] **Step 2: Esegui — deve fallire** (`pytest tests/data/test_migrations.py -q`; le tabelle/colonna non esistono ancora).

- [ ] **Step 3: Scrivi la migrazione** `0007_report.sql`:

```sql
-- Aggregate matching outcomes (per-run, NO pseudonym / NO per-person rows, §5)
-- and a kind discriminator on export requests to reuse the S16 approval workflow.
CREATE TABLE matching.match_run (
    id               bigserial PRIMARY KEY,
    created_at       timestamptz NOT NULL DEFAULT now(),
    job_request_id   bigint,
    evaluated_count  int NOT NULL,
    compatible_count int NOT NULL,
    gaps             jsonb NOT NULL DEFAULT '{}'::jsonb
);
GRANT SELECT, INSERT ON matching.match_run TO bussola_app;
GRANT USAGE, SELECT ON SEQUENCE matching.match_run_id_seq TO bussola_app;

ALTER TABLE export.export_request
    ADD COLUMN kind text NOT NULL DEFAULT 'profiles'
    CHECK (kind IN ('profiles', 'report'));
```
(Verifica il nome dello schema/owner e il pattern dei GRANT rispetto a `0006_exports.sql`; l'auditor NON deve avere accesso a `match_run`, coerente con S16.)

- [ ] **Step 4: Esegui — deve passare** (`pytest tests/data/test_migrations.py -q`).

- [ ] **Step 5: Commit** — `git add ... && git commit -m "feat(report): migration 0007 — match_run + export_request.kind"`

---

## Task 2: Persistenza aggregata dell'esito di matching

**Files:**
- Create: `backend/src/bussola/matching/match_runs.py`
- Modify: `backend/src/bussola/matching/service.py` (dentro `match()`, prima di `self._conn.commit()`)
- Test: `backend/tests/matching/test_match_runs.py` (nuovo)

**Interfaces:**
- Consumes: `MatchResult` (ha `gaps: list[GapItem]`, `GapItem.recommended_training: str`).
- Produces: `record_match_run(conn, *, job_request_id: int, evaluated_count: int, compatible_count: int, gaps: dict[str, int]) -> None` (INSERT in `matching.match_run`, no commit — il chiamante committa).

- [ ] **Step 1: Scrivi il test** (aggregato scritto; nessuno pseudonimo)

```python
def test_record_match_run_persists_aggregate_without_pseudonym(db_conn):
    from bussola.matching.match_runs import record_match_run
    record_match_run(db_conn, job_request_id=1, evaluated_count=7, compatible_count=3,
                     gaps={"HACCP": 2, "muletto": 1})
    db_conn.commit()
    with db_conn.cursor() as cur:
        cur.execute("SELECT evaluated_count, compatible_count, gaps FROM matching.match_run")
        ev, comp, gaps = cur.fetchone()
        assert (ev, comp) == (7, 3)
        assert gaps == {"HACCP": 2, "muletto": 1}
        # no per-person column exists at all:
        cur.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='matching' AND table_name='match_run'")
        cols = {r[0] for r in cur.fetchall()}
        assert "pseudonym_id" not in cols and "pseudonym" not in cols
```

- [ ] **Step 2: Esegui — deve fallire** (modulo inesistente).

- [ ] **Step 3: Implementa** `match_runs.py`:

```python
"""Persist ONLY aggregate matching outcomes (per run): counts + gap frequencies.
Never a pseudonym or a per-person row (§5 minimization; avoids §2 profiling)."""
from __future__ import annotations
import psycopg
from psycopg.types.json import Jsonb


def record_match_run(
    conn: psycopg.Connection, *, job_request_id: int,
    evaluated_count: int, compatible_count: int, gaps: dict[str, int],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matching.match_run "
            "(job_request_id, evaluated_count, compatible_count, gaps) VALUES (%s, %s, %s, %s)",
            (job_request_id, evaluated_count, compatible_count, Jsonb(gaps)),
        )
```

- [ ] **Step 4: Cabla in `service.py`** — dentro `match()`, calcola l'aggregato e scrivilo nella stessa transazione dell'audit (prima di `self._conn.commit()`), guardato come l'audit:

```python
# match(): raccogli la lista dei profili una sola volta per contarli
profiles = self._profiles.list_all()
evaluated = len(profiles)
for profile in profiles:
    ...
# ... dopo aver costruito `results` e chiamato self._audit(action="matching_run", ...):
if self._audit is not None:
    self._audit(action="matching_run", actor=actor,
                details={"job_request_id": str(job_id), "candidates": str(len(results))})
    from collections import Counter
    from bussola.matching.match_runs import record_match_run
    gaps_freq = Counter(g.recommended_training for r in results for g in r.gaps)
    record_match_run(self._conn, job_request_id=job_id, evaluated_count=evaluated,
                     compatible_count=len(results), gaps=dict(gaps_freq))
    self._conn.commit()
return results
```
(La persistenza avviene solo quando `self._audit` è configurato, come oggi il commit; con engine finti/unit senza audit, nessuna scrittura. Non cambiare il valore di ritorno.)

- [ ] **Step 5: Test d'invarianza del contratto** — un test che `match()` restituisce ancora la stessa `list[MatchResult]` (asserzione sul tipo/contenuto) E che dopo il run esiste una riga `match_run` con `compatible_count == len(results)`. Riusa il pattern di setup dei test esistenti in `tests/matching/`.

- [ ] **Step 6: Esegui il gate matching** — `pytest tests/matching -q && ruff check . && mypy src`. Le suite matching esistenti restano verdi **senza modifiche alle asserzioni**.

- [ ] **Step 7: Commit** — `feat(report): persist aggregate match_run per matching run (no per-person data)`

---

## Task 3: Motore report `compute_report` + soppressione k=5

**Files:**
- Create: `backend/src/bussola/report/__init__.py`, `backend/src/bussola/report/models.py`, `backend/src/bussola/report/service.py`
- Test: `backend/tests/report/__init__.py`, `backend/tests/report/test_report.py` (nuovi)

**Interfaces:**
- Consumes: `profiles.work_profile.profile` (JSONB), `profiles.work_profile.created_at`; `matching.job_request` (`created_at`); `matching.match_run`. Enum in `bussola.profile.models` / `bussola.matching.models` (LanguageLevel, SkillKind, EvidenceGrade, Availability, WorkConstraint).
- Produces:
  ```python
  Count = int | Literal["<5"]  # cella soppressa
  class Coverage(BaseModel): total_profiles:int; completed_profiles:int; average_completeness:float; completeness_histogram: dict[str, Count]
  class MatchingAgg(BaseModel): runs:int; evaluated:int; compatible:int; compatible_rate:float; top_gaps: dict[str, Count]
  class Trends(BaseModel): profiles_by_week: dict[str, Count]; job_requests_by_week: dict[str, Count]
  class Report(BaseModel):  # model_config = ConfigDict(extra="forbid")
      coverage: Coverage
      languages: dict[str, Count]      # "<lang> (<level>)" -> count
      skill_kinds: dict[str, Count]
      skill_evidence: dict[str, Count]
      availability: dict[str, Count]
      constraints: dict[str, Count]
      total_job_requests: int
      matching: MatchingAgg
      trends: Trends
  def compute_report(conn: psycopg.Connection, *, k: int = 5) -> Report: ...
  def suppress(n: int, k: int = 5) -> Count:  # n<=0 -> 0 ; 0<n<k -> f"<{k}" ; else n
  ```

- [ ] **Step 1: Scrivi i test dell'ANONIMATO per primi (§9)**

```python
def test_suppress_hides_small_cells():
    from bussola.report.service import suppress
    assert suppress(0) == 0
    assert suppress(1) == "<5" and suppress(4) == "<5"
    assert suppress(5) == 5 and suppress(42) == 42

def test_report_suppresses_rare_languages(db_conn):
    # inserisci: 5 profili con lingua "it", 1 con lingua "ti" (tigrino)
    _seed_profiles(db_conn, langs=["it"]*5 + ["ti"])
    from bussola.report.service import compute_report
    rep = compute_report(db_conn, k=5)
    # una lingua con 1 solo profilo non deve MAI comparire come numero 1..4
    assert all(v == "<5" or v == 0 or isinstance(v, int) and v >= 5 for v in rep.languages.values())
    ti = next((v for kk, v in rep.languages.items() if kk.startswith("ti")), None)
    assert ti in (None, "<5")  # tigrino soppresso o assente
    # e nessuno pseudonimo/testo libero nel dump
    dump = rep.model_dump_json()
    assert "pseudonym" not in dump
```
(Scrivi `_seed_profiles` come helper nel test: INSERT di `profiles.work_profile` con JSONB minimi contenenti le `languages` volute. Riusa la fixture DB del progetto.)

- [ ] **Step 2: Esegui — deve fallire.**

- [ ] **Step 3: Implementa `service.py`** — `suppress()`; `compute_report()` che:
  - legge tutti i `profile` JSONB e i `created_at`; calcola `Coverage` (total, completed = completezza 1.0 con la stessa definizione di `bussola.metrics`, average, istogramma per bucket 0/20/40/60/80/100%);
  - conta le distribuzioni marginali **enumerate**: `languages` (chiave `"<language> (<level>)"`), `skill_kinds`, `skill_evidence`, `availability`, `constraints`;
  - `total_job_requests` = COUNT job_request; `matching` = aggrega `match_run` (runs, sum evaluated, sum compatible, rate, top_gaps = somma delle mappe `gaps`);
  - `trends` = conteggi per settimana ISO (`date_trunc('week', created_at)`) di profili completati e richieste;
  - applica `suppress(n, k)` a **ogni** conteggio di distribuzione, istogramma, top_gaps e trend (NON a `total_profiles`/`average`/`rate`, che sono aggregati globali non identificanti).

- [ ] **Step 4: Esegui — deve passare** (i test anonimato + correttezza).

- [ ] **Step 5: Test di correttezza aggregati** — su fixture nota, verifica i valori di `coverage`, una distribuzione ≥5 (numero esatto), `matching` (rate = compatible/evaluated), e un trend settimanale.

- [ ] **Step 6: Gate** — `pytest tests/report -q && ruff check . && mypy src`.

- [ ] **Step 7: Commit** — `feat(report): compute_report engine with k=5 small-cell suppression`

---

## Task 4: Serializzazione CSV del report

**Files:**
- Create: `backend/src/bussola/report/csv.py`
- Test: `backend/tests/report/test_report_csv.py` (nuovo)

**Interfaces:**
- Produces: `report_to_csv(report: Report) -> str` — CSV multi-sezione (una tabella per blocco: `section,key,value`), con le celle soppresse rese come `"<5"`. Il JSON è `report.model_dump()` (nessuna funzione dedicata).

- [ ] **Step 1: Test**

```python
def test_report_to_csv_renders_sections_and_keeps_suppression():
    from bussola.report.models import Report
    from bussola.report.csv import report_to_csv
    rep = _minimal_report(languages={"it (fluent)": 6, "ti (basic)": "<5"})
    csv = report_to_csv(rep)
    assert "languages,it (fluent),6" in csv
    assert "languages,ti (basic),<5" in csv   # cella soppressa resa verbatim
    assert "pseudonym" not in csv
```
(`_minimal_report` costruisce un `Report` valido con sezioni minime.)

- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa** `report_to_csv` (itera le sezioni del DTO → righe `section,key,value`; usa il modulo `csv` stdlib con quoting).
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Commit** — `feat(report): CSV serialization of the aggregate report`

---

## Task 5: `GET /report` — vista supervisore (sola lettura, auditata)

**Files:**
- Create: `backend/src/bussola/api/routers/report.py`
- Modify: `backend/src/bussola/api/app.py` (include il router)
- Test: `backend/tests/api/test_report_router.py` (nuovo)

**Interfaces:**
- Consumes: `compute_report`; `require_permission(Permission.VIEW_METRICS)`; `append_audit`. Mirror di `api/routers/metrics.py` (leggilo per il pattern esatto di conn/audit/permission).
- Produces: `GET /report` → `Report` (JSON), audit `report_viewed`.

- [ ] **Step 1: Test** (RBAC + audit + shape). Mirror `tests/api/test_metrics_router.py`:

```python
def test_report_requires_supervisor(client_as):  # helper esistente per ruoli
    assert client_as("operator").get("/report").status_code == 403
    assert client_as("admin").get("/report").status_code == 403
    r = client_as("supervisor").get("/report")
    assert r.status_code == 200
    assert "coverage" in r.json()

def test_report_view_is_audited(client_as, db_conn):
    client_as("supervisor").get("/report")
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log WHERE action='report_viewed'")
        assert cur.fetchone()[0] >= 1
```
(Usa gli stessi helper/fixture dei test router esistenti — `test_metrics_router.py` è il modello 1:1.)

- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa il router** (copia la forma di `metrics.py`: `_view = require_permission(Permission.VIEW_METRICS)`; dentro l'handler `compute_report(conn)`, `append_audit(conn, action="report_viewed", actor=..., commit=True)`), e includilo in `app.py`.
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Gate** — `pytest -q && ruff check . && mypy src`.
- [ ] **Step 6: Commit** — `feat(report): GET /report supervisor view (read-only, audited)`

---

## Task 6: Export del report via workflow S16 (`kind='report'`)

**Files:**
- Modify: `backend/src/bussola/export/models.py` (`ExportRequest` + `kind`), `backend/src/bussola/export/service.py` (`create_request` accetta `kind`; `generate_payload`/download diramano su `kind`), `backend/src/bussola/api/routers/exports.py` (download con `?format=`, dirama su kind), `backend/src/bussola/api/routers/report.py` (`POST /report/export`).
- Test: `backend/tests/api/test_report_export.py` (nuovo); NON modificare `tests/**/test_export*` esistenti.

**Interfaces:**
- Consumes: `ExportService`, `compute_report`, `report_to_csv`.
- Produces: `POST /report/export` (VIEW_METRICS) → crea `export_request` con `kind='report'`, `filters={}`, `reason` opzionale; `GET /exports/{id}/download?format=csv|json` → per `kind='report'` restituisce il file (Response `text/csv` o `application/json` + `Content-Disposition`), gated su `approved` + proprietà; per `kind='profiles'` **invariato**.

- [ ] **Step 1: Test retro-compatibilità (per primo)** — un test che il flusso S16 profili è invariato: create (operatore) → pending con `kind='profiles'` → approve (supervisore) → download = lista profili. (Se un helper/fixture S16 esiste, riusalo.)

- [ ] **Step 2: Test del percorso report**

```python
def test_report_export_end_to_end(client_as):
    # supervisore crea la richiesta report, la approva, poi scarica CSV e JSON
    rid = client_as("supervisor").post("/report/export").json()["id"]
    assert client_as("operator").post("/report/export").status_code == 403  # solo VIEW_METRICS
    client_as("supervisor").post(f"/exports/{rid}/approve")
    j = client_as("supervisor").get(f"/exports/{rid}/download?format=json")
    assert j.status_code == 200 and "coverage" in j.json()
    c = client_as("supervisor").get(f"/exports/{rid}/download?format=csv")
    assert c.status_code == 200 and "text/csv" in c.headers["content-type"]

def test_report_download_gated_until_approved(client_as):
    rid = client_as("supervisor").post("/report/export").json()["id"]
    assert client_as("supervisor").get(f"/exports/{rid}/download").status_code == 409  # pending
```

- [ ] **Step 3: Esegui — deve fallire.**
- [ ] **Step 4: Implementa** — `kind` nel DTO/SELECT (`_FIELDS` include `kind`); `create_request(*, actor, filters, reason, kind='profiles')`; nel download, se `kind=='report'`: `compute_report(conn)` + (`report_to_csv` se `format=csv`, altrimenti `model_dump`) → `Response` col media-type e `Content-Disposition: attachment; filename=report.{ext}`; il gating (approved + proprietà) resta quello esistente. `POST /report/export` in `report.py` chiama `ExportService.create_request(kind='report', filters={}, reason=...)`.
- [ ] **Step 5: Esegui — deve passare** (retro-compat + report path).
- [ ] **Step 6: Gate completo** — `pytest -q && ruff check . && mypy src`. Suite S16 verde **senza modifiche alle asserzioni** (il default `kind='profiles'` lo garantisce; se un'asserzione S16 dovesse cambiare → STOP, non è retro-compatibile).
- [ ] **Step 7: Commit** — `feat(report): authorized CSV/JSON report export via the S16 approval workflow`

---

## Task 7: Frontend — `ReportPanel` + export

**Files:**
- Create: `operator-portal/src/screens/report/ReportPanel.tsx`, `.../ReportPanel.test.tsx`
- Modify: `operator-portal/src/api/operatorClient.ts` (+`getReport()`, `createReportExport()`), `src/types.ts` (`Report` types; `kind` su `ExportRequest`), `src/rbac/nav.ts` (voce «Report», `built`), routing (`/report`), `src/i18n/locales/it.ts` (stringhe), `src/screens/exports/ExportApprovals.tsx` (mostra `kind='report'` come «Report aggregato»).
- Test: `ReportPanel.test.tsx` (nuovo); NON modificare i test export esistenti.

**Interfaces:**
- Consumes: `GET /report`, `POST /report/export`, la coda approvazioni S17.
- Produces: pannello supervisore `/report`.

- [ ] **Step 1: Test** (mirror `MetricsPanel.test.tsx`): con client fake supervisore che restituisce un report, il pannello mostra una sezione (es. copertura) e una cella soppressa resa «<5»; 403 → messaggio forbidden; il pulsante «Esporta report» chiama `createReportExport`. Verifica anche che `ExportApprovals` renda una richiesta `kind='report'` con etichetta «Report aggregato» (non i filtri profilo).

- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa** `getReport()`/`createReportExport()` (fail-closed, pattern `getMetrics`), il tipo `Report` + `kind` su `ExportRequest`, `ReportPanel` (usa `useFetchOnMount`; rende le sezioni; «<5» reso verbatim; pulsante export → `createReportExport` → messaggio «richiesta inviata, in attesa di approvazione»), nav «Report» `built` + rotta `/report` (dietro `ProtectedRoute`, il server impone l'RBAC), stringhe i18n, e in `ExportApprovals` un ramo per `kind==='report'`.
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Gate frontend** — `npm test && npm run typecheck && npm run lint && npm run build`. I test export/approvals esistenti restano verdi **senza modifiche alle asserzioni** (se cambiano → STOP).
- [ ] **Step 6: Commit** — `feat(operator-portal): supervisor report panel + authorized report export`

---

## Self-Review (autore)

- **Copertura spec:** §2/§3 spec → Task 1–2 (persistenza aggregata) ; motore+soppressione → Task 3 ; CSV/JSON → Task 4/6 ; vista → Task 5 ; export §7.3 → Task 6 ; frontend → Task 7. Tutte le sezioni del report (coverage/distribuzioni/matching/trends) in Task 3.
- **Anonimato:** la soppressione vive solo in `report/service.py` (Task 3) e vista/export la riusano (Task 5/6) — nessun bypass. Test anonimato scritti **per primi** (Task 3 Step 1).
- **Retro-compatibilità:** `kind` default `'profiles'` (Task 1); Task 6 ha un test retro-compat **per primo** e la regola STOP se un'asserzione S16 cambia.
- **RBAC:** creazione report-export su `VIEW_METRICS` via endpoint dedicato `POST /report/export` (Task 6) — nessun `EXPORT_DATA` al supervisore.
- **Type consistency:** `Count = int | Literal["<5"]`, `Report`/`compute_report`/`suppress`/`record_match_run`/`report_to_csv` coerenti tra i task; `kind` su `ExportRequest` (backend Task 6 + frontend Task 7).
- **Contratto matching invariato:** Task 2 Step 5 lo verifica.

---

## Execution Handoff

Piano salvato in `docs/superpowers/plans/2026-07-29-report-aggregato-anonimo.md`. Due opzioni di esecuzione:

**1. Subagent-Driven (consigliata)** — un subagent implementer fresco per task + review a due stadi tra i task, iterazione veloce.

**2. Inline Execution** — esecuzione in questa sessione con executing-plans, a checkpoint.

Quale approccio?
