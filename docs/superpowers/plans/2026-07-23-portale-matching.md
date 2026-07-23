# Piano — Sottosistema 6: Portale operatore — core matching

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Richieste di lavoro + matching spiegabile (gate deterministico dei vincoli rigidi + giudizio semantico LLM ancorato) con gap formativi, e consultazione/ricerca profili — endpoint operatore RBAC-gated e auditati.

**Architecture:** Package `bussola.matching` (modelli, gate deterministico, giudizio semantico LLM, scoring, gap, servizio, repo richieste) + estensione `ProfileRepository` (ricerca) + migrazione `0005_job_requests.sql` (schema `matching`) + router FastAPI operatore. Poggia su S1 (`WorkProfile`/enum), S2 (`ProfileRepository`, audit, ruoli DB), S3 (client LLM constrained), S5 (RBAC, `require_permission`, layer FastAPI).

**Tech Stack:** Python 3.12, Pydantic, psycopg3 (JSONB + text[]), httpx-LLM (constrained JSON), FastAPI/TestClient, pytest. Nessuna nuova dipendenza.

## Global Constraints

- **Mai una scatola nera** (§2/§10): matching **ibrido** — vincoli rigidi (disponibilità, turni notturni, livello lingua) via **gate deterministico** che esclude con motivo; idoneità semantica sul testo libero via **LLM con output strutturato ancorato** (per requisito: soddisfatto/no + evidenza citata dal profilo). Il punteggio è **derivato dai contributi mostrati**, mai opaco.
- **L'LLM giudica SOLO l'idoneità lavorativa** rispetto ai requisiti espliciti; mai giudizi sulla persona (§2/§4). Constrained JSON + `temp 0`; fail-safe: requisito non soddisfatto se output non valido.
- **Vincoli rigidi PRIMA dell'LLM**: il gate deterministico esclude i non-compatibili (e limita le chiamate LLM). L'LLM non tocca i vincoli rigidi.
- **Solo-lavoro per costruzione** (§2/§5): `JobRequest` è una whitelist Pydantic `extra="forbid"`; nessun criterio discriminatorio/extra-lavorativo. I profili sono già solo-lavoro (S1).
- **RBAC + audit** (§6/§7.3): endpoint gated da `require_permission` (permessi §6 dichiarati in S5); ogni run/consultazione auditata (`actor` dalla sessione, `details` whitelist).
- **Matching on-demand, non persistito** (Fase 1).
- **TDD; solo dati sintetici** (§9); **codice in inglese** (§11).
- **Gate:** `ruff check` + `ruff format --check` (file toccati) + `mypy --strict` su `backend/src` puliti.
- **Shell state non persiste tra chiamate Bash:** percorsi assoluti `backend/.venv/bin/...` dalla radice del repo; niente `cd`. Postgres attivo su :15432 (i test DB girano). I test che richiedono l'LLM reale (`requires_llm`) si skippano se llama-server è giù.
- I test DB usano le fixture condivise (`tests/conftest.py`: `app_conn`/`owner_conn`/`auditor_conn`, skip a setup se Postgres è giù) + `pytestmark = pytest.mark.usefixtures("db")`.

---

## Struttura dei file

```
backend/src/bussola/
├── data/
│   ├── profiles.py                      # + list_all() / search() (read, no commit)
│   └── migrations/0005_job_requests.sql # schema matching + job_request
├── matching/
│   ├── __init__.py
│   ├── models.py            # JobRequest, JobRequestCreate, RequiredLanguage, RequirementVerdict, ConstraintOutcome, GapItem, MatchResult
│   ├── errors.py            # JobRequestNotFound
│   ├── requests.py          # JobRequestRepository (CRUD, no commit interno)
│   ├── hard_constraints.py  # evaluate(profile, job) -> ConstraintOutcome
│   ├── semantic.py          # judge_requirements(client, profile, job, language) -> list[RequirementVerdict]
│   ├── scoring.py           # score(verdicts) -> float
│   ├── gaps.py              # compute(verdicts, profile) -> list[GapItem]
│   └── service.py           # MatchingService.match(job_id, *, actor) -> list[MatchResult]
└── api/
    ├── app.py                           # + include dei 3 router
    └── routers/
        ├── job_requests.py
        ├── matching.py
        └── profiles.py
backend/tests/
├── conftest.py                          # + troncamento matching.job_request
├── matching/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_migration_matching.py
│   ├── test_requests.py
│   ├── test_hard_constraints.py
│   ├── test_semantic.py
│   ├── test_scoring_gaps.py
│   ├── test_service.py
│   └── test_service_live.py             # integrazione, requires_llm + DB
├── data/test_profiles_search.py
└── api/
    ├── test_job_requests_router.py
    ├── test_matching_router.py
    └── test_profiles_router.py
```

---

### Task 1: Modelli di dominio (`matching/models.py` + `errors.py`)

**Files:**
- Create: `backend/src/bussola/matching/__init__.py` (vuoto), `backend/src/bussola/matching/models.py`, `backend/src/bussola/matching/errors.py`
- Test: `backend/tests/matching/__init__.py` (vuoto), `backend/tests/matching/test_models.py`

**Interfaces:**
- Produces (tutti Pydantic `extra="forbid"`):
  - `RequiredLanguage(language: str[2..32], min_level: LanguageLevel)`.
  - `JobRequestCreate(title, sector, description="", required_skills: list[str], required_languages: list[RequiredLanguage], required_availability: Availability|None, involves_night_shifts: bool=False, training_prerequisites: list[str])`.
  - `JobRequest(JobRequestCreate + id: int, created_by: str)`.
  - `RequirementVerdict(requirement: str, satisfied: bool, evidence: str|None=None)`.
  - `ConstraintOutcome(compatible: bool, reasons: list[str])`.
  - `GapItem(requirement: str, recommended_training: str)`.
  - `MatchResult(pseudonym_id: str, score: float, requirements: list[RequirementVerdict], constraint: ConstraintOutcome, gaps: list[GapItem])`.
  - `errors.JobRequestNotFound(Exception)`.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/matching/__init__.py`: (vuoto)

File `backend/tests/matching/test_models.py`:
```python
import pytest
from pydantic import ValidationError

from bussola.matching.models import (
    JobRequest,
    JobRequestCreate,
    MatchResult,
    RequiredLanguage,
    RequirementVerdict,
)
from bussola.profile.enums import Availability, LanguageLevel


def test_job_request_create_forbids_extra_fields():
    with pytest.raises(ValidationError):
        JobRequestCreate(title="Cuoco", sector="ristorazione", danger_score=9)


def test_job_request_create_minimal():
    jr = JobRequestCreate(title="Cuoco", sector="ristorazione")
    assert jr.required_skills == []
    assert jr.involves_night_shifts is False
    assert jr.required_availability is None


def test_required_language_roundtrip():
    rl = RequiredLanguage(language="it", min_level=LanguageLevel.INTERMEDIATE)
    assert rl.min_level is LanguageLevel.INTERMEDIATE


def test_job_request_has_id_and_creator():
    jr = JobRequest(
        id=1, created_by="op1", title="Cuoco", sector="ristorazione",
        required_availability=Availability.FULL_TIME,
    )
    assert jr.id == 1 and jr.created_by == "op1"


