# Piano — Sottosistema 2: Strato dati sicuro (PostgreSQL)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistere i profili lavorativi e un registro di audit immutabile su PostgreSQL, con segregazione a ruoli imposta dal DB, filtro PII al salvataggio e audit append-only con hash-chain.

**Architecture:** Nuovo package `bussola.data` (psycopg3 + migrazioni SQL). Schemi `profiles` e `audit` separati; ruoli `bussola_owner`/`bussola_app`/`bussola_auditor`. Profilo come JSONB (validato da Pydantic). Audit hash-chained con verifica. Nessun dato di identità nel sistema.

**Tech Stack:** Python 3.12, psycopg3 (LGPL, accettato per §3 — vedi spec), PostgreSQL 16 (docker-compose), pytest.

## Global Constraints

- **Locale / on-premise:** Postgres in docker-compose, esposto **solo su `127.0.0.1`**; nessun servizio esterno.
- **Open source:** psycopg3 (LGPL-3.0, accettato come interpretazione larga di §3; GPL forte e non-commerciale restano esclusi), PostgreSQL license, pytest MIT.
- **Nessun dato di identità:** il sistema non memorizza mai anagrafica né mappa pseudonimo↔persona. Nessun `pgcrypto`.
- **Privilegio minimo imposto dal DB:** `owner` (DDL), `app` (RW profili, **INSERT+SELECT** audit, **mai** UPDATE/DELETE), `auditor` (**SELECT** audit, **nessun** accesso ai profili).
- **Audit append-only:** `UPDATE`/`DELETE` revocati **e** vietati da trigger; **hash-chain** anti-manomissione.
- **Filtro PII al salvataggio (§7.3):** `save` applica `sanitize_profile` prima di persistere; fail-closed.
- **TDD**; **solo dati sintetici**; **codice in inglese** (§11).
- **Prerequisito test:** Postgres attivo (`docker compose up -d db`). I test si **skippano** con messaggio chiaro se il DB non è raggiungibile.
- **Shell state non persiste tra chiamate Bash:** usare i binari del venv per percorso assoluto (`backend/.venv/bin/...`).

---

## Struttura dei file

```
progetto_bussola/
├── docker-compose.yml                      # servizio Postgres (solo 127.0.0.1)
├── .env.example                            # variabili + default dev
├── db-init/
│   └── 00-roles.sh                         # bootstrap ruoli (superuser, al primo init)
└── backend/
    ├── pyproject.toml                       # + psycopg[binary]
    ├── src/bussola/data/
    │   ├── __init__.py
    │   ├── config.py                        # DSN da env (owner/app/auditor/superuser)
    │   ├── connection.py                    # helper di connessione psycopg3
    │   ├── pseudonym.py                     # generate_pseudonym()
    │   ├── migrate.py                       # runner minimale
    │   ├── migrations/
    │   │   ├── 0001_schemas_and_roles.sql
    │   │   ├── 0002_profiles.sql
    │   │   └── 0003_audit.sql
    │   ├── profiles.py                      # ProfileRepository
    │   └── audit.py                         # append_audit, verify_audit_chain
    └── tests/data/
        ├── conftest.py                      # skip-if-no-db + DB fixtures
        ├── test_pseudonym.py
        ├── test_connection.py
        ├── test_migrations.py
        ├── test_profiles.py
        └── test_audit.py
```

---

### Task 1: Generatore di pseudonimo (puro, senza DB)

**Files:**
- Create: `backend/src/bussola/data/__init__.py` (vuoto)
- Create: `backend/src/bussola/data/pseudonym.py`
- Test: `backend/tests/data/test_pseudonym.py`

**Interfaces:**
- Consumes: nulla.
- Produces: `generate_pseudonym() -> str` — identificativo opaco, prefisso `"P-"`, lunghezza ≤ 64.

- [ ] **Step 1: Scrivere i test (falliscono: modulo assente)**

File `backend/tests/data/test_pseudonym.py`:

