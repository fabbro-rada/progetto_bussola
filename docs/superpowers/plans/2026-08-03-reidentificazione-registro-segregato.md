# Re-identification (segregated identity register) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an operator link a pseudonymous work profile back to the real person — operator-initiated provisioning (enters a `matricola`, never sees the pseudonym) + supervisor-only, fully-audited de-anonymization — via a segregated `pseudonimo↔matricola` register and a code-launched kiosk start.

**Architecture:** A new segregated schema `identity` holds ONLY `pseudonym_id↔matricola`. Provisioning (operator) creates an empty profile + the identity link + a one-time `start_code` (mechanism mirrors the follow-up token), returning only the code. The kiosk starts a first interview by consuming a `start_code` (no more anonymous self-start). Only the supervisor holds the `DEANONYMIZE` permission to resolve pseudonym↔matricola, each resolution audited.

**Tech Stack:** Python 3.12 · FastAPI · psycopg3 · PostgreSQL 16 (segregated schemas + role grants) · React 18/TS (kiosk + operator portal) · pytest / vitest.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-08-03-reidentificazione-registro-segregato-design.md` (source of truth).
- **Nucleus (§0):** the CLAUDE.md edits in Task 1 are pre-approved; apply them exactly as written.
- The identity register contains **only** `pseudonym_id`, `matricola`, `created_at`, `created_by` — never name/anagraphic/crimes/health.
- The provisioning response **never** contains the pseudonym.
- De-anonymization is **supervisor-only** (`Permission.DEANONYMIZE`); every link creation and every resolution is an **audit** event (`append_audit`, hash-chained, `commit=False` + single commit by the caller).
- Codes/tokens: `secrets.token_urlsafe(32)`; store only `hash_token(code)` (sha256, from `bussola.auth.sessions`); single-use + expiring (atomic `UPDATE ... WHERE used_at IS NULL AND expires_at > now RETURNING`).
- Migrations run as `bussola_owner`; app runs as `bussola_app`; new schemas `AUTHORIZATION bussola_owner` + explicit `GRANT` to `bussola_app` (auditor gets NO grant on `identity`/`startcode`).
- TDD, security tests first (§9). Backend gate: `pytest -q`, `ruff check .`, `mypy src`. Kiosk/portal gate: `npm test -- --run`, `npm run typecheck`, `npm run lint`, `npm run build`. Some backend tests need `docker compose up -d db`.
- Matricola is **UNIQUE** (one profile per person; updates go through follow-up). Existing anonymous profiles stay unlinkable (out of scope).

---

### Task 1: Nucleus edits (CLAUDE.md) + STATO_TECNICO decision row

**Files:**
- Modify: `CLAUDE.md` (§2, §5, §6, §7.3)
- Modify: `STATO_TECNICO.md` (decision-log table, add one row)
- Modify: `backend/src/bussola/data/pseudonym.py:2-5` (docstring)

**Interfaces:** none (documentation). No automated test — the task reviewer verifies the wording matches the spec §3 verbatim.

- [ ] **Step 1: Edit CLAUDE.md §5** — after the bullet list item «un identificativo interno **pseudonimizzato**, separato dai dati anagrafici;» add a new paragraph after the "Cosa il profilo NON deve mai contenere" block:

```markdown
**Registro d'identità segregato.** Il legame tra lo pseudonimo e la persona vive in un **registro separato** dal profilo lavorativo, che contiene **solo** lo pseudonimo e la **matricola** (il riferimento che la struttura già gestisce) — mai nome, anagrafica, reati, salute. Il registro è accessibile **soltanto al supervisore** per la de-anonimizzazione (§6) e **ogni accesso è tracciato** nel log di audit (§7.3). Il profilo lavorativo resta minimo e pseudonimo: chi lo consulta (operatore) **non** vede l'identità.
```

- [ ] **Step 2: Edit CLAUDE.md §6** — in the **Operatore** bullet, replace «Non recupera informazioni personali: nel profilo, per costruzione, non ce ne sono.» with:

```markdown
Non risolve l'identità: **avvia** i colloqui inserendo la **matricola** (crea il legame pseudonimo↔persona) ma **non può leggerlo** — scrive, non risolve. Lavora solo su pseudonimi; nel profilo, per costruzione, non ci sono dati personali.
```

  In the **Supervisore** bullet, after «Non è un validatore dei singoli dati.» add:

```markdown
È l'**unica** autorità di **de-anonimizzazione**: l'unico ruolo che può risolvere pseudonimo↔matricola, per consegnare gli esiti del matching e indirizzare i follow-up. Ogni risoluzione è tracciata (§7.3).
```

- [ ] **Step 3: Edit CLAUDE.md §2** — append to the bullet «I dati non possono essere riusati…»:

```markdown
Il registro d'identità (pseudonimo↔matricola) è utilizzabile **solo** per orientamento, matching e follow-up, **mai** per sorveglianza, disciplina o valutazione; contiene **solo la matricola** e ogni accesso è tracciato e revisionabile dall'auditor.
```

- [ ] **Step 4: Edit CLAUDE.md §7.3** — after the «Registro di audit immutabile» bullet add:

```markdown
- **Tracciamento della re-identificazione.** La creazione del legame pseudonimo↔matricola (all'avvio del colloquio) e ogni de-anonimizzazione sono eventi del log immutabile. *Perché:* la re-identificazione è potente e va resa sempre verificabile.
```

- [ ] **Step 5: Update `pseudonym.py:2-5` docstring** — replace the sentence «The system never stores the link between a pseudonym and a real person — that register lives outside the system.» with:

```
The pseudonym is the ONLY identifier inside the work profile. The link between a
pseudonym and a real person (matricola) lives in a SEPARATE, segregated register
(schema `identity`), readable only by the supervisor role and fully audited (§5/§6/§7.3).
```

- [ ] **Step 6: Add a STATO_TECNICO decision row** at the top of the §15 «segue» table (before the `Sott. 27` row), dated `2026-08-03`, summarizing: «Sott. 50 — Re-identificazione con registro segregato: modello approvato (§0). Registro `identity` (pseudonimo↔matricola), provisioning operatore (start_code, mai lo pseudonimo), de-anonimizzazione solo supervisore + audit. Modifiche al nucleo §5/§6/§2/§7.3. Vedi spec 2026-08-03.»

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md STATO_TECNICO.md backend/src/bussola/data/pseudonym.py
git commit -m "docs(nucleo): registro d'identità segregato — modifiche §2/§5/§6/§7.3 (approvate)"
```

---

### Task 2: Migration 0009 — `identity` + `startcode` schemas

**Files:**
- Create: `backend/src/bussola/data/migrations/0009_identity_and_startcode.sql`
- Test: `backend/tests/data/test_migration_identity.py`

**Interfaces:**
- Produces: table `identity.pseudonym_identity(pseudonym_id text PK → profiles.work_profile, matricola text NOT NULL UNIQUE, created_at, created_by text NOT NULL)`; table `startcode.start_code(code_hash text PK, pseudonym_id text NOT NULL, created_at, expires_at, used_at)`. Both `GRANT`ed to `bussola_app`; auditor gets NO grant.

- [ ] **Step 1: Write the failing test** (DB-backed; mirror an existing `backend/tests/data/` test's owner-connection fixture — connect with `config.dsn("owner")`, run `apply_migrations`, then assert):

```python
import psycopg
from bussola.data import config
from bussola.data.migrate import apply_migrations

def test_identity_and_startcode_tables_exist_and_are_segregated():
    with psycopg.connect(config.dsn("owner")) as conn:
        apply_migrations(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='identity' AND table_name='pseudonym_identity' ORDER BY 1"
            )
            cols = [r[0] for r in cur.fetchall()]
            assert cols == ["created_at", "created_by", "matricola", "pseudonym_id"]
            # matricola is UNIQUE (one profile per person)
            cur.execute(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE table_schema='identity' AND table_name='pseudonym_identity' "
                "AND constraint_type='UNIQUE'"
            )
            assert cur.fetchone() is not None
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='startcode' AND table_name='start_code' ORDER BY 1"
            )
            assert [r[0] for r in cur.fetchall()] == [
                "code_hash", "created_at", "expires_at", "pseudonym_id", "used_at",
            ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && docker compose -f ../docker-compose.yml up -d db && python -m pytest tests/data/test_migration_identity.py -v`
Expected: FAIL (schemas/tables do not exist).

- [ ] **Step 3: Write the migration** `0009_identity_and_startcode.sql`:

```sql
-- Segregated identity register + one-time interview start codes (§5). Run as bussola_owner.
-- identity.pseudonym_identity: the ONLY link between a pseudonym and a real person
-- (matricola). No name/anagraphic. Readable only via the supervisor-gated app path;
-- the auditor gets NO grant on this schema (absence of grant = no access).
CREATE SCHEMA IF NOT EXISTS identity AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA identity TO bussola_app;

CREATE TABLE identity.pseudonym_identity (
    pseudonym_id text PRIMARY KEY REFERENCES profiles.work_profile(pseudonym_id),
    matricola    text NOT NULL UNIQUE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    created_by   text NOT NULL
);
CREATE INDEX ON identity.pseudonym_identity (matricola);
GRANT SELECT, INSERT ON identity.pseudonym_identity TO bussola_app;

-- startcode.start_code: one-time, expiring code that launches a FIRST interview on a
-- pre-created (empty) pseudonym. Stores ONLY the code hash + pseudonym + timestamps.
CREATE SCHEMA IF NOT EXISTS startcode AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA startcode TO bussola_app;

CREATE TABLE startcode.start_code (
    code_hash    text PRIMARY KEY,
    pseudonym_id text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    used_at      timestamptz
);
GRANT SELECT, INSERT, UPDATE ON startcode.start_code TO bussola_app;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/data/test_migration_identity.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/bussola/data/migrations/0009_identity_and_startcode.sql backend/tests/data/test_migration_identity.py
git commit -m "feat(data): migration 0009 — segregated identity + start-code schemas"
```

---

### Task 3: Identity register service + empty-profile helper

**Files:**
- Create: `backend/src/bussola/identity/__init__.py` (empty), `backend/src/bussola/identity/service.py`, `backend/src/bussola/identity/errors.py`
- Modify: `backend/src/bussola/data/profiles.py` (add `create_empty_profile(conn)`)
- Test: `backend/tests/identity/test_identity_service.py`

**Interfaces:**
- Consumes: `append_audit` (`bussola.data.audit`), migration 0009 tables.
- Produces:
  - `create_empty_profile(conn: psycopg.Connection) -> str` (generates a pseudonym, inserts an empty `profiles.work_profile` row, returns the pseudonym; no redactor needed).
  - `class MatricolaAlreadyLinked(Exception)`.
  - `class IdentityService:` `__init__(conn, *, audit: Callable[..., None] | None = None)`; `link(pseudonym_id: str, matricola: str, *, actor: str) -> None` (raises `MatricolaAlreadyLinked`); `resolve(pseudonym_id: str, *, actor: str) -> str | None`; `resolve_matricola(matricola: str, *, actor: str) -> str | None`. No internal commit (caller owns the transaction). Audits `identity_link_created` on `link`, `identity_resolved` on each successful resolve.

- [ ] **Step 1: Write the failing tests** (DB-backed; mirror the owner/app conn fixture used by other `backend/tests/` DB tests):

```python
import psycopg, pytest
from bussola.data import config
from bussola.data.profiles import create_empty_profile
from bussola.identity.service import IdentityService
from bussola.identity.errors import MatricolaAlreadyLinked

def _conn():
    return psycopg.connect(config.dsn("app"))

def test_link_then_resolve_both_directions_and_audit():
    audited = []
    with _conn() as conn:
        p = create_empty_profile(conn); conn.commit()
        svc = IdentityService(conn, audit=lambda **kw: audited.append(kw))
        svc.link(p, "MAT-001", actor="op1"); conn.commit()
        assert svc.resolve(p, actor="sup1") == "MAT-001"
        assert svc.resolve_matricola("MAT-001", actor="sup1") == p
    actions = [a["action"] for a in audited]
    assert actions.count("identity_link_created") == 1
    assert actions.count("identity_resolved") == 2

def test_duplicate_matricola_is_rejected():
    with _conn() as conn:
        p1 = create_empty_profile(conn); p2 = create_empty_profile(conn); conn.commit()
        svc = IdentityService(conn)
        svc.link(p1, "MAT-DUP", actor="op1"); conn.commit()
        with pytest.raises(MatricolaAlreadyLinked):
            svc.link(p2, "MAT-DUP", actor="op1")

def test_resolve_unknown_returns_none():
    with _conn() as conn:
        svc = IdentityService(conn)
        assert svc.resolve("P-nope", actor="sup1") is None
        assert svc.resolve_matricola("MAT-nope", actor="sup1") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/identity/test_identity_service.py -v`
Expected: FAIL (import errors — modules not defined).

- [ ] **Step 3: Implement** `data/profiles.py` helper (add near `generate_pseudonym` import; reuse the model + upsert SQL, redactor-free):

```python
def create_empty_profile(conn: psycopg.Connection) -> str:
    """Create an empty work profile under a fresh pseudonym; return the pseudonym.
    Redactor-free (the operator provisioning path must not load NLP models)."""
    pseudonym = generate_pseudonym()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles.work_profile (pseudonym_id, profile) VALUES (%s, %s) "
            "ON CONFLICT (pseudonym_id) DO NOTHING",
            (pseudonym, WorkProfile(pseudonym_id=pseudonym).model_dump_json()),
        )
    return pseudonym
```

  `identity/errors.py`:

```python
class MatricolaAlreadyLinked(Exception):
    """A profile already exists for this matricola (use follow-up to update it)."""
```

  `identity/service.py`:

```python
from collections.abc import Callable
import psycopg
from psycopg.errors import UniqueViolation
from bussola.identity.errors import MatricolaAlreadyLinked

AuditFn = Callable[..., None]

class IdentityService:
    def __init__(self, conn: psycopg.Connection, *, audit: AuditFn | None = None) -> None:
        self._conn = conn
        self._audit = audit

    def link(self, pseudonym_id: str, matricola: str, *, actor: str) -> None:
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO identity.pseudonym_identity "
                    "(pseudonym_id, matricola, created_by) VALUES (%s, %s, %s)",
                    (pseudonym_id, matricola, actor),
                )
        except UniqueViolation as exc:
            raise MatricolaAlreadyLinked(matricola) from exc
        if self._audit is not None:
            self._audit(action="identity_link_created", actor=actor, target_pseudonym=pseudonym_id)

    def resolve(self, pseudonym_id: str, *, actor: str) -> str | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT matricola FROM identity.pseudonym_identity WHERE pseudonym_id = %s",
                (pseudonym_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        if self._audit is not None:
            self._audit(action="identity_resolved", actor=actor, target_pseudonym=pseudonym_id)
        return str(row[0])

    def resolve_matricola(self, matricola: str, *, actor: str) -> str | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT pseudonym_id FROM identity.pseudonym_identity WHERE matricola = %s",
                (matricola,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        pseudonym = str(row[0])
        if self._audit is not None:
            self._audit(action="identity_resolved", actor=actor, target_pseudonym=pseudonym)
        return pseudonym
```

> Note: `UniqueViolation` aborts the transaction; the caller must not commit after catching `MatricolaAlreadyLinked` (the provision endpoint returns 409 and does not commit).

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/identity/test_identity_service.py -v` → PASS. Then `ruff check . && mypy src`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/bussola/identity/ backend/src/bussola/data/profiles.py backend/tests/identity/
git commit -m "feat(identity): segregated pseudonym↔matricola register service"
```

---

### Task 4: Start-code service

**Files:**
- Create: `backend/src/bussola/startcode/__init__.py` (empty), `backend/src/bussola/startcode/service.py`
- Test: `backend/tests/startcode/test_start_code_service.py`

**Interfaces:**
- Consumes: `hash_token` (`bussola.auth.sessions`), migration 0009 `startcode.start_code`.
- Produces: `class StartCodeService:` `__init__(conn, *, ttl_seconds: int = 86400)`; `issue(pseudonym_id: str) -> str` (returns cleartext code once); `consume(code: str) -> str | None` (atomic single-use; returns pseudonym or None). No commit inside (caller owns the transaction). Directly mirrors `bussola.followup.service.FollowupTokenService` (issue/consume), minus the audit (the provision endpoint audits the identity link).

- [ ] **Step 1: Write the failing tests** (mirror `backend/tests/followup/` token tests):

```python
import psycopg
from datetime import datetime, timedelta, timezone
from bussola.data import config
from bussola.auth.sessions import hash_token
from bussola.startcode.service import StartCodeService

def _conn(): return psycopg.connect(config.dsn("app"))

def test_issue_then_consume_returns_pseudonym_once():
    with _conn() as conn:
        code = StartCodeService(conn).issue("P-abc"); conn.commit()
        assert StartCodeService(conn).consume(code) == "P-abc"; conn.commit()
        assert StartCodeService(conn).consume(code) is None  # single-use

def test_expired_code_is_rejected():
    with _conn() as conn:
        code = StartCodeService(conn, ttl_seconds=-1).issue("P-exp"); conn.commit()
        assert StartCodeService(conn).consume(code) is None

def test_stores_only_the_hash():
    with _conn() as conn:
        code = StartCodeService(conn).issue("P-h"); conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT code_hash FROM startcode.start_code WHERE pseudonym_id='P-h'")
            assert cur.fetchone()[0] == hash_token(code)
```

- [ ] **Step 2: Run to verify it fails** — Run: `cd backend && python -m pytest tests/startcode/test_start_code_service.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement** `startcode/service.py` (mirror `FollowupTokenService`):

```python
import secrets
from datetime import datetime, timedelta, timezone
import psycopg
from bussola.auth.sessions import hash_token

class StartCodeService:
    def __init__(self, conn: psycopg.Connection, *, ttl_seconds: int = 86400) -> None:
        self._conn = conn
        self._ttl_seconds = ttl_seconds

    def issue(self, pseudonym_id: str) -> str:
        code = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO startcode.start_code (code_hash, pseudonym_id, created_at, expires_at) "
                "VALUES (%s, %s, %s, %s)",
                (hash_token(code), pseudonym_id, now, now + timedelta(seconds=self._ttl_seconds)),
            )
        return code

    def consume(self, code: str) -> str | None:
        now = datetime.now(timezone.utc)
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE startcode.start_code SET used_at = %s "
                "WHERE code_hash = %s AND used_at IS NULL AND expires_at > %s "
                "RETURNING pseudonym_id",
                (now, hash_token(code), now),
            )
            row = cur.fetchone()
            if cur.rowcount != 1 or row is None:
                return None
            return str(row[0])