def test_match_result_shape():
    mr = MatchResult(
        pseudonym_id="P-1", score=0.5,
        requirements=[RequirementVerdict(requirement="cooking", satisfied=True, evidence="Cucina")],
        constraint={"compatible": True, "reasons": ["ok"]},
        gaps=[],
    )
    assert mr.requirements[0].satisfied is True
    assert mr.constraint.compatible is True
```

- [ ] **Step 2: Eseguire (deve fallire)** — `backend/.venv/bin/pytest backend/tests/matching/test_models.py -q` → FAIL (modulo inesistente).

- [ ] **Step 3: Implementare**

File `backend/src/bussola/matching/__init__.py`: (vuoto)

File `backend/src/bussola/matching/errors.py`:
```python
"""Matching domain errors."""

from __future__ import annotations


class JobRequestNotFound(Exception):
    pass
```

File `backend/src/bussola/matching/models.py`:
```python
"""Matching domain models. All work-only whitelists (extra="forbid"): a job
request cannot carry discriminatory or non-work criteria by construction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from bussola.profile.enums import Availability, LanguageLevel

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)
_TEXT = 200


class RequiredLanguage(BaseModel):
    model_config = _STRICT
    language: str = Field(min_length=2, max_length=32)
    min_level: LanguageLevel


class JobRequestCreate(BaseModel):
    model_config = _STRICT
    title: str = Field(min_length=1, max_length=_TEXT)
    sector: str = Field(min_length=1, max_length=_TEXT)
    description: str = Field(default="", max_length=2000)
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    required_languages: list[RequiredLanguage] = Field(default_factory=list, max_length=10)
    required_availability: Availability | None = None
    involves_night_shifts: bool = False
    training_prerequisites: list[str] = Field(default_factory=list, max_length=20)


class JobRequest(JobRequestCreate):
    id: int
    created_by: str


class RequirementVerdict(BaseModel):
    model_config = _STRICT
    requirement: str
    satisfied: bool
    evidence: str | None = None


class ConstraintOutcome(BaseModel):
    model_config = _STRICT
    compatible: bool
    reasons: list[str] = Field(default_factory=list)


class GapItem(BaseModel):
    model_config = _STRICT
    requirement: str
    recommended_training: str


class MatchResult(BaseModel):
    model_config = _STRICT
    pseudonym_id: str
    score: float
    requirements: list[RequirementVerdict] = Field(default_factory=list)
    constraint: ConstraintOutcome
    gaps: list[GapItem] = Field(default_factory=list)
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS (5 test).

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/matching/__init__.py backend/src/bussola/matching/models.py backend/src/bussola/matching/errors.py backend/tests/matching/__init__.py backend/tests/matching/test_models.py
git commit -m "feat(matching): modelli di dominio (JobRequest + risultati) whitelist"
```

---

### Task 2: Migrazione `0005_job_requests.sql` + troncamento fixture

**Files:**
- Create: `backend/src/bussola/data/migrations/0005_job_requests.sql`
- Modify: `backend/tests/conftest.py` (troncare `matching.job_request`)
- Test: `backend/tests/matching/test_migration_matching.py`

**Interfaces:**
- Produces: schema `matching` + tabella `matching.job_request` + grant per `bussola_app` (SELECT/INSERT/UPDATE, no DELETE); `bussola_auditor` nessun accesso.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/matching/test_migration_matching.py`:
```python
import psycopg
import pytest

pytestmark = pytest.mark.usefixtures("db")


def test_matching_schema_and_table_exist(owner_conn: psycopg.Connection):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT to_regclass('matching.job_request')")
        assert cur.fetchone()[0] is not None


def test_app_can_write_matching_but_auditor_cannot(
    app_conn: psycopg.Connection, auditor_conn: psycopg.Connection
):
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matching.job_request (title, sector, created_by) "
            "VALUES ('Cuoco', 'ristorazione', 'op1')"
        )
    app_conn.commit()
    with auditor_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT count(*) FROM matching.job_request")
    auditor_conn.rollback()
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL (schema inesistente).

- [ ] **Step 3: Implementare la migrazione**

File `backend/src/bussola/data/migrations/0005_job_requests.sql`:
```sql
-- Job requests (positions offered by companies). Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS matching AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA matching TO bussola_app;
-- auditor gets NO access to the matching schema (absence of grant).

CREATE TABLE matching.job_request (
    id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title                  text NOT NULL,
    sector                 text NOT NULL,
    description            text NOT NULL DEFAULT '',
    required_skills        text[] NOT NULL DEFAULT '{}',
    required_languages     jsonb NOT NULL DEFAULT '[]'::jsonb,
    required_availability  text,
    involves_night_shifts  boolean NOT NULL DEFAULT false,
    training_prerequisites text[] NOT NULL DEFAULT '{}',
    created_by             text NOT NULL,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now()
);

-- No DELETE (positions are closed by convention, not deleted, in Fase 1).
GRANT SELECT, INSERT, UPDATE ON matching.job_request TO bussola_app;
```

- [ ] **Step 4: Estendere il troncamento in `backend/tests/conftest.py`**

Nel fixture `db`, dentro lo stesso `with owner.cursor() as cur:`, aggiungere dopo i troncamenti esistenti:
```python
            cur.execute("SELECT to_regclass('matching.job_request')")
            job_request_tbl = cur.fetchone()[0]
            if job_request_tbl is not None:
                cur.execute("TRUNCATE matching.job_request RESTART IDENTITY")
```

- [ ] **Step 5: Eseguire (devono passare)** — PASS. Full suite per non-regressione: `backend/.venv/bin/pytest backend/tests -q`.

- [ ] **Step 6: Committare**
```bash
git add backend/src/bussola/data/migrations/0005_job_requests.sql backend/tests/conftest.py backend/tests/matching/test_migration_matching.py
git commit -m "feat(matching): schema DB matching + tabella job_request + troncamento fixture"
```

---

### Task 3: `JobRequestRepository` (`requests.py`)

**Files:**
- Create: `backend/src/bussola/matching/requests.py`
- Test: `backend/tests/matching/test_requests.py`

**Interfaces:**
- Consumes: `models.{JobRequest,JobRequestCreate,RequiredLanguage}`, `errors.JobRequestNotFound`.
- Produces: `JobRequestRepository(conn)` con `create(req: JobRequestCreate, *, created_by: str) -> JobRequest`, `get(job_id: int) -> JobRequest | None`, `list_all() -> list[JobRequest]`. Nessun commit interno.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/matching/test_requests.py`:
```python
import psycopg
import pytest

from bussola.matching.models import JobRequestCreate, RequiredLanguage
from bussola.matching.requests import JobRequestRepository
from bussola.profile.enums import Availability, LanguageLevel

pytestmark = pytest.mark.usefixtures("db")


def _sample() -> JobRequestCreate:
    return JobRequestCreate(
        title="Cuoco", sector="ristorazione", description="mensa",
        required_skills=["cucina", "igiene alimentare"],
        required_languages=[RequiredLanguage(language="it", min_level=LanguageLevel.INTERMEDIATE)],
        required_availability=Availability.FULL_TIME,
        involves_night_shifts=False,
        training_prerequisites=["sicurezza alimentare"],
    )


def test_create_and_get(app_conn: psycopg.Connection):
    repo = JobRequestRepository(app_conn)
    jr = repo.create(_sample(), created_by="op1")
    app_conn.commit()
    assert jr.id > 0 and jr.created_by == "op1"
    got = repo.get(jr.id)
    assert got is not None
    assert got.required_skills == ["cucina", "igiene alimentare"]
    assert got.required_languages[0].language == "it"
    assert got.required_availability is Availability.FULL_TIME


def test_get_missing_returns_none(app_conn: psycopg.Connection):
    assert JobRequestRepository(app_conn).get(999999) is None


def test_list_all(app_conn: psycopg.Connection):
    repo = JobRequestRepository(app_conn)
    repo.create(_sample(), created_by="op1")
    repo.create(_sample(), created_by="op1")
    app_conn.commit()
    assert len(repo.list_all()) == 2
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/matching/requests.py`:
```python
"""Job request persistence (matching.job_request). No internal commit."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from bussola.matching.models import JobRequest, JobRequestCreate, RequiredLanguage
from bussola.profile.enums import Availability