```python
from bussola.data.pseudonym import generate_pseudonym


def test_has_prefix_and_hex_body():
    pid = generate_pseudonym()
    assert pid.startswith("P-")
    body = pid[2:]
    assert body and all(c in "0123456789abcdef" for c in body)


def test_within_profile_length_bounds():
    pid = generate_pseudonym()
    assert 1 <= len(pid) <= 64


def test_values_are_unique():
    values = {generate_pseudonym() for _ in range(1000)}
    assert len(values) == 1000
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_pseudonym.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'bussola.data'`.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/data/__init__.py`: (vuoto)

File `backend/src/bussola/data/pseudonym.py`:

```python
"""Opaque pseudonym generation.

The pseudonym is the ONLY identifier of a work profile. The system never
stores the link between a pseudonym and a real person — that register lives
outside the system.
"""

from __future__ import annotations

import secrets

_PREFIX = "P-"


def generate_pseudonym() -> str:
    """Return a new opaque, unguessable pseudonym (e.g. 'P-a1b2c3...')."""
    return _PREFIX + secrets.token_hex(8)  # 'P-' + 16 hex chars = 18 chars
```

- [ ] **Step 4: Eseguire i test (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_pseudonym.py -q`
Expected: PASS (3 test).

- [ ] **Step 5: Committare**

```bash
git add backend/src/bussola/data/__init__.py backend/src/bussola/data/pseudonym.py backend/tests/data/test_pseudonym.py
git commit -m "feat(data): generatore di pseudonimo opaco"
```

---

### Task 2: Postgres (docker-compose) + ruoli + config + connessione

**Files:**
- Create: `docker-compose.yml`, `.env.example`, `db-init/00-roles.sh`
- Modify: `backend/pyproject.toml` (aggiunge `psycopg[binary]`)
- Create: `backend/src/bussola/data/config.py`, `backend/src/bussola/data/connection.py`
- Create: `backend/tests/data/conftest.py` (skip-if-no-db), `backend/tests/data/test_connection.py`

**Interfaces:**
- Produces: `config.dsn(role: str, dbname: str | None = None) -> str` (ruoli: `owner`, `app`, `auditor`, `superuser`); `connection.connect(role, dbname=None)` context manager → `psycopg.Connection`.

- [ ] **Step 1: `docker-compose.yml` + `.env.example` + init dei ruoli**

File `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: bussola
      POSTGRES_PASSWORD: ${POSTGRES_SUPERUSER_PASSWORD:-postgres_dev}
      BUSSOLA_OWNER_PASSWORD: ${BUSSOLA_OWNER_PASSWORD:-owner_dev}
      BUSSOLA_APP_PASSWORD: ${BUSSOLA_APP_PASSWORD:-app_dev}
      BUSSOLA_AUDITOR_PASSWORD: ${BUSSOLA_AUDITOR_PASSWORD:-auditor_dev}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - ./db-init:/docker-entrypoint-initdb.d:ro
      - bussola_pgdata:/var/lib/postgresql/data

volumes:
  bussola_pgdata:
```

File `.env.example`:

```bash
# Copia in .env e cambia le password in produzione. Valori di default = solo sviluppo locale.
POSTGRES_SUPERUSER_PASSWORD=postgres_dev
BUSSOLA_OWNER_PASSWORD=owner_dev
BUSSOLA_APP_PASSWORD=app_dev
BUSSOLA_AUDITOR_PASSWORD=auditor_dev
# Connessione (default già validi per docker-compose locale)
BUSSOLA_DB_HOST=127.0.0.1
BUSSOLA_DB_PORT=5432
BUSSOLA_DB_NAME=bussola
```

File `db-init/00-roles.sh`:

```bash
#!/bin/bash
# Runs once, as superuser, on first container init. Creates the least-privilege
# roles and makes bussola_owner own the database (so it can run DDL migrations).
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE bussola_owner   LOGIN PASSWORD '${BUSSOLA_OWNER_PASSWORD}';
    CREATE ROLE bussola_app     LOGIN PASSWORD '${BUSSOLA_APP_PASSWORD}';
    CREATE ROLE bussola_auditor LOGIN PASSWORD '${BUSSOLA_AUDITOR_PASSWORD}';
    ALTER DATABASE ${POSTGRES_DB} OWNER TO bussola_owner;
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO bussola_app, bussola_auditor;
EOSQL
```