```

- [ ] **Step 4: Run to verify it passes** — `python -m pytest tests/startcode/ -v` → PASS; `ruff check . && mypy src`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/bussola/startcode/ backend/tests/startcode/
git commit -m "feat(startcode): one-time expiring interview start-code service"
```

---

### Task 5: `Interview.start_on` + kiosk start-from-code

**Files:**
- Modify: `backend/src/bussola/interview/interview.py` (add `start_on`)
- Modify: `backend/src/bussola/api/kiosk/deps.py` (rename `build_followup_interview` → `build_kiosk_interview`; keep it generic)
- Modify: `backend/src/bussola/api/kiosk/routers/interview.py` (change `start` to consume a `start_code`)
- Test: `backend/tests/interview/test_interview.py` (add `start_on`), `backend/tests/api/kiosk/test_interview_endpoints.py` (update `start`)

**Interfaces:**
- Consumes: `StartCodeService.consume`, `build_kiosk_interview(conn, language)`.
- Produces: `Interview.start_on(pseudonym_id: str) -> Step` (first interview on a PRE-created pseudonym; full sections, overwrite merge; does NOT call `create_new`). Kiosk `POST /kiosk/interview/start` body becomes `{start_code: str, language: str}`.

- [ ] **Step 1: Write the failing tests.** In `test_interview.py`:

```python
def test_start_on_uses_the_given_pseudonym_without_creating_a_new_one(make_fake_json_llm):
    repo = FakeRepo()
    itw = Interview(make_fake_json_llm(), ScopeGuard(make_fake_json_llm()), repo, language="it")
    step = itw.start_on("P-fixed")
    assert step.kind == "question"
    assert repo.saved == []           # nothing saved yet
    # first confirmed section must persist under P-fixed (not a create_new pseudonym)
```

  In `test_interview_endpoints.py` (kiosk): a start now requires a valid `start_code`; mirror the existing `start-followup` endpoint test (provision a code via `StartCodeService` against the test DB, POST it, expect a `question` step; invalid code → 401). Update/replace the old anonymous-`start` test.

- [ ] **Step 2: Run to verify it fails** — `python -m pytest tests/interview/test_interview.py -k start_on -v` → FAIL (`start_on` missing).

- [ ] **Step 3: Implement `Interview.start_on`** (mirror `start()` but skip `create_new`):

```python
def start_on(self, pseudonym_id: str) -> Step:
    """Start a FIRST interview on a pre-created (empty) pseudonym (operator-
    provisioned). Full sections, overwrite merge — like start(), but the
    pseudonym/profile already exist, so we do not create a new one."""
    self._session = InterviewSession(pseudonym_id, self._language)
    self._awaiting_confirmation = False
    self._awaiting_final_clarification = False
    self._section_answer = ""
    self._final_clarification = None
    self._last_summary = ""
    return self._question_step()
```