_COLS = (
    "id, title, sector, description, required_skills, required_languages, "
    "required_availability, involves_night_shifts, training_prerequisites, created_by"
)


def _to_job_request(row: tuple[Any, ...]) -> JobRequest:
    return JobRequest(
        id=row[0],
        title=row[1],
        sector=row[2],
        description=row[3],
        required_skills=list(row[4]),
        required_languages=[RequiredLanguage.model_validate(item) for item in row[5]],
        required_availability=Availability(row[6]) if row[6] is not None else None,
        involves_night_shifts=row[7],
        training_prerequisites=list(row[8]),
        created_by=row[9],
    )


class JobRequestRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, req: JobRequestCreate, *, created_by: str) -> JobRequest:
        languages = [lang.model_dump(mode="json") for lang in req.required_languages]
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO matching.job_request "
                "(title, sector, description, required_skills, required_languages, "
                "required_availability, involves_night_shifts, training_prerequisites, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING " + _COLS,
                (
                    req.title,
                    req.sector,
                    req.description,
                    req.required_skills,
                    Jsonb(languages),
                    req.required_availability.value if req.required_availability else None,
                    req.involves_night_shifts,
                    req.training_prerequisites,
                    created_by,
                ),
            )
            row = cur.fetchone()
        assert row is not None
        return _to_job_request(row)

    def get(self, job_id: int) -> JobRequest | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _COLS + " FROM matching.job_request WHERE id = %s", (job_id,)
            )
            row = cur.fetchone()
        return _to_job_request(row) if row is not None else None

    def list_all(self) -> list[JobRequest]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT " + _COLS + " FROM matching.job_request ORDER BY id")
            rows = cur.fetchall()
        return [_to_job_request(r) for r in rows]
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/matching/requests.py backend/tests/matching/test_requests.py
git commit -m "feat(matching): JobRequestRepository (CRUD, senza commit interno)"
```

---

### Task 4: Gate deterministico dei vincoli rigidi (`hard_constraints.py`)

**Files:**
- Create: `backend/src/bussola/matching/hard_constraints.py`
- Test: `backend/tests/matching/test_hard_constraints.py`

**Interfaces:**
- Consumes: `WorkProfile`/`Aspiration` (S1), enum `Availability`/`WorkConstraint`/`LanguageLevel`, `models.{JobRequest,ConstraintOutcome}`.
- Produces: `evaluate(profile: WorkProfile, job: JobRequest) -> ConstraintOutcome` — deterministico; `compatible=False` con **motivi espliciti** su conflitto; `compatible=True` (con motivi «soddisfatto») altrimenti. Regole: disponibilità, turni notturni, livello lingua.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/matching/test_hard_constraints.py`:
```python
from bussola.matching.hard_constraints import evaluate
from bussola.matching.models import JobRequest, RequiredLanguage
from bussola.profile.enums import Availability, LanguageLevel, WorkConstraint
from bussola.profile.models import Aspiration, LanguageKnown, WorkProfile


def _job(**kw) -> JobRequest:
    base = dict(id=1, created_by="op1", title="t", sector="s")
    base.update(kw)
    return JobRequest(**base)


def test_night_shift_conflict_excludes_with_reason():
    profile = WorkProfile(
        pseudonym_id="P-1",
        aspiration=Aspiration(constraints=[WorkConstraint.NO_NIGHT_SHIFTS]),
    )
    out = evaluate(profile, _job(involves_night_shifts=True))
    assert out.compatible is False
    assert any("night" in r.lower() for r in out.reasons)


def test_part_time_only_conflicts_with_full_time():
    profile = WorkProfile(
        pseudonym_id="P-1",
        aspiration=Aspiration(availability=Availability.PART_TIME),
    )
    out = evaluate(profile, _job(required_availability=Availability.FULL_TIME))
    assert out.compatible is False


def test_flexible_availability_is_compatible():
    profile = WorkProfile(
        pseudonym_id="P-1", aspiration=Aspiration(availability=Availability.FLEXIBLE)
    )
    out = evaluate(profile, _job(required_availability=Availability.FULL_TIME))
    assert out.compatible is True


def test_missing_language_level_excludes():
    profile = WorkProfile(
        pseudonym_id="P-1",
        languages=[LanguageKnown(language="it", level=LanguageLevel.BASIC)],
    )
    out = evaluate(
        profile,
        _job(required_languages=[RequiredLanguage(language="it", min_level=LanguageLevel.FLUENT)]),
    )
    assert out.compatible is False
    assert any("it" in r.lower() for r in out.reasons)


def test_language_at_or_above_level_is_ok():
    profile = WorkProfile(
        pseudonym_id="P-1",
        languages=[LanguageKnown(language="IT", level=LanguageLevel.NATIVE)],
    )
    out = evaluate(
        profile,
        _job(required_languages=[RequiredLanguage(language="it", min_level=LanguageLevel.FLUENT)]),
    )
    assert out.compatible is True


def test_no_constraints_is_compatible_with_reason():
    out = evaluate(WorkProfile(pseudonym_id="P-1"), _job())
    assert out.compatible is True
    assert out.reasons  # non-empty ("all hard constraints satisfied")
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/matching/hard_constraints.py`:
```python
"""Deterministic hard-constraint gate. Runs BEFORE the LLM: incompatible
profiles are excluded WITH an explicit reason and never reach the semantic
judgment. Only enum dimensions are decided here (availability, night shifts,
language level) — never free-text skills."""

from __future__ import annotations

from bussola.matching.models import ConstraintOutcome, JobRequest, RequiredLanguage
from bussola.profile.enums import Availability, LanguageLevel, WorkConstraint
from bussola.profile.models import WorkProfile

_LEVEL_ORDER = {
    LanguageLevel.BASIC: 0,
    LanguageLevel.INTERMEDIATE: 1,
    LanguageLevel.FLUENT: 2,
    LanguageLevel.NATIVE: 3,
}


def _availability_conflict(profile: WorkProfile, job: JobRequest) -> str | None:
    if job.required_availability is None or profile.aspiration is None:
        return None
    person = profile.aspiration.availability
    if person is None or person is Availability.FLEXIBLE:
        return None
    # A full-time-available person can also take a part-time position; the only
    # confirmed conflict is a part-time-only person against a full-time job.
    if job.required_availability is Availability.FULL_TIME and person is Availability.PART_TIME:
        return "job requires full-time but person is available part-time only"
    return None


def _night_conflict(profile: WorkProfile, job: JobRequest) -> str | None:
    if not job.involves_night_shifts or profile.aspiration is None:
        return None
    if WorkConstraint.NO_NIGHT_SHIFTS in profile.aspiration.constraints:
        return "job involves night shifts but person cannot work nights"
    return None


def _part_time_only_conflict(profile: WorkProfile, job: JobRequest) -> str | None:
    if profile.aspiration is None:
        return None
    if (
        job.required_availability is Availability.FULL_TIME
        and WorkConstraint.PART_TIME_ONLY in profile.aspiration.constraints
    ):
        return "job requires full-time but person is part-time only"
    return None


def _language_conflicts(profile: WorkProfile, job: JobRequest) -> list[str]:
    reasons: list[str] = []
    for req in job.required_languages:
        if not _has_language(profile, req):
            reasons.append(f"missing language {req.language} at level {req.min_level.value}")
    return reasons


def _has_language(profile: WorkProfile, req: RequiredLanguage) -> bool:
    need = _LEVEL_ORDER[req.min_level]
    target = req.language.strip().lower()
    return any(
        lang.language.strip().lower() == target and _LEVEL_ORDER[lang.level] >= need
        for lang in profile.languages
    )


def evaluate(profile: WorkProfile, job: JobRequest) -> ConstraintOutcome:
    reasons: list[str] = []
    for reason in (
        _availability_conflict(profile, job),
        _night_conflict(profile, job),
        _part_time_only_conflict(profile, job),
    ):
        if reason is not None:
            reasons.append(reason)
    reasons.extend(_language_conflicts(profile, job))
    if reasons:
        return ConstraintOutcome(compatible=False, reasons=reasons)
    return ConstraintOutcome(compatible=True, reasons=["all hard constraints satisfied"])
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/matching/hard_constraints.py backend/tests/matching/test_hard_constraints.py
git commit -m "feat(matching): gate deterministico dei vincoli rigidi (esclude con motivo)"
```