- [ ] **Step 2: Aggiungere la dipendenza e avviare Postgres**

Nel file `backend/pyproject.toml`, sezione `dependencies`, aggiungere la riga `psycopg[binary]>=3.1,<4` (dopo `spacy`).

Run (da repo root):

```bash
backend/.venv/bin/pip install -e "backend[dev]"
docker compose up -d db
sleep 5   # attende l'avvio + init dei ruoli (una tantum)
```

Expected: container `db` up; ruoli creati al primo init.

- [ ] **Step 3: Scrivere `conftest.py` (skip-if-no-db) e il test di connessione (fallisce: config assente)**

File `backend/tests/data/conftest.py`:

```python
"""Fixtures for data-layer tests. Require a running Postgres:
    docker compose up -d db
"""

from __future__ import annotations

import psycopg
import pytest

from bussola.data import config


def _server_reachable() -> bool:
    try:
        with psycopg.connect(config.dsn("superuser", dbname="postgres"), connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _server_reachable(),
    reason="Postgres non raggiungibile (avvia: docker compose up -d db)",
)
```

File `backend/tests/data/test_connection.py`:

```python
from bussola.data.connection import connect

from .conftest import requires_db


@requires_db
def test_owner_can_connect():
    with connect("owner") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
```

> Il RED arriva naturalmente: `connection`/`config` non esistono ancora → `ModuleNotFoundError: No module named 'bussola.data.config'`.

- [ ] **Step 4: Eseguire il test (deve fallire)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_connection.py -q`
Expected: FAIL con `ModuleNotFoundError` (config/connection assenti).

- [ ] **Step 5: Implementare `config.py` e `connection.py`**

File `backend/src/bussola/data/config.py`:

```python
"""Database connection configuration, from environment with dev-only defaults.

The defaults match docker-compose.yml so tests run out-of-the-box against a
local Postgres. In production every value is overridden via environment
variables; passwords are never committed.
"""

from __future__ import annotations

import os

_HOST = os.environ.get("BUSSOLA_DB_HOST", "127.0.0.1")
_PORT = os.environ.get("BUSSOLA_DB_PORT", "5432")
_DBNAME = os.environ.get("BUSSOLA_DB_NAME", "bussola")

# role -> (db user, password env var, dev-only default password)
_ROLES = {
    "owner": ("bussola_owner", "BUSSOLA_OWNER_PASSWORD", "owner_dev"),
    "app": ("bussola_app", "BUSSOLA_APP_PASSWORD", "app_dev"),
    "auditor": ("bussola_auditor", "BUSSOLA_AUDITOR_PASSWORD", "auditor_dev"),
    "superuser": ("postgres", "POSTGRES_SUPERUSER_PASSWORD", "postgres_dev"),
}


def dsn(role: str, dbname: str | None = None) -> str:
    """Build a libpq connection string for the given role."""
    if role not in _ROLES:
        raise ValueError(f"unknown role: {role!r}")
    user, env_key, default = _ROLES[role]
    password = os.environ.get(env_key, default)
    database = dbname or _DBNAME
    return f"host={_HOST} port={_PORT} dbname={database} user={user} password={password}"