- [ ] **Step 4: Rename deps builder + rewire the kiosk `start` route.** In `kiosk/deps.py` rename `build_followup_interview` → `build_kiosk_interview` (same body) and update its one existing caller (`start-followup`). In `kiosk/routers/interview.py` change `StartRequest` to `{start_code: str; language: str = Field(default="it", min_length=2, max_length=5)}` and rewrite `start` mirroring `start_followup`:

```python
@router.post("/start", response_model=StartResponse)
def start(body: StartRequest) -> StartResponse:
    conn = open_kiosk_conn()
    pseudonym = StartCodeService(conn).consume(body.start_code)
    if pseudonym is None:
        conn.close()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired start code")
    conn.commit()  # LOAD-BEARING: persist single-use consume before anything can raise
    interview = build_kiosk_interview(conn, body.language)
    try:
        step = interview.start_on(pseudonym)
    except Exception:
        conn.close()
        raise
    token = REGISTRY.create(interview, on_evict=conn.close)
    return StartResponse(session_token=token, step=StepOut(kind=step.kind, text=step.text))
```

  (Import `StartCodeService`; the old `build_interview(language)` self-conn/create_new path is no longer used by `start` — remove it if unused elsewhere.)

- [ ] **Step 5: Run tests** — `python -m pytest tests/interview tests/api/kiosk -v` (DB up) → PASS; `ruff check . && mypy src`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/bussola/interview/interview.py backend/src/bussola/api/kiosk/ backend/tests/interview/test_interview.py backend/tests/api/kiosk/test_interview_endpoints.py
git commit -m "feat(kiosk): start a first interview by consuming a one-time start code"
```

---

### Task 6: Operator provision endpoint (`POST /interviews/provision`)

**Files:**
- Create: `backend/src/bussola/api/routers/interviews.py`
- Modify: `backend/src/bussola/auth/rbac.py` (add `Permission.PROVISION_INTERVIEW` to enum + OPERATOR set)
- Modify: `backend/src/bussola/api/app.py` (register the router)
- Test: `backend/tests/api/test_interviews_provision.py`

**Interfaces:**
- Consumes: `create_empty_profile`, `IdentityService.link`, `StartCodeService.issue`, `require_permission`, `append_audit`.
- Produces: `POST /interviews/provision` (permission `PROVISION_INTERVIEW`) body `{matricola: str}` → `201 {start_code: str}` (NEVER the pseudonym); duplicate matricola → `409`.

- [ ] **Step 1: Write the failing tests** (mirror `tests/api/.../test` auth harness that logs in an operator; assert):

```python
def test_provision_returns_start_code_and_never_the_pseudonym(operator_client, db):
    r = operator_client.post("/interviews/provision", json={"matricola": "MAT-100"})
    assert r.status_code == 201
    body = r.json()
    assert body["start_code"] and "start_code" in body
    assert "pseudonym" not in str(body).lower()  # no pseudonym leaked