---

### Task 5: Giudizio semantico LLM ancorato (`semantic.py`)

**Files:**
- Create: `backend/src/bussola/matching/semantic.py`
- Test: `backend/tests/matching/conftest.py` (LLM finto), `backend/tests/matching/test_semantic.py`

**Interfaces:**
- Consumes: `LlmClient.chat_json` (S3/S4), `WorkProfile`, `models.{JobRequest,RequirementVerdict}`.
- Produces: `judge_requirements(client, profile, job, language) -> list[RequirementVerdict]`. I requisiti sono `required_skills + training_prerequisites`. Constrained JSON `{"verdicts":[{"requirement":str,"satisfied":bool,"evidence":str|null}]}`; per ogni requisito ritorna il verdetto (allineato per nome; fail-safe: **non soddisfatto senza evidenza** se manca/invalid). Il prompt vincola l'LLM a citare **evidenza dal profilo** e a giudicare **solo** l'idoneità lavorativa.
- Test support in `conftest.py`: `FakeJsonLlmClient(json_responses)` con `.chat_json`.

- [ ] **Step 1: Scrivere conftest + test (falliscono)**

File `backend/tests/matching/conftest.py`:
```python
from __future__ import annotations

import pytest


class FakeJsonLlmClient:
    def __init__(self, json_responses: list[dict] | None = None) -> None:
        self._json = list(json_responses or [])
        self.calls: list[dict] = []

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None) -> dict:
        self.calls.append({"messages": messages})
        if not self._json:
            raise AssertionError("FakeJsonLlmClient: no more json responses")
        return self._json.pop(0)


@pytest.fixture
def make_fake_json_llm():
    def _make(json_responses=None) -> FakeJsonLlmClient:
        return FakeJsonLlmClient(json_responses)

    return _make
```

File `backend/tests/matching/test_semantic.py`:
```python
from bussola.matching.models import JobRequest
from bussola.matching.semantic import judge_requirements
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile


def _profile() -> WorkProfile:
    return WorkProfile(
        pseudonym_id="P-1",
        skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)],
    )


def _job() -> JobRequest:
    return JobRequest(
        id=1, created_by="op1", title="Cuoco", sector="ristorazione",
        required_skills=["cucina", "igiene alimentare"],
    )


def test_parses_grounded_verdicts(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{
        "verdicts": [
            {"requirement": "cucina", "satisfied": True, "evidence": "Cucina"},
            {"requirement": "igiene alimentare", "satisfied": False, "evidence": None},
        ]
    }])
    verdicts = judge_requirements(client, _profile(), _job(), "it")
    assert len(verdicts) == 2
    assert verdicts[0].satisfied is True and verdicts[0].evidence == "Cucina"
    assert verdicts[1].satisfied is False


def test_invalid_output_is_fail_safe_unsatisfied(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{"unexpected": "x"}])
    verdicts = judge_requirements(client, _profile(), _job(), "it")
    # one verdict per requirement, all unsatisfied, no invented evidence
    assert [v.requirement for v in verdicts] == ["cucina", "igiene alimentare"]
    assert all(v.satisfied is False and v.evidence is None for v in verdicts)


def test_no_requirements_returns_empty(make_fake_json_llm):
    job = JobRequest(id=1, created_by="op1", title="t", sector="s")
    client = make_fake_json_llm(json_responses=[{"verdicts": []}])
    assert judge_requirements(client, _profile(), job, "it") == []
```