```

File `backend/src/bussola/data/connection.py`:

```python
"""Thin psycopg3 connection helper."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from bussola.data import config


@contextmanager
def connect(role: str, dbname: str | None = None) -> Iterator[psycopg.Connection]:
    """Open a connection for the given role; close it on exit."""
    conn = psycopg.connect(config.dsn(role, dbname))
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 6: Eseguire il test (deve passare)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_connection.py -q`
Expected: PASS `test_owner_can_connect` (o SKIP con messaggio chiaro se il DB non è su — in tal caso avviare `docker compose up -d db`).

- [ ] **Step 7: Committare**

```bash
git add docker-compose.yml .env.example db-init/00-roles.sh backend/pyproject.toml \
        backend/src/bussola/data/config.py backend/src/bussola/data/connection.py \
        backend/tests/data/conftest.py backend/tests/data/test_connection.py
git commit -m "feat(data): postgres docker-compose, ruoli a privilegio minimo, config e connessione"
```

---

### Task 3: Runner di migrazioni + schemi e grant (0001) + fixture DB

**Files:**
- Create: `backend/src/bussola/data/migrate.py`, `backend/src/bussola/data/migrations/0001_schemas_and_roles.sql`
- Modify: `backend/tests/data/conftest.py` (aggiunge fixture del DB di test)
- Test: `backend/tests/data/test_migrations.py`

**Interfaces:**
- Produces: `apply_migrations(conn, migrations_dir=None) -> list[str]`; fixture pytest `test_database` (crea+migra `bussola_test`), `db` (truncate tra i test), `owner_conn`/`app_conn`/`auditor_conn`.

- [ ] **Step 1: Espandere `conftest.py` con le fixture del DB di test**

Aggiungere in fondo a `backend/tests/data/conftest.py`:

```python
from collections.abc import Iterator

from bussola.data.migrate import apply_migrations

_TEST_DB = "bussola_test"


@pytest.fixture(scope="session")
def test_database() -> Iterator[None]:
    # Recreate a clean test database owned by bussola_owner.
    with psycopg.connect(config.dsn("superuser", dbname="postgres")) as su:
        su.autocommit = True
        with su.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (_TEST_DB,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {_TEST_DB}")
            cur.execute(f"CREATE DATABASE {_TEST_DB} OWNER bussola_owner")
            cur.execute(f"GRANT CONNECT ON DATABASE {_TEST_DB} TO bussola_app, bussola_auditor")
    with psycopg.connect(config.dsn("owner", dbname=_TEST_DB)) as owner:
        apply_migrations(owner)
    yield


@pytest.fixture
def db(test_database: None) -> Iterator[None]:
    # Truncate mutable tables between tests. TRUNCATE bypasses the append-only
    # row trigger, and owner owns the tables. Guarded so it works before the
    # profiles/audit tables exist (Task 3 only has schemas).
    with psycopg.connect(config.dsn("owner", dbname=_TEST_DB)) as owner:
        with owner.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('audit.audit_log'), to_regclass('profiles.work_profile')"
            )
            audit_tbl, profiles_tbl = cur.fetchone()
            if audit_tbl is not None:
                cur.execute("TRUNCATE audit.audit_log RESTART IDENTITY")
            if profiles_tbl is not None:
                cur.execute("TRUNCATE profiles.work_profile")
        owner.commit()
    yield


def _role_conn(role: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(config.dsn(role, dbname=_TEST_DB)) as conn:
        yield conn


@pytest.fixture
def owner_conn(db: None) -> Iterator[psycopg.Connection]:
    yield from _role_conn("owner")


@pytest.fixture
def app_conn(db: None) -> Iterator[psycopg.Connection]:
    yield from _role_conn("app")


@pytest.fixture
def auditor_conn(db: None) -> Iterator[psycopg.Connection]:
    yield from _role_conn("auditor")
```

- [ ] **Step 2: Scrivere i test delle migrazioni (falliscono: runner/0001 assenti)**

File `backend/tests/data/test_migrations.py`:

```python
import psycopg
import pytest

from .conftest import requires_db

pytestmark = requires_db


def test_schemas_exist(owner_conn: psycopg.Connection):
    with owner_conn.cursor() as cur:
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name IN ('profiles', 'audit')"
        )
        found = {r[0] for r in cur.fetchall()}
    assert found == {"profiles", "audit"}


def test_auditor_cannot_use_profiles_schema(auditor_conn: psycopg.Connection):
    with auditor_conn.cursor() as cur:
        cur.execute(
            "SELECT has_schema_privilege('bussola_auditor', 'profiles', 'USAGE')"
        )
        assert cur.fetchone()[0] is False


def test_app_can_use_both_schemas(app_conn: psycopg.Connection):
    with app_conn.cursor() as cur:
        cur.execute("SELECT has_schema_privilege('bussola_app', 'profiles', 'USAGE')")
        assert cur.fetchone()[0] is True
        cur.execute("SELECT has_schema_privilege('bussola_app', 'audit', 'USAGE')")
        assert cur.fetchone()[0] is True
```

- [ ] **Step 3: Eseguire i test (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_migrations.py -q`
Expected: FAIL (import di `apply_migrations` fallisce / migrazione 0001 assente).

- [ ] **Step 4: Implementare il runner e la migrazione 0001**

File `backend/src/bussola/data/migrate.py`:

```python
"""Minimal, transparent SQL migration runner.