def test_duplicate_matricola_returns_409(operator_client):
    operator_client.post("/interviews/provision", json={"matricola": "MAT-DUP"})
    r = operator_client.post("/interviews/provision", json={"matricola": "MAT-DUP"})
    assert r.status_code == 409

def test_provision_requires_permission(auditor_client):
    r = auditor_client.post("/interviews/provision", json={"matricola": "MAT-X"})
    assert r.status_code == 403

def test_provision_audits_identity_link_created(operator_client, auditor_conn):
    operator_client.post("/interviews/provision", json={"matricola": "MAT-AUD"})
    # assert an 'identity_link_created' row exists in audit.audit_log
```

- [ ] **Step 2: Run to verify it fails** — endpoint missing → 404/failures.

- [ ] **Step 3: Add the permission.** In `rbac.py`: add `PROVISION_INTERVIEW = "provision_interview"` to `Permission`, and add it to `Role.OPERATOR`'s frozenset.

- [ ] **Step 4: Implement the router** `api/routers/interviews.py` (mirror `followups.py` atomic-audit idiom):

```python
import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.data.profiles import create_empty_profile
from bussola.identity.service import IdentityService
from bussola.identity.errors import MatricolaAlreadyLinked
from bussola.startcode.service import StartCodeService

router = APIRouter(prefix="/interviews", tags=["interviews"])
_provision = require_permission(Permission.PROVISION_INTERVIEW)

class ProvisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matricola: str

class ProvisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_code: str

@router.post("/provision", status_code=status.HTTP_201_CREATED, response_model=ProvisionResponse)
def provision_interview(
    body: ProvisionBody,
    operator: Operator = Depends(_provision),
    conn: psycopg.Connection = Depends(get_conn),
) -> ProvisionResponse:
    pseudonym = create_empty_profile(conn)
    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]
    try:
        IdentityService(conn, audit=audit).link(pseudonym, body.matricola, actor=operator.username)
    except MatricolaAlreadyLinked:
        conn.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "a profile already exists for this matricola")
    code = StartCodeService(conn).issue(pseudonym)
    conn.commit()
    return ProvisionResponse(start_code=code)  # pseudonym intentionally NOT returned
```

  Register in `app.py`: `from bussola.api.routers import interviews` + `app.include_router(interviews.router)`.

- [ ] **Step 5: Run tests** → PASS; `ruff check . && mypy src`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/bussola/api/routers/interviews.py backend/src/bussola/auth/rbac.py backend/src/bussola/api/app.py backend/tests/api/test_interviews_provision.py
git commit -m "feat(api): operator provisions an interview (matricola → start_code, no pseudonym)"
```

---

### Task 7: `DEANONYMIZE` permission + supervisor resolve endpoints

**Files:**
- Modify: `backend/src/bussola/auth/rbac.py` (add `Permission.DEANONYMIZE` → SUPERVISOR)
- Create: `backend/src/bussola/api/routers/identity.py`
- Modify: `backend/src/bussola/api/app.py` (register)
- Test: `backend/tests/api/test_identity_resolve.py`

**Interfaces:**
- Produces: `POST /identity/resolve` (perm `DEANONYMIZE`) `{pseudonym_ids: list[str]}` → `{results: [{pseudonym_id, matricola}]}` (unknown pseudonyms omitted); `POST /identity/resolve-matricola` `{matricola}` → `{pseudonym_id}` or `404`. Each successful resolution audits `identity_resolved`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_supervisor_resolves_pseudonym_to_matricola(supervisor_client, provisioned):
    r = supervisor_client.post("/identity/resolve", json={"pseudonym_ids": [provisioned.pseudonym]})
    assert r.status_code == 200
    assert r.json()["results"] == [{"pseudonym_id": provisioned.pseudonym, "matricola": provisioned.matricola}]

def test_operator_cannot_resolve(operator_client):
    assert operator_client.post("/identity/resolve", json={"pseudonym_ids": ["P-x"]}).status_code == 403

def test_auditor_and_admin_cannot_resolve(auditor_client, admin_client):
    assert auditor_client.post("/identity/resolve", json={"pseudonym_ids": ["P-x"]}).status_code == 403
    assert admin_client.post("/identity/resolve", json={"pseudonym_ids": ["P-x"]}).status_code == 403

def test_resolve_matricola_reverse_and_404(supervisor_client, provisioned):
    assert supervisor_client.post("/identity/resolve-matricola", json={"matricola": provisioned.matricola}).json()["pseudonym_id"] == provisioned.pseudonym
    assert supervisor_client.post("/identity/resolve-matricola", json={"matricola": "MAT-nope"}).status_code == 404

def test_resolution_is_audited(supervisor_client, provisioned, auditor_conn):
    supervisor_client.post("/identity/resolve", json={"pseudonym_ids": [provisioned.pseudonym]})
    # assert an 'identity_resolved' row for that pseudonym exists in audit.audit_log
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Add permission.** `rbac.py`: `DEANONYMIZE = "deanonymize"` in `Permission`; add to `Role.SUPERVISOR`'s frozenset.

- [ ] **Step 4: Implement `api/routers/identity.py`:**