- [ ] **Step 2: Eseguire (devono fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/matching/semantic.py`:
```python
"""LLM semantic judgment, grounded and structured. For each job requirement the
model answers satisfied/unsatisfied and MUST cite evidence from the profile (or
null). It judges ONLY work fitness against the explicit requirements — never the
person. Fail-safe: an unparseable/invalid answer yields all-unsatisfied verdicts
(no invented data)."""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from bussola.llm.client import LlmClient
from bussola.matching.models import JobRequest, RequirementVerdict
from bussola.profile.models import WorkProfile

_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "satisfied": {"type": "boolean"},
                    "evidence": {"type": ["string", "null"]},
                },
                "required": ["requirement", "satisfied", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

_PROMPT = (
    "You match a WORK profile against a job's requirements. For EACH requirement, "
    "decide if the profile satisfies it and CITE the exact profile element that is "
    "your evidence (a skill name, a role/sector, a training) — or null if not "
    "satisfied. Judge ONLY work fitness against the listed requirements; never judge "
    "the person, never infer anything beyond the profile. Do not invent evidence. "
    'Reply JSON {"verdicts":[{"requirement":string,"satisfied":bool,"evidence":string|null}]} '
    "with exactly one entry per requirement, in the given order."
)


class _Verdicts(BaseModel):
    verdicts: list[RequirementVerdict]


def _requirements(job: JobRequest) -> list[str]:
    return [*job.required_skills, *job.training_prerequisites]


def judge_requirements(
    client: LlmClient, profile: WorkProfile, job: JobRequest, language: str
) -> list[RequirementVerdict]:
    requirements = _requirements(job)
    if not requirements:
        return []
    user = (
        f"[language={language}]\n"
        f"[requirements]\n{json.dumps(requirements, ensure_ascii=False)}\n"
        f"[profile]\n{profile.model_dump_json()}"
    )
    raw = client.chat_json(
        [{"role": "system", "content": _PROMPT}, {"role": "user", "content": user}],
        json_schema=_SCHEMA,
    )
    try:
        parsed = _Verdicts.model_validate(raw)
    except ValidationError:
        return [RequirementVerdict(requirement=r, satisfied=False, evidence=None) for r in requirements]
    by_name = {v.requirement: v for v in parsed.verdicts}
    # Re-key to the requested requirements: an unmatched/missing one is unsatisfied.
    return [
        by_name.get(r, RequirementVerdict(requirement=r, satisfied=False, evidence=None))
        for r in requirements
    ]
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/matching/semantic.py backend/tests/matching/conftest.py backend/tests/matching/test_semantic.py
git commit -m "feat(matching): giudizio semantico LLM ancorato (constrained, fail-safe)"
```

---

### Task 6: Scoring + gap (`scoring.py`, `gaps.py`)

**Files:**
- Create: `backend/src/bussola/matching/scoring.py`, `backend/src/bussola/matching/gaps.py`
- Test: `backend/tests/matching/test_scoring_gaps.py`

**Interfaces:**
- Produces:
  - `scoring.score(verdicts: list[RequirementVerdict]) -> float` — frazione di requisiti soddisfatti in `[0.0, 1.0]` (trasparente: `soddisfatti / totali`; `0.0` se nessun requisito). *(Nota: il peso per grado di evidenza è un raffinamento Fase 2; in Fase 1 il punteggio è la frazione soddisfatta — vedi handoff.)*
  - `gaps.compute(verdicts, profile) -> list[GapItem]` — per ogni requisito **non** soddisfatto, `GapItem(requirement, recommended_training)`: la formazione consigliata cita il `desired_training` della persona se un topic corrisponde (match per sottostringa case-insensitive), altrimenti «formazione in <requisito>».

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/matching/test_scoring_gaps.py`:
```python
from bussola.matching.gaps import compute
from bussola.matching.models import RequirementVerdict
from bussola.matching.scoring import score
from bussola.profile.models import DesiredTraining, WorkProfile


def _v(name, sat):
    return RequirementVerdict(requirement=name, satisfied=sat, evidence=("x" if sat else None))


def test_score_is_fraction_satisfied():
    assert score([_v("a", True), _v("b", True), _v("c", False), _v("d", False)]) == 0.5
    assert score([]) == 0.0
    assert score([_v("a", True)]) == 1.0


def test_gaps_only_for_unsatisfied():
    profile = WorkProfile(pseudonym_id="P-1")
    gaps = compute([_v("cucina", True), _v("igiene alimentare", False)], profile)
    assert len(gaps) == 1
    assert gaps[0].requirement == "igiene alimentare"


def test_gap_uses_desired_training_when_matching():
    profile = WorkProfile(
        pseudonym_id="P-1",
        desired_training=[DesiredTraining(topic="corso di igiene alimentare")],
    )
    gaps = compute([_v("igiene alimentare", False)], profile)
    assert "igiene alimentare" in gaps[0].recommended_training.lower()
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/matching/scoring.py`:
```python
"""Transparent scoring: the fraction of the job's requirements the profile
satisfies. The score is nothing more than the visible verdicts summarized."""

from __future__ import annotations

from bussola.matching.models import RequirementVerdict


def score(verdicts: list[RequirementVerdict]) -> float:
    if not verdicts:
        return 0.0
    satisfied = sum(1 for v in verdicts if v.satisfied)
    return satisfied / len(verdicts)
```

File `backend/src/bussola/matching/gaps.py`:
```python
"""Formative gaps: each unmet requirement becomes a recommended-training item,
citing the person's own desired training when a topic matches (§10)."""

from __future__ import annotations

from bussola.matching.models import GapItem, RequirementVerdict
from bussola.profile.models import WorkProfile


def compute(verdicts: list[RequirementVerdict], profile: WorkProfile) -> list[GapItem]:
    gaps: list[GapItem] = []
    for verdict in verdicts:
        if verdict.satisfied:
            continue
        gaps.append(
            GapItem(
                requirement=verdict.requirement,
                recommended_training=_recommend(verdict.requirement, profile),
            )
        )
    return gaps


def _recommend(requirement: str, profile: WorkProfile) -> str:
    needle = requirement.strip().lower()
    for training in profile.desired_training:
        if needle in training.topic.strip().lower() or training.topic.strip().lower() in needle:
            return training.topic
    return f"formazione in {requirement}"
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/matching/scoring.py backend/src/bussola/matching/gaps.py backend/tests/matching/test_scoring_gaps.py
git commit -m "feat(matching): scoring trasparente (frazione soddisfatta) + gap formativi"
```

---

### Task 7: Ricerca profili (`ProfileRepository.list_all/search`)

**Files:**
- Modify: `backend/src/bussola/data/profiles.py`
- Test: `backend/tests/data/test_profiles_search.py`

**Interfaces:**
- Produces (su `ProfileRepository`, read-only, nessun commit):
  - `list_all() -> list[WorkProfile]`.
  - `search(*, availability: Availability | None = None, language: str | None = None, note: OperationalNoteCategory | None = None, skill_query: str | None = None) -> list[WorkProfile]` — filtri combinabili via JSONB (parametrizzati). `skill_query`: match case-insensitive su `skill.name`.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/data/test_profiles_search.py`:
```python
import psycopg
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import (
    Availability,
    EvidenceGrade,
    LanguageLevel,
    OperationalNoteCategory,
    SkillKind,
)
from bussola.profile.models import Aspiration, LanguageKnown, Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


@pytest.fixture
def repo(app_conn: psycopg.Connection) -> ProfileRepository:
    return ProfileRepository(app_conn, PiiRedactor())


def _seed(repo: ProfileRepository) -> None:
    repo.save(WorkProfile(
        pseudonym_id="P-cook",
        skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
        aspiration=Aspiration(availability=Availability.FULL_TIME),
        operational_notes=[OperationalNoteCategory.PREFERS_TEAM_WORK],
    ))
    repo.save(WorkProfile(
        pseudonym_id="P-clerk",
        skills=[Skill(name="Data entry", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        aspiration=Aspiration(availability=Availability.PART_TIME),
    ))


def test_list_all(repo: ProfileRepository):
    _seed(repo)
    assert {p.pseudonym_id for p in repo.list_all()} == {"P-cook", "P-clerk"}


def test_search_by_availability(repo: ProfileRepository):
    _seed(repo)
    got = repo.search(availability=Availability.FULL_TIME)
    assert [p.pseudonym_id for p in got] == ["P-cook"]


def test_search_by_skill_query_case_insensitive(repo: ProfileRepository):
    _seed(repo)
    got = repo.search(skill_query="cucina")
    assert [p.pseudonym_id for p in got] == ["P-cook"]


def test_search_by_note(repo: ProfileRepository):
    _seed(repo)
    got = repo.search(note=OperationalNoteCategory.PREFERS_TEAM_WORK)
    assert [p.pseudonym_id for p in got] == ["P-cook"]
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL (`list_all`/`search` inesistenti).

- [ ] **Step 3: Implementare** — aggiungere a `backend/src/bussola/data/profiles.py`:

In cima, aggiungere gli import (accanto agli esistenti):
```python
from bussola.profile.enums import Availability, OperationalNoteCategory
```
E i metodi in `ProfileRepository`:
```python
    def list_all(self) -> list[WorkProfile]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT profile FROM profiles.work_profile ORDER BY pseudonym_id")
            rows = cur.fetchall()
        return [WorkProfile.model_validate(r[0]) for r in rows]

    def search(
        self,
        *,
        availability: Availability | None = None,
        language: str | None = None,
        note: OperationalNoteCategory | None = None,
        skill_query: str | None = None,
    ) -> list[WorkProfile]:
        clauses: list[str] = []
        params: list[object] = []
        if availability is not None:
            clauses.append("profile->'aspiration'->>'availability' = %s")
            params.append(availability.value)
        if language is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(profile->'languages') AS l "
                "WHERE lower(l->>'language') = lower(%s))"
            )
            params.append(language)
        if note is not None:
            clauses.append("profile->'operational_notes' ? %s")
            params.append(note.value)
        if skill_query is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(profile->'skills') AS s "
                "WHERE s->>'name' ILIKE %s)"
            )
            params.append(f"%{skill_query}%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT profile FROM profiles.work_profile" + where + " ORDER BY pseudonym_id",
                params,
            )
            rows = cur.fetchall()
        return [WorkProfile.model_validate(r[0]) for r in rows]
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS. Full suite: `backend/.venv/bin/pytest backend/tests -q`.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/data/profiles.py backend/tests/data/test_profiles_search.py
git commit -m "feat(data): ProfileRepository.list_all/search (filtri JSONB, read-only)"
```

---

### Task 8: `MatchingService` (`service.py`)

**Files:**
- Create: `backend/src/bussola/matching/service.py`
- Test: `backend/tests/matching/test_service.py`

**Interfaces:**
- Consumes: `ProfileRepository` (S1/S2 + Task 7), `JobRequestRepository` (Task 3), `hard_constraints` (Task 4), `semantic` (Task 5), `scoring`/`gaps` (Task 6), `errors.JobRequestNotFound`, `PiiRedactor`, `LlmClient`.
- Produces: `MatchingService(conn, client, redactor, *, language="it", audit=None)` con `match(job_id: int, *, actor: str) -> list[MatchResult]` — carica la richiesta (`JobRequestNotFound` se assente), itera i profili (`ProfileRepository.list_all`), **gate deterministico** (esclude i non-compatibili), **giudizio semantico** sui sopravvissuti, `score`+`gaps` → `MatchResult`, ordina per `score` desc; se `audit` è fornito, registra `matching_run` (actor, `details={job_request_id, candidates}`) e committa.
- `AuditFn = Callable[..., None]`.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/matching/test_service.py`:
```python
import psycopg
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.matching.errors import JobRequestNotFound
from bussola.matching.models import JobRequestCreate, RequiredLanguage
from bussola.matching.requests import JobRequestRepository
from bussola.matching.service import MatchingService
from bussola.profile.enums import (
    Availability,
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
    WorkConstraint,
)
from bussola.profile.models import Aspiration, LanguageKnown, Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


class FakeLlm:
    """Marks a requirement satisfied iff the profile has a skill whose name
    appears in the requirement (case-insensitive) — deterministic, grounded."""

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
        import json as _json

        user = messages[-1]["content"]
        reqs = _json.loads(user.split("[requirements]\n", 1)[1].split("\n[profile]", 1)[0])
        profile = _json.loads(user.split("[profile]\n", 1)[1])
        names = [s["name"].lower() for s in profile["skills"]]
        verdicts = []
        for r in reqs:
            hit = next((n for n in names if n in r.lower() or r.lower() in n), None)
            verdicts.append({"requirement": r, "satisfied": hit is not None, "evidence": hit})
        return {"verdicts": verdicts}


def _seed_profiles(app_conn: psycopg.Connection) -> None:
    repo = ProfileRepository(app_conn, PiiRedactor())
    repo.save(WorkProfile(
        pseudonym_id="P-cook",
        skills=[Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)],
        languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
        aspiration=Aspiration(availability=Availability.FULL_TIME),
    ))
    repo.save(WorkProfile(
        pseudonym_id="P-night",  # excluded by the night-shift hard constraint
        skills=[Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)],
        aspiration=Aspiration(constraints=[WorkConstraint.NO_NIGHT_SHIFTS]),
    ))


def _job(app_conn: psycopg.Connection, **kw) -> int:
    base = dict(title="Cuoco", sector="ristorazione", required_skills=["cucina", "igiene"])
    base.update(kw)
    jr = JobRequestRepository(app_conn).create(JobRequestCreate(**base), created_by="op1")
    app_conn.commit()
    return jr.id


def test_match_ranks_and_reports_gaps(app_conn: psycopg.Connection):
    _seed_profiles(app_conn)
    job_id = _job(app_conn)
    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor())
    results = svc.match(job_id, actor="op1")
    ids = [r.pseudonym_id for r in results]
    assert "P-cook" in ids
    cook = next(r for r in results if r.pseudonym_id == "P-cook")
    assert 0.0 < cook.score <= 1.0
    assert any(g.requirement == "igiene" for g in cook.gaps)  # unmet -> gap