Applies *.sql files from a directory in filename order, recording applied
ones in bussola_meta.schema_migrations. Must run as the owner role (DDL).
"""

from __future__ import annotations

from pathlib import Path

import psycopg

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path | None = None) -> list[str]:
    """Apply pending migrations in filename order; return newly applied names."""
    directory = migrations_dir or _MIGRATIONS_DIR
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS bussola_meta")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS bussola_meta.schema_migrations ("
            "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT name FROM bussola_meta.schema_migrations")
        applied = {row[0] for row in cur.fetchall()}

    newly_applied: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        if path.name in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO bussola_meta.schema_migrations (name) VALUES (%s)",
                (path.name,),
            )
        conn.commit()
        newly_applied.append(path.name)
    return newly_applied
```

File `backend/src/bussola/data/migrations/0001_schemas_and_roles.sql`:

```sql
-- Segregated schemas + least-privilege schema grants. Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS profiles AUTHORIZATION bussola_owner;
CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION bussola_owner;

-- app uses both schemas; auditor only the audit schema.
GRANT USAGE ON SCHEMA profiles TO bussola_app;
GRANT USAGE ON SCHEMA audit TO bussola_app;
GRANT USAGE ON SCHEMA audit TO bussola_auditor;
-- auditor gets NO privilege on the profiles schema (absence of grant = no access).
```

- [ ] **Step 5: Eseguire i test (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_migrations.py -q`
Expected: PASS (3 test).

- [ ] **Step 6: Committare**

```bash
git add backend/src/bussola/data/migrate.py \
        backend/src/bussola/data/migrations/0001_schemas_and_roles.sql \
        backend/tests/data/conftest.py backend/tests/data/test_migrations.py
git commit -m "feat(data): runner di migrazioni + schemi segregati e grant (0001)"
```

---

### Task 4: Persistenza dei profili (0002 + ProfileRepository)

**Files:**
- Create: `backend/src/bussola/data/migrations/0002_profiles.sql`, `backend/src/bussola/data/profiles.py`
- Test: `backend/tests/data/test_profiles.py`

**Interfaces:**
- Consumes: `WorkProfile` (Sott. 1), `sanitize_profile`/`PiiRedactor` (Sott. 1), `generate_pseudonym` (Task 1).
- Produces: `ProfileRepository(conn, redactor, language="it")` con `create_new() -> str`, `save(profile) -> WorkProfile`, `get(pseudonym_id) -> WorkProfile | None`.

- [ ] **Step 1: Scrivere i test (falliscono: 0002/repository assenti)**

File `backend/tests/data/test_profiles.py`:

```python
import psycopg
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkExperience, WorkProfile

from .conftest import requires_db

pytestmark = requires_db


@pytest.fixture(scope="session")
def redactor() -> PiiRedactor:
    return PiiRedactor()


def test_create_new_returns_persisted_pseudonym(app_conn: psycopg.Connection, redactor):
    repo = ProfileRepository(app_conn, redactor)
    pid = repo.create_new()
    assert pid.startswith("P-")
    loaded = repo.get(pid)
    assert loaded is not None
    assert loaded.pseudonym_id == pid


def test_save_round_trips(app_conn: psycopg.Connection, redactor):
    repo = ProfileRepository(app_conn, redactor)
    profile = WorkProfile(
        pseudonym_id="P-roundtrip",
        skills=[Skill(name="cooking", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)],
        experiences=[WorkExperience(role="cook", sector="catering", duration_months=24)],
    )
    repo.save(profile)
    loaded = repo.get("P-roundtrip")
    assert loaded is not None
    assert loaded.skills[0].name == "cooking"
    assert loaded.experiences[0].duration_months == 24


def test_save_redacts_pii_before_persisting(app_conn: psycopg.Connection, redactor):
    repo = ProfileRepository(app_conn, redactor)
    profile = WorkProfile(
        pseudonym_id="P-pii",
        skills=[Skill(name="contact mario.rossi@example.com", kind=SkillKind.SOFT, evidence=EvidenceGrade.STATED)],
    )
    repo.save(profile)
    # The raw stored JSONB must not contain the email.
    with app_conn.cursor() as cur:
        cur.execute("SELECT profile::text FROM profiles.work_profile WHERE pseudonym_id = %s", ("P-pii",))
        stored = cur.fetchone()[0]
    assert "mario.rossi@example.com" not in stored


def test_get_missing_returns_none(app_conn: psycopg.Connection, redactor):
    repo = ProfileRepository(app_conn, redactor)
    assert repo.get("P-does-not-exist") is None
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_profiles.py -q`
Expected: FAIL (import di `ProfileRepository` / tabella `profiles.work_profile` assente).

- [ ] **Step 3: Implementare 0002 e il repository**

File `backend/src/bussola/data/migrations/0002_profiles.sql`:

```sql
-- Work profiles, keyed by pseudonym; the validated profile is stored as JSONB.
CREATE TABLE profiles.work_profile (
    pseudonym_id text PRIMARY KEY,
    profile      jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

-- app may read and write profiles; never DELETE.
GRANT SELECT, INSERT, UPDATE ON profiles.work_profile TO bussola_app;
```

File `backend/src/bussola/data/profiles.py`:

```python
"""Profile persistence. Applies the outbound PII filter on save (§7.3)."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from bussola.data.pseudonym import generate_pseudonym
from bussola.guardrails.pii import PiiRedactor, sanitize_profile
from bussola.profile.models import WorkProfile