```python
import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.identity.service import IdentityService

router = APIRouter(prefix="/identity", tags=["identity"])
_resolve = require_permission(Permission.DEANONYMIZE)

class ResolveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pseudonym_ids: list[str]

class ResolveItem(BaseModel):
    pseudonym_id: str
    matricola: str

class ResolveResponse(BaseModel):
    results: list[ResolveItem]

class ResolveMatricolaBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matricola: str

class ResolveMatricolaResponse(BaseModel):
    pseudonym_id: str

@router.post("/resolve", response_model=ResolveResponse)
def resolve(body: ResolveBody, operator: Operator = Depends(_resolve),
            conn: psycopg.Connection = Depends(get_conn)) -> ResolveResponse:
    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]
    svc = IdentityService(conn, audit=audit)
    items = []
    for pid in body.pseudonym_ids:
        m = svc.resolve(pid, actor=operator.username)
        if m is not None:
            items.append(ResolveItem(pseudonym_id=pid, matricola=m))
    conn.commit()
    return ResolveResponse(results=items)

@router.post("/resolve-matricola", response_model=ResolveMatricolaResponse)
def resolve_matricola(body: ResolveMatricolaBody, operator: Operator = Depends(_resolve),
                      conn: psycopg.Connection = Depends(get_conn)) -> ResolveMatricolaResponse:
    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]
    pid = IdentityService(conn, audit=audit).resolve_matricola(body.matricola, actor=operator.username)
    if pid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no profile for this matricola")
    conn.commit()
    return ResolveMatricolaResponse(pseudonym_id=pid)
```

  Register in `app.py`.

- [ ] **Step 5: Run tests** → PASS; `ruff check . && mypy src`; then full `pytest -q`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/bussola/api/routers/identity.py backend/src/bussola/auth/rbac.py backend/src/bussola/api/app.py backend/tests/api/test_identity_resolve.py
git commit -m "feat(api): supervisor-only, audited de-anonymization (resolve both directions)"
```

---

### Task 8: Kiosk frontend — start-code entry

**Files:**
- Modify: `frontend/src/api/kioskClient.ts` (+ `frontend/src/types.ts`): `startInterview` now takes a `startCode` + `language`
- Modify: `frontend/src/state/kioskMachine.ts`, `frontend/src/App.tsx`, `frontend/src/screens/LanguagePicker.tsx` flow
- Create: `frontend/src/screens/StartCodeEntry.tsx` (mirror `FollowupEntry.tsx`) + i18n keys (5 languages) + test
- Modify: `frontend/src/test/fakeClient.ts`
- Test: `frontend/src/screens/StartCodeEntry.test.tsx`, `frontend/src/App.test.tsx`

**Interfaces:**
- `KioskClient.startInterview(startCode: string, language: string): Promise<StartResult>` → `POST /kiosk/interview/start {start_code, language}` (mirror `startFollowup`).

- [ ] **Step 1: Write the failing tests.** `StartCodeEntry.test.tsx` (mirror `FollowupEntry.test.tsx`): pick a language, type a code, submit → `onSubmit(code, language)` fires. In `App.test.tsx`: the happy path now begins with the person entering a start code (provided in the test) before the first question; update the existing "happy path" harness to route through the code entry.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement.**
  - `kioskClient.startInterview(startCode, language)` mirrors `startFollowup` but posts to `/kiosk/interview/start` with `{ start_code: startCode, language }`; update the `KioskClient` interface in `types.ts`.
  - `StartCodeEntry.tsx`: copy `FollowupEntry.tsx`, rename props to `onSubmit(code, language)`, use i18n keys `startCode.title/codeLabel/codePlaceholder/submit` (add to all 5 locale files `frontend/src/i18n/locales/{it,en,fr,es,ar}.ts`).
  - `kioskMachine.ts`: add a `startCode` field + actions mirroring the follow-up ones (`submitStartCode`, `startingFirst`); after the code+language are captured, the consent screen's accept calls `startInterview(startCode, language)`.
  - `App.tsx`: the entry flow becomes LanguagePicker → StartCodeEntry → Consent → start. Wire callbacks mirroring `submitFollowupCredentials`/`startFollowup`.
  - `fakeClient.ts`: update `startInterview` signature.

- [ ] **Step 4: Run tests** → PASS; `npm run typecheck && npm run lint && npm run build`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(kiosk): enter a start code to begin the interview"
```

---

### Task 9: Portal — operator "new interview" (provision) screen

**Files:**
- Modify: `operator-portal/src/api/operatorClient.ts` + `src/types.ts` (add `provisionInterview`)
- Modify: `operator-portal/src/test/fakeClient.ts`
- Create: `operator-portal/src/screens/interviews/NewInterview.tsx` (form: matricola → shows the start code in a modal mirroring `FollowupTokenModal`) + test
- Modify: `operator-portal/src/App.tsx` (route), `operator-portal/src/rbac/nav.ts` (operator nav entry), `operator-portal/src/i18n/locales/it.ts` (strings)

**Interfaces:**
- `operatorClient.provisionInterview(matricola: string): Promise<ProvisionInterviewResult>` where `ProvisionInterviewResult = {status:'ok', startCode:string} | {status:'unauthorized'} | {status:'forbidden'} | {status:'conflict'} | {status:'error'}` → `POST /interviews/provision {matricola}` (409 → `conflict`). Mirror `createFollowup`.