def test_hard_constraint_excludes_candidate(app_conn: psycopg.Connection):
    _seed_profiles(app_conn)
    job_id = _job(app_conn, involves_night_shifts=True)
    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor())
    ids = [r.pseudonym_id for r in svc.match(job_id, actor="op1")]
    assert "P-night" not in ids  # excluded by the deterministic gate


def test_missing_job_raises(app_conn: psycopg.Connection):
    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor())
    with pytest.raises(JobRequestNotFound):
        svc.match(999999, actor="op1")


def test_match_is_audited(app_conn: psycopg.Connection):
    _seed_profiles(app_conn)
    job_id = _job(app_conn)
    from bussola.data.audit import append_audit

    def audit(**kw):
        append_audit(app_conn, commit=False, **kw)

    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor(), audit=audit)
    svc.match(job_id, actor="op1")
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor = cur.fetchone()
    assert action == "matching_run" and actor == "op1"
```

> Nota: il `FakeLlm` del test è deterministico e ancorato — ricava i requisiti e le competenze dal messaggio (entrambi JSON, via `json.loads`, nessun `eval`) e segna soddisfatto un requisito solo se una competenza del profilo vi corrisponde. Riproduce così il contratto «ancorato» del giudizio semantico senza chiamare l'LLM reale.

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/matching/service.py`:
```python
"""Matching orchestration: deterministic hard-constraint gate first, then the
grounded semantic judgment on the survivors, then transparent scoring + gaps.
Computed on-demand (not persisted); each run is audited."""

from __future__ import annotations

from typing import Callable

import psycopg

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.llm.client import LlmClient
from bussola.matching import gaps as gaps_mod
from bussola.matching import hard_constraints, scoring, semantic
from bussola.matching.errors import JobRequestNotFound
from bussola.matching.models import MatchResult
from bussola.matching.requests import JobRequestRepository

AuditFn = Callable[..., None]


class MatchingService:
    def __init__(
        self,
        conn: psycopg.Connection,
        client: LlmClient,
        redactor: PiiRedactor,
        *,
        language: str = "it",
        audit: AuditFn | None = None,
    ) -> None:
        self._conn = conn
        self._client = client
        self._profiles = ProfileRepository(conn, redactor, language)
        self._jobs = JobRequestRepository(conn)
        self._language = language
        self._audit = audit

    def match(self, job_id: int, *, actor: str) -> list[MatchResult]:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobRequestNotFound(str(job_id))
        results: list[MatchResult] = []
        for profile in self._profiles.list_all():
            outcome = hard_constraints.evaluate(profile, job)
            if not outcome.compatible:
                continue  # excluded by a hard constraint (privacy-minimal: not surfaced)
            verdicts = semantic.judge_requirements(self._client, profile, job, self._language)
            results.append(
                MatchResult(
                    pseudonym_id=profile.pseudonym_id,
                    score=scoring.score(verdicts),
                    requirements=verdicts,
                    constraint=outcome,
                    gaps=gaps_mod.compute(verdicts, profile),
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        if self._audit is not None:
            self._audit(
                action="matching_run",
                actor=actor,
                details={"job_request_id": str(job_id), "candidates": str(len(results))},
            )
            self._conn.commit()
        return results
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/matching/service.py backend/tests/matching/test_service.py
git commit -m "feat(matching): MatchingService (gate -> semantico -> scoring/gap, on-demand, auditato)"
```