class ProfileRepository:
    """Reads and writes work profiles.

    `save` redacts PII before persisting and may raise
    ``pydantic.ValidationError`` if redaction would violate the schema
    (fail-closed) — callers must be prepared to handle it.
    """

    def __init__(
        self, conn: psycopg.Connection, redactor: PiiRedactor, language: str = "it"
    ) -> None:
        self._conn = conn
        self._redactor = redactor
        self._language = language

    def create_new(self) -> str:
        """Create an empty profile under a fresh pseudonym; return the pseudonym."""
        pseudonym = generate_pseudonym()
        self._upsert(WorkProfile(pseudonym_id=pseudonym))
        return pseudonym

    def save(self, profile: WorkProfile) -> WorkProfile:
        """Redact PII (§7.3), persist, and return the sanitized profile."""
        clean = sanitize_profile(profile, self._redactor, self._language)
        self._upsert(clean)
        return clean

    def get(self, pseudonym_id: str) -> WorkProfile | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT profile FROM profiles.work_profile WHERE pseudonym_id = %s",
                (pseudonym_id,),
            )
            row = cur.fetchone()
        return WorkProfile.model_validate(row[0]) if row is not None else None

    def _upsert(self, profile: WorkProfile) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO profiles.work_profile (pseudonym_id, profile) "
                "VALUES (%s, %s) "
                "ON CONFLICT (pseudonym_id) DO UPDATE "
                "SET profile = EXCLUDED.profile, updated_at = now()",
                (profile.pseudonym_id, Jsonb(profile.model_dump(mode="json"))),
            )
        self._conn.commit()
```

- [ ] **Step 4: Eseguire i test (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_profiles.py -q`
Expected: PASS (4 test).

- [ ] **Step 5: Committare**

```bash
git add backend/src/bussola/data/migrations/0002_profiles.sql \
        backend/src/bussola/data/profiles.py backend/tests/data/test_profiles.py
git commit -m "feat(data): persistenza profili (JSONB) con filtro PII al salvataggio"
```

---

### Task 5: Audit append-only + hash-chain (0003 + append/verify)

**Files:**
- Create: `backend/src/bussola/data/migrations/0003_audit.sql`, `backend/src/bussola/data/audit.py`
- Test: `backend/tests/data/test_audit.py`