- [ ] **Step 1: Write the failing test** (mirror `FollowupTokenModal.test.tsx` + a form): entering a matricola and submitting shows the returned start code (reuse a token modal); a `conflict` shows a "profilo già esistente" message.

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement.** `provisionInterview` in `operatorClient.ts` (mirror `createFollowup`, map 409→`conflict`) + `ProvisionInterviewResult` in `types.ts` + `OperatorClient` interface + `fakeClient.ts`. `NewInterview.tsx`: matricola form → on `ok` render a code modal (mirror `FollowupTokenModal`, generic title `interviews.startCodeTitle`); on `conflict` show `interviews.conflict`; use `useApiError` for `forbidden/unauthorized`. Add route `<Route path="new-interview" element={<NewInterview/>} />` in `App.tsx` and a nav entry `{ path: '/new-interview', labelKey: 'nav.newInterview', built: true }` under `operator` in `nav.ts`. Add i18n strings.

- [ ] **Step 4: Run** `npm test -- --run && npm run typecheck && npm run lint && npm run build` → PASS.

- [ ] **Step 5: Commit**

```bash
git add operator-portal/src
git commit -m "feat(portal): operator provisions an interview (matricola → start code)"
```

---

### Task 10: Portal — supervisor "de-anonymize" screen

**Files:**
- Modify: `operator-portal/src/api/operatorClient.ts` + `src/types.ts` (`resolveIdentity`, `resolveMatricola`)
- Modify: `operator-portal/src/test/fakeClient.ts`
- Create: `operator-portal/src/screens/identity/Deanonymize.tsx` + test
- Modify: `operator-portal/src/App.tsx` (route), `operator-portal/src/rbac/nav.ts` (**supervisor** nav entry), `operator-portal/src/i18n/locales/it.ts`

**Interfaces:**
- `operatorClient.resolveIdentity(pseudonymIds: string[]): Promise<ResolveIdentityResult>` (`{status:'ok', results:[{pseudonymId,matricola}]} | forbidden | unauthorized | error`) → `POST /identity/resolve`.
- `operatorClient.resolveMatricola(matricola: string): Promise<ResolveMatricolaResult>` (`{status:'ok', pseudonymId} | {status:'not-found'} | forbidden | unauthorized | error`) → `POST /identity/resolve-matricola`.

- [ ] **Step 1: Write the failing test:** as supervisor, pasting pseudonyms → shows the matricole; a `forbidden` result (non-supervisor) shows the permissions message. (The server is the authority; the screen is only in the supervisor nav.)

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement.** Client methods (mirror `createFollowup`; map 404→`not-found`) + types + interface + fake client. `Deanonymize.tsx`: a textarea/list to paste pseudonyms → button «De-anonimizza» → table `pseudonimo → matricola`; a second field matricola → pseudonym (for follow-up targeting). Warn banner: «Uso consentito solo per orientamento/matching/follow-up; ogni accesso è tracciato.» Add route `<Route path="deanonymize" element={<Deanonymize/>} />`; nav entry under **supervisor** `{ path: '/deanonymize', labelKey: 'nav.deanonymize', built: true }`; i18n strings.

- [ ] **Step 4: Run** the portal gate → PASS.

- [ ] **Step 5: Commit**

```bash
git add operator-portal/src
git commit -m "feat(portal): supervisor de-anonymization screen (resolve both directions)"
```

---

## Self-Review

**Spec coverage:** §3 nucleus edits → Task 1. §5 data model → Task 2. §6 creation flow → Tasks 3–6, 8. §6.3 resolution → Task 7. §7 API → Tasks 6,7 + kiosk Task 5. §8 permissions → Tasks 6,7. §9 portal → Tasks 9,10. §10 kiosk → Task 8. §11 security → Tasks 2,3,6,7 tests. §12 tests → each task's test-first steps. §13 migration/kiosk-start change → Tasks 2,5,8. §14 out-of-scope respected (no retroactive linking, matricola only, DB-role hardening deferred). ✅

**Type consistency:** `IdentityService.link/resolve/resolve_matricola`, `StartCodeService.issue/consume`, `create_empty_profile`, `Interview.start_on`, `PROVISION_INTERVIEW`/`DEANONYMIZE`, audit actions `identity_link_created`/`identity_resolved`, provision `{start_code}`, kiosk `{start_code, language}` — used consistently across tasks. ✅

**Placeholder scan:** backend tasks carry full code; frontend tasks (8–10) give exact new signatures, i18n keys, routes/nav wiring, and name the exact existing file to mirror (`FollowupEntry.tsx`, `FollowupTokenModal.tsx`, `createFollowup`) — the implementer copies a real, cited pattern rather than inventing. Test harness fixtures (operator/supervisor/auditor authed clients, DB conn) follow the existing `backend/tests/api/` and `backend/tests/data/` patterns.

**Note on the kiosk-start change (Task 5/8):** replacing anonymous self-start with code-launched start updates `scripts/smoke-full-stack.sh` / any e2e that self-starts an interview — the final whole-branch review must confirm those still pass or are updated.