---

### Task 9: Router operatore (`job_requests.py`, `matching.py`, `profiles.py`) + wiring

**Files:**
- Create: `backend/src/bussola/api/routers/job_requests.py`, `matching.py`, `profiles.py`
- Modify: `backend/src/bussola/api/app.py` (include dei 3 router)
- Test: `backend/tests/api/test_job_requests_router.py`, `test_matching_router.py`, `test_profiles_router.py`

**Interfaces:**
- Consumes: `deps.{get_conn, require_permission}`, `Permission.{MANAGE_JOB_REQUESTS,RUN_MATCHING,READ_PROFILES}`, `JobRequestRepository`, `MatchingService`, `ProfileRepository`, `models`, `append_audit`, `PiiRedactor`, `HttpxLlmClient`.
- Produces:
  - `POST /job-requests` (201, `JobRequest`) + `GET /job-requests` + `GET /job-requests/{id}` — `MANAGE_JOB_REQUESTS`; `actor`/`created_by` dalla sessione; commit sul create.
  - `POST /job-requests/{id}/match` (`list[MatchResult]`) — `RUN_MATCHING`; usa `MatchingService` con `audit` che chiama `append_audit(commit=False)`; 404 su `JobRequestNotFound`.
  - `GET /profiles` (query: availability/language/note/skill_query) + `GET /profiles/{pseudonym}` — `READ_PROFILES`; audita `profile_viewed` sul dettaglio.
  - `app.py` include i 3 router.

- [ ] **Step 1: Scrivere i test (falliscono)**

File `backend/tests/api/test_job_requests_router.py`:
```python
import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, make_operator, role):
    user, temp = make_operator(f"{role.value}1", role)
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_operator_creates_and_lists_job_requests(client, make_operator):
    token = _login(client, make_operator, Role.OPERATOR)
    r = client.post(
        "/job-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Cuoco", "sector": "ristorazione", "required_skills": ["cucina"]},
    )
    assert r.status_code == 201 and r.json()["id"] > 0
    lst = client.get("/job-requests", headers={"Authorization": f"Bearer {token}"})
    assert lst.status_code == 200 and len(lst.json()) == 1


def test_non_operator_forbidden(client, make_operator):
    token = _login(client, make_operator, Role.AUDITOR)
    r = client.post(
        "/job-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "X", "sector": "Y"},
    )
    assert r.status_code == 403
```

File `backend/tests/api/test_profiles_router.py`:
```python
import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def test_operator_searches_profiles(client, make_operator, app_conn: psycopg.Connection):
    ProfileRepository(app_conn, PiiRedactor()).save(WorkProfile(
        pseudonym_id="P-1",
        skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
    ))
    user, temp = make_operator("op1", Role.OPERATOR)
    token = client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]
    r = client.get("/profiles?skill_query=cucina", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert [p["pseudonym_id"] for p in r.json()] == ["P-1"]
```

File `backend/tests/api/test_matching_router.py`:
```python
import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def test_match_endpoint_returns_results(client, make_operator, app_conn, monkeypatch):
    # stub the LLM client the router builds, so the test is deterministic
    from bussola.api.routers import matching as matching_router

    class FakeLlm:
        def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
            return {"verdicts": [{"requirement": "cucina", "satisfied": True, "evidence": "Cucina"}]}

    monkeypatch.setattr(matching_router, "HttpxLlmClient", lambda: FakeLlm())

    ProfileRepository(app_conn, PiiRedactor()).save(WorkProfile(
        pseudonym_id="P-1",
        skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
    ))
    user, temp = make_operator("op1", Role.OPERATOR)
    token = client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]
    created = client.post(
        "/job-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Cuoco", "sector": "ristorazione", "required_skills": ["cucina"]},
    ).json()
    r = client.post(
        f"/job-requests/{created['id']}/match", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()[0]["pseudonym_id"] == "P-1"
    assert r.json()[0]["requirements"][0]["satisfied"] is True
```

- [ ] **Step 2: Eseguire (devono fallire)** — FAIL (router inesistenti / 404).

- [ ] **Step 3: Implementare**

File `backend/src/bussola/api/routers/job_requests.py`:
```python
"""Job request endpoints (operator role)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, status

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.matching.models import JobRequest, JobRequestCreate
from bussola.matching.requests import JobRequestRepository

router = APIRouter(prefix="/job-requests", tags=["job-requests"])
_manage = require_permission(Permission.MANAGE_JOB_REQUESTS)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=JobRequest)
def create_job_request(
    body: JobRequestCreate,
    operator: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> JobRequest:
    jr = JobRequestRepository(conn).create(body, created_by=operator.username)
    conn.commit()
    return jr


@router.get("", response_model=list[JobRequest])
def list_job_requests(
    operator: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[JobRequest]:
    return JobRequestRepository(conn).list_all()


@router.get("/{job_id}", response_model=JobRequest)
def get_job_request(
    job_id: int,
    operator: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> JobRequest:
    jr = JobRequestRepository(conn).get(job_id)
    if jr is None:
        from fastapi import HTTPException

        raise HTTPException(status.HTTP_404_NOT_FOUND, "job request not found")
    return jr
```

File `backend/src/bussola/api/routers/matching.py`:
```python
"""Matching endpoint (operator role)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.guardrails.pii import PiiRedactor
from bussola.llm.client import HttpxLlmClient
from bussola.matching.models import MatchResult
from bussola.matching.service import MatchingService

router = APIRouter(prefix="/job-requests", tags=["matching"])
_run = require_permission(Permission.RUN_MATCHING)


@router.post("/{job_id}/match", response_model=list[MatchResult])
def run_match(
    job_id: int,
    operator: Operator = Depends(_run),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[MatchResult]:
    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]

    service = MatchingService(conn, HttpxLlmClient(), PiiRedactor(), audit=audit)
    return service.match(job_id, actor=operator.username)
```