**Interfaces:**
- Produces: `append_audit(conn, *, action, actor=None, target_pseudonym=None, details=None) -> None`; `verify_audit_chain(conn) -> VerificationResult(ok, broken_at, reason)`.

- [ ] **Step 1: Scrivere i test (falliscono: 0003/audit assenti)**

File `backend/tests/data/test_audit.py`:

```python
import psycopg
import pytest

from bussola.data.audit import append_audit, verify_audit_chain

from .conftest import requires_db

pytestmark = requires_db


def test_append_and_verify_ok(app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    append_audit(app_conn, action="matching_run", actor="op1")
    result = verify_audit_chain(app_conn)
    assert result.ok is True


def test_app_cannot_update_audit(app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1")
    with pytest.raises(psycopg.Error):
        with app_conn.cursor() as cur:
            cur.execute("UPDATE audit.audit_log SET action = 'tampered'")
    app_conn.rollback()


def test_app_cannot_delete_audit(app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1")
    with pytest.raises(psycopg.Error):
        with app_conn.cursor() as cur:
            cur.execute("DELETE FROM audit.audit_log")
    app_conn.rollback()


def test_auditor_can_read_audit_but_not_profiles(auditor_conn: psycopg.Connection, app_conn: psycopg.Connection):
    append_audit(app_conn, action="export_performed", actor="sup1")
    with auditor_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log")
        assert cur.fetchone()[0] == 1
    with pytest.raises(psycopg.Error):
        with auditor_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM profiles.work_profile")
    auditor_conn.rollback()


def test_tampering_is_detected(app_conn: psycopg.Connection, owner_conn: psycopg.Connection):
    append_audit(app_conn, action="a1", actor="op1")
    append_audit(app_conn, action="a2", actor="op1")
    # Tamper as owner (drop the append-only trigger, mutate, restore).
    with owner_conn.cursor() as cur:
        cur.execute("ALTER TABLE audit.audit_log DISABLE TRIGGER audit_log_append_only")
        cur.execute("UPDATE audit.audit_log SET action = 'tampered' WHERE id = 1")
        cur.execute("ALTER TABLE audit.audit_log ENABLE TRIGGER audit_log_append_only")
    owner_conn.commit()
    result = verify_audit_chain(app_conn)
    assert result.ok is False
    assert result.broken_at == 1
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_audit.py -q`
Expected: FAIL (import di `append_audit` / tabella `audit.audit_log` assente).

- [ ] **Step 3: Implementare 0003 e `audit.py`**

File `backend/src/bussola/data/migrations/0003_audit.sql`:

```sql
-- Append-only, tamper-evident audit log.
CREATE TABLE audit.audit_log (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at      timestamptz NOT NULL,
    actor            text,
    action           text NOT NULL,
    target_pseudonym text,
    details          jsonb NOT NULL DEFAULT '{}'::jsonb,
    prev_hash        text,
    record_hash      text NOT NULL
);

-- app may append and read (reading is needed to chain); auditor may only read.
GRANT SELECT, INSERT ON audit.audit_log TO bussola_app;
GRANT SELECT ON audit.audit_log TO bussola_auditor;

-- Append-only: forbid UPDATE/DELETE for everyone via a row-level trigger.
-- Extraordinary maintenance = owner deliberately disables/drops the trigger.
CREATE OR REPLACE FUNCTION audit.forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit.audit_log is append-only: % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_append_only
    BEFORE UPDATE OR DELETE ON audit.audit_log
    FOR EACH ROW EXECUTE FUNCTION audit.forbid_mutation();
```

File `backend/src/bussola/data/audit.py`:

```python
"""Append-only, tamper-evident audit log (hash-chained)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

_CHAIN_LOCK_KEY = 4242  # advisory-lock key serializing audit appends


def _record_hash(
    occurred_at: datetime,
    actor: str | None,
    action: str,
    target_pseudonym: str | None,
    details: dict,
    prev_hash: str | None,
) -> str:
    canonical = json.dumps(
        {
            "occurred_at": occurred_at.astimezone(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "target_pseudonym": target_pseudonym,
            "details": details,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit(
    conn: psycopg.Connection,
    *,
    action: str,
    actor: str | None = None,
    target_pseudonym: str | None = None,
    details: dict | None = None,
) -> None:
    """Append one audit record, chained to the previous one."""
    payload = details or {}
    occurred_at = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_CHAIN_LOCK_KEY,))
        cur.execute("SELECT record_hash FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        prev_hash = row[0] if row is not None else None
        record_hash = _record_hash(
            occurred_at, actor, action, target_pseudonym, payload, prev_hash
        )
        cur.execute(
            "INSERT INTO audit.audit_log "
            "(occurred_at, actor, action, target_pseudonym, details, prev_hash, record_hash) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (occurred_at, actor, action, target_pseudonym, Jsonb(payload), prev_hash, record_hash),
        )
    conn.commit()


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    broken_at: int | None = None
    reason: str | None = None


def verify_audit_chain(conn: psycopg.Connection) -> VerificationResult:
    """Walk the chain in id order; report the first record that breaks it."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, occurred_at, actor, action, target_pseudonym, details, prev_hash, record_hash "
            "FROM audit.audit_log ORDER BY id ASC"
        )
        rows = cur.fetchall()

    expected_prev: str | None = None
    for rid, occurred_at, actor, action, target, details, prev_hash, record_hash in rows:
        if prev_hash != expected_prev:
            return VerificationResult(ok=False, broken_at=rid, reason="prev_hash mismatch")
        if _record_hash(occurred_at, actor, action, target, details, prev_hash) != record_hash:
            return VerificationResult(ok=False, broken_at=rid, reason="record_hash mismatch")
        expected_prev = record_hash
    return VerificationResult(ok=True)
```

- [ ] **Step 4: Eseguire i test (devono passare)**

Run: `backend/.venv/bin/pytest backend/tests/data/test_audit.py -q`
Expected: PASS (5 test): append+verify, no-UPDATE, no-DELETE, auditor read-only, tampering rilevato.

- [ ] **Step 5: Gate completo del backend**

Run (da repo root, con Postgres su):

```bash
backend/.venv/bin/pytest backend/tests -q
backend/.venv/bin/ruff check backend/
backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/src
```
Expected: tutto verde (i test del data layer si skippano solo se il DB non è raggiungibile).

- [ ] **Step 6: Committare**

```bash
git add backend/src/bussola/data/migrations/0003_audit.sql \
        backend/src/bussola/data/audit.py backend/tests/data/test_audit.py
git commit -m "feat(data): audit append-only con hash-chain e verifica"
```

---

## Note di chiusura (scelte di ambito)

- **Log delle conversazioni**: schema `conversations` non creato ora (Sott. 4). Gli schemi `profiles`/`audit` sono già separati.
- **Indici GIN** per il matching su JSONB: Sott. 6.
- **Account operatore / autenticazione / RBAC**: sottosistema «Auth & operatori» (popolerà `actor` nell'audit).
- **Cifratura a riposo**: LUKS full-disk = passo di deployment, fuori dal codice.
- **`mypy` e psycopg3**: psycopg3 fornisce type hint (`py.typed`); se emergono attriti strict mirati, aggiungere `# type: ignore[<code>]` puntuali (come nel Sott. 1), mai disabilitare strict globalmente.

## Verifica di copertura (spec → task)

| Requisito (spec/§) | Task |
|---|---|
| Nessun dato identità; pseudonimo unico id (§3.1) | Task 1, 4 |
| psycopg3 + migrazioni SQL (§3.3) | Task 2, 3 |
| Ruoli DB coarse a privilegio minimo (§3.4, §5) | Task 2, 3, 5 |
| Profilo JSONB (§3.5) | Task 4 |
| Filtro PII al salvataggio, fail-closed (§3.6, §7.3) | Task 4 |
| Audit append-only + hash-chain + verifica (§3.7) | Task 5 |
| Segregazione auditor/app imposta dal DB (§6) | Task 5 |
| TDD, solo dati sintetici (§9) | Tutti |
| Codice in inglese (§11) | Tutti |