File `backend/src/bussola/api/routers/profiles.py`:
```python
"""Profile consultation endpoints (operator role)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import Availability, OperationalNoteCategory
from bussola.profile.models import WorkProfile

router = APIRouter(prefix="/profiles", tags=["profiles"])
_read = require_permission(Permission.READ_PROFILES)


@router.get("", response_model=list[WorkProfile])
def search_profiles(
    availability: Availability | None = None,
    language: str | None = None,
    note: OperationalNoteCategory | None = None,
    skill_query: str | None = None,
    operator: Operator = Depends(_read),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[WorkProfile]:
    return ProfileRepository(conn, PiiRedactor()).search(
        availability=availability, language=language, note=note, skill_query=skill_query
    )


@router.get("/{pseudonym}", response_model=WorkProfile)
def get_profile(
    pseudonym: str,
    operator: Operator = Depends(_read),
    conn: psycopg.Connection = Depends(get_conn),
) -> WorkProfile:
    profile = ProfileRepository(conn, PiiRedactor()).get(pseudonym)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile not found")
    append_audit(
        conn, action="profile_viewed", actor=operator.username, target_pseudonym=pseudonym
    )
    return profile
```

Modificare `backend/src/bussola/api/app.py` — aggiungere gli import e le `include_router`:
```python
from bussola.api.routers import job_requests as job_requests_router
from bussola.api.routers import matching as matching_router
from bussola.api.routers import profiles as profiles_router
```
e dentro `create_app()`, dopo gli include esistenti:
```python
    app.include_router(job_requests_router.router)
    app.include_router(matching_router.router)
    app.include_router(profiles_router.router)
```

> Nota ordine router: `job_requests_router` (prefix `/job-requests`, con `POST ""`/`GET ""`/`GET /{job_id}`) e `matching_router` (prefix `/job-requests`, con `POST /{job_id}/match`) condividono il prefisso ma hanno path distinti → nessun conflitto. Includere entrambi.

- [ ] **Step 4: Eseguire (devono passare)** — PASS. Full suite: `backend/.venv/bin/pytest backend/tests -q`.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/api/routers/job_requests.py backend/src/bussola/api/routers/matching.py backend/src/bussola/api/routers/profiles.py backend/src/bussola/api/app.py backend/tests/api/test_job_requests_router.py backend/tests/api/test_matching_router.py backend/tests/api/test_profiles_router.py
git commit -m "feat(api): router operatore (job-requests, matching, profiles) RBAC + audit"
```

---

### Task 10: Integrazione end-to-end col modello reale (`test_service_live.py`)

**Files:**
- Test: `backend/tests/matching/test_service_live.py`

**Interfaces:**
- Consumes: `MatchingService`, `HttpxLlmClient`, `ProfileRepository`, `JobRequestRepository`, `PiiRedactor` (contro `bussola_test` + Qwen2.5 reale).

- [ ] **Step 1: Scrivere il test**

File `backend/tests/matching/test_service_live.py`:
```python
import httpx
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.matching.models import JobRequestCreate, RequiredLanguage
from bussola.matching.requests import JobRequestRepository
from bussola.matching.service import MatchingService
from bussola.llm.client import HttpxLlmClient
from bussola.profile.enums import (
    Availability,
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
    WorkConstraint,
)
from bussola.profile.models import Aspiration, LanguageKnown, Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def _llm_up() -> bool:
    try:
        httpx.get("http://127.0.0.1:8080/health", timeout=3)
        return True
    except Exception:
        return False


requires_llm = pytest.mark.skipif(not _llm_up(), reason="llama-server non attivo")


@requires_llm
def test_synthetic_matching_is_grounded_and_gated(app_conn):
    profiles = ProfileRepository(app_conn, PiiRedactor())
    profiles.save(WorkProfile(
        pseudonym_id="P-cook",
        skills=[Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)],
        experiences=[],
        languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
        aspiration=Aspiration(availability=Availability.FULL_TIME),
    ))
    profiles.save(WorkProfile(
        pseudonym_id="P-night",  # must be excluded by the night-shift gate
        skills=[Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)],
        aspiration=Aspiration(constraints=[WorkConstraint.NO_NIGHT_SHIFTS]),
    ))
    job = JobRequestRepository(app_conn).create(
        JobRequestCreate(
            title="Cuoco", sector="ristorazione",
            required_skills=["cucina", "sicurezza alimentare"],
            required_languages=[RequiredLanguage(language="it", min_level=LanguageLevel.INTERMEDIATE)],
            required_availability=Availability.FULL_TIME,
            involves_night_shifts=True,
        ),
        created_by="op1",
    )
    app_conn.commit()

    results = MatchingService(app_conn, HttpxLlmClient(), PiiRedactor()).match(job.id, actor="op1")
    ids = [r.pseudonym_id for r in results]
    assert "P-night" not in ids  # deterministic hard-constraint gate held
    cook = next(r for r in results if r.pseudonym_id == "P-cook")
    # "cucina" satisfied and grounded in the profile; "sicurezza alimentare" a gap
    cooking = next(v for v in cook.requirements if "cucina" in v.requirement.lower())
    assert cooking.satisfied is True and cooking.evidence  # evidence cites the profile
    assert any("sicurezza" in g.requirement.lower() for g in cook.gaps)
```

- [ ] **Step 2: Prerequisiti ed esecuzione (server + DB su)**

Run (con Postgres e llama-server attivi):
```bash
docker compose up -d db
# avviare llama-server (binario Vulkan, attendere /health)
backend/.venv/bin/pytest backend/tests/matching/test_service_live.py -v
```
Expected: PASS — il candidato incompatibile è escluso dal gate; il match ha spiegazione **ancorata** (evidenza dal profilo) e un gap formativo. Se un passo non regge, investigare il prompt semantico (non indebolire le asserzioni).

- [ ] **Step 3: Gate completo + commit**
```bash
backend/.venv/bin/pytest backend/tests -q
backend/.venv/bin/ruff check backend/ && backend/.venv/bin/ruff format --check backend/src/bussola/matching backend/src/bussola/api backend/tests/matching backend/tests/api
backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/src
git add backend/tests/matching/test_service_live.py
git commit -m "test(matching): integrazione end-to-end con Qwen2.5 reale (gate + ancoraggio)"
```

---

## Note di chiusura (scelte di ambito)

- **Metriche minime** e **export-con-approvazione** (§7.2/§7.3): follow-on dedicato.
- **Persistenza degli esiti di matching**: Fase 2 (ora on-demand).
- **Peso per grado di evidenza** nello scoring: raffinamento Fase 2 (ora frazione soddisfatta — trasparente).
- **Frontend/kiosk**: S7.

## Verifica di copertura (spec → task)

| Requisito (spec/§) | Task |
|---|---|
| Modello `JobRequest` whitelist (§3, §5) | 1 |
| Schema DB `matching` + privilegi (§5) | 2 |
| CRUD richieste di lavoro (§7.2) | 3, 9 |
| Gate deterministico dei vincoli rigidi (§3.2) | 4 |
| Giudizio semantico LLM ancorato (§3.1/§3.3/§3.4) | 5 |
| Scoring trasparente + gap formativi (§3.6/§10) | 6 |
| Consultazione/ricerca profili (§7.2) | 7, 9 |
| Orchestrazione matching on-demand + audit (§3.5/§7.3) | 8 |
| Endpoint operatore RBAC + audit (§6/§7) | 9 |
| Integrazione col modello reale (§9) | 10 |
| TDD, dati sintetici, codice inglese (§9/§11) | Tutti |
