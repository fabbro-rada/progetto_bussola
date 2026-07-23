# Piano — Sottosistema 5: Auth & operatori

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Autenticazione degli operatori, sessioni server-side revocabili, RBAC sui quattro ruoli (§6), e il primo layer HTTP (FastAPI) che espone solo endpoint auth/sessione/gestione account — con audit vincolato e atomico di ogni evento.

**Architecture:** Package `bussola.auth` (dominio: password, rbac, account, sessioni, servizio, bootstrap) + package `bussola.api` (trasporto FastAPI: app, dipendenze, error handler, router). Poggia su S2 (ruoli DB `bussola_app`, schema segregati, `append_audit` hash-chained, runner di migrazioni). Nessuna logica di business del portale.

**Tech Stack:** Python 3.12, FastAPI (MIT) + Starlette TestClient (via httpx già presente), argon2-cffi (MIT, argon2id), psycopg3, Pydantic, PostgreSQL, pytest.

## Global Constraints

- **Locale/on-premise, open source PERMISSIVO, budget nullo** (§3): dipendenze nuove solo MIT/BSD/permissive (`fastapi`, `uvicorn`, `argon2-cffi`); verificare la licenza all'aggiunta.
- **Privilegio minimo + accesso vincolato allo scopo** (§6): RBAC applicato nell'app; `bussola_app` scrive lo schema `auth`, `bussola_auditor` non vi accede.
- **Provisioning dall'Amministratore** (§7.2): nessuna auto-registrazione; identità = username assegnato; primo accesso forza il cambio password.
- **Nessuna credenziale di default versionata**; **password mai nei log**; **token di sessione salvato solo come hash**.
- **Anti-abuso** (§3): errore di login generico (no user-enumeration), dummy-verify sull'utente inesistente, lockout dopo ripetuti fallimenti.
- **Audit di ogni evento auth** (§7.3): `actor`=username, `target_pseudonym`=null, `details`=whitelist (nessun testo libero/PII); operazione d'account e audit **nella stessa transazione**.
- **Codice e identificatori in inglese** (§11); stringhe utente/errore predisposte i18n dove rivolte all'utente.
- **TDD; solo dati sintetici** (§9). **Sicurezza-first**: RBAC, revoca, lockout, no-enumeration, auth su ogni endpoint, audit atomico prima di tutto.
- **Gate**: `ruff check` + `ruff format --check` (file toccati) + `mypy --strict` su `backend/src` puliti.
- **Shell state non persiste tra chiamate Bash**: usare percorsi assoluti `backend/.venv/bin/...` dalla radice del repo; niente `cd`.
- I test che toccano il DB usano le fixture condivise di `backend/tests/conftest.py` (`owner_conn`/`app_conn`/`auditor_conn`) e si skippano se Postgres è giù. Le migrazioni (incl. `0004_auth.sql`) sono applicate dalla fixture `test_database`.

---

## Struttura dei file

```
backend/
├── pyproject.toml                         # + fastapi, uvicorn, argon2-cffi
└── src/bussola/
    ├── data/
    │   ├── audit.py                        # + parametro commit (unità-di-lavoro)
    │   └── migrations/0004_auth.sql        # schema auth: operator + session
    ├── auth/
    │   ├── __init__.py
    │   ├── rbac.py                          # Role, Permission, ROLE_PERMISSIONS, has_permission
    │   ├── passwords.py                     # argon2id hash/verify + dummy_verify
    │   ├── models.py                        # Operator (pubblico), OperatorRecord (interno), DTO
    │   ├── auth_audit.py                    # record_auth_event (details vincolato, commit=False)
    │   ├── accounts.py                      # AccountRepository (CRUD auth.operator)
    │   ├── sessions.py                      # SessionStore (token hash, create/lookup/revoke)
    │   ├── config.py                        # tunables da env (ttl, idle, lockout)
    │   ├── service.py                       # AuthService (login/logout/authenticate/change_pw + account mgmt)
    │   ├── errors.py                        # AuthError, PermissionDenied, ...
    │   └── bootstrap.py                     # CLI primo admin
    └── api/
        ├── __init__.py
        ├── app.py                           # create_app() factory
        ├── deps.py                          # get_conn, current_operator, require_role/permission
        ├── errors.py                        # handler uniformi
        └── routers/
            ├── __init__.py
            ├── auth.py                       # /auth/login|logout|me|change-password
            └── operators.py                 # /operators (admin)
backend/tests/
├── conftest.py                              # + troncamento tabelle auth nel fixture db
├── auth/
│   ├── __init__.py
│   ├── test_passwords.py
│   ├── test_rbac.py
│   ├── test_migration_auth.py
│   ├── test_accounts.py
│   ├── test_auth_audit.py
│   ├── test_sessions.py
│   ├── test_service_login.py
│   └── test_service_accounts.py
└── api/
    ├── __init__.py
    ├── conftest.py                          # client + admin/operator sintetici
    ├── test_deps.py
    ├── test_auth_router.py
    └── test_operators_router.py
```

---

### Task 1: Fondamenta — dipendenze + `passwords.py` + `rbac.py`

**Files:**
- Modify: `backend/pyproject.toml` (aggiunge `argon2-cffi`)
- Create: `backend/src/bussola/auth/__init__.py` (vuoto), `backend/src/bussola/auth/passwords.py`, `backend/src/bussola/auth/rbac.py`
- Test: `backend/tests/auth/__init__.py` (vuoto), `backend/tests/auth/test_passwords.py`, `backend/tests/auth/test_rbac.py`

**Interfaces:**
- Produces:
  - `passwords.hash_password(password: str) -> str`; `passwords.verify_password(hash_: str, password: str) -> bool`; `passwords.dummy_verify() -> None`.
  - `rbac.Role(str, Enum)` = `OPERATOR|SUPERVISOR|ADMIN|AUDITOR`; `rbac.Permission(str, Enum)`; `rbac.ROLE_PERMISSIONS: dict[Role, frozenset[Permission]]`; `rbac.has_permission(role: Role, permission: Permission) -> bool`.

- [ ] **Step 1: Aggiungere la dipendenza**

In `backend/pyproject.toml`, nella lista `dependencies`, aggiungere dopo `psycopg[binary]...`:
```toml
    "argon2-cffi>=23.1,<24",
```
Poi installarla: `backend/.venv/bin/pip install -e "backend[dev]"` (o `pip install argon2-cffi`).

- [ ] **Step 2: Scrivere i test (falliscono)**

File `backend/tests/auth/__init__.py`: (vuoto)

File `backend/tests/auth/test_passwords.py`:
```python
from bussola.auth import passwords


def test_hash_is_not_plaintext_and_verifies():
    h = passwords.hash_password("s3cret-pw")
    assert h != "s3cret-pw"
    assert passwords.verify_password(h, "s3cret-pw") is True


def test_wrong_password_does_not_verify():
    h = passwords.hash_password("s3cret-pw")
    assert passwords.verify_password(h, "wrong") is False


def test_same_password_hashes_differ_by_salt():
    assert passwords.hash_password("x") != passwords.hash_password("x")


def test_verify_on_garbage_hash_is_false_not_raises():
    assert passwords.verify_password("not-a-hash", "x") is False


def test_dummy_verify_does_not_raise():
    passwords.dummy_verify()
```

File `backend/tests/auth/test_rbac.py`:
```python
from bussola.auth.rbac import Permission, Role, has_permission


def test_admin_can_manage_operators_others_cannot():
    assert has_permission(Role.ADMIN, Permission.MANAGE_OPERATORS) is True
    for role in (Role.OPERATOR, Role.SUPERVISOR, Role.AUDITOR):
        assert has_permission(role, Permission.MANAGE_OPERATORS) is False


def test_operator_business_permissions():
    assert has_permission(Role.OPERATOR, Permission.READ_PROFILES) is True
    assert has_permission(Role.OPERATOR, Permission.RUN_MATCHING) is True
    assert has_permission(Role.OPERATOR, Permission.READ_AUDIT) is False


def test_auditor_only_reads_audit():
    assert has_permission(Role.AUDITOR, Permission.READ_AUDIT) is True
    assert has_permission(Role.AUDITOR, Permission.READ_PROFILES) is False


def test_supervisor_sees_metrics_not_profiles():
    assert has_permission(Role.SUPERVISOR, Permission.VIEW_METRICS) is True
    assert has_permission(Role.SUPERVISOR, Permission.READ_PROFILES) is False
```

- [ ] **Step 3: Eseguire (devono fallire)**

Run: `backend/.venv/bin/pytest backend/tests/auth/test_passwords.py backend/tests/auth/test_rbac.py -q`
Expected: FAIL (moduli inesistenti).

- [ ] **Step 4: Implementare**

File `backend/src/bussola/auth/__init__.py`: (vuoto)

File `backend/src/bussola/auth/passwords.py`:
```python
"""Password hashing (argon2id). Passwords are never logged or stored in clear."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()
# A fixed hash used only to spend comparable CPU time when the username is
# unknown, so login timing does not reveal whether an account exists.
_DUMMY_HASH = _hasher.hash("timing-equalization-placeholder")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(hash_: str, password: str) -> bool:
    try:
        return _hasher.verify(hash_, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify() -> None:
    """Verify against a fixed hash to equalize timing for unknown users."""
    try:
        _hasher.verify(_DUMMY_HASH, "wrong")
    except VerifyMismatchError:
        pass
```

File `backend/src/bussola/auth/rbac.py`:
```python
"""Role-based access control. Roles map to a fixed set of permissions (§6).

This subsystem ENFORCES only MANAGE_OPERATORS (+ self-service, which needs no
permission, just a valid session). The business permissions are DECLARED here
so the RBAC engine is complete; later subsystems (portal) enforce them.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    AUDITOR = "auditor"


class Permission(str, Enum):
    MANAGE_OPERATORS = "manage_operators"  # enforced now
    # declared; enforced by later subsystems
    READ_PROFILES = "read_profiles"
    MANAGE_JOB_REQUESTS = "manage_job_requests"
    RUN_MATCHING = "run_matching"
    EXPORT_DATA = "export_data"
    VIEW_METRICS = "view_metrics"
    VIEW_OPERATOR_ACTIVITY = "view_operator_activity"
    READ_AUDIT = "read_audit"
    CONFIGURE_SYSTEM = "configure_system"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OPERATOR: frozenset(
        {
            Permission.READ_PROFILES,
            Permission.MANAGE_JOB_REQUESTS,
            Permission.RUN_MATCHING,
            Permission.EXPORT_DATA,
        }
    ),
    Role.SUPERVISOR: frozenset(
        {Permission.VIEW_METRICS, Permission.VIEW_OPERATOR_ACTIVITY}
    ),
    Role.ADMIN: frozenset({Permission.MANAGE_OPERATORS, Permission.CONFIGURE_SYSTEM}),
    Role.AUDITOR: frozenset({Permission.READ_AUDIT}),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
```

- [ ] **Step 5: Eseguire (devono passare)** — `backend/.venv/bin/pytest backend/tests/auth/test_passwords.py backend/tests/auth/test_rbac.py -q` → PASS.

- [ ] **Step 6: Committare**
```bash
git add backend/pyproject.toml backend/src/bussola/auth/__init__.py backend/src/bussola/auth/passwords.py backend/src/bussola/auth/rbac.py backend/tests/auth/__init__.py backend/tests/auth/test_passwords.py backend/tests/auth/test_rbac.py
git commit -m "feat(auth): fondamenta — hashing argon2id + RBAC ruoli/permessi"
```

---

### Task 2: Migrazione `0004_auth.sql` + `models.py` + troncamento fixture

**Files:**
- Create: `backend/src/bussola/data/migrations/0004_auth.sql`, `backend/src/bussola/auth/models.py`
- Modify: `backend/tests/conftest.py` (troncare le tabelle `auth` tra i test)
- Test: `backend/tests/auth/test_migration_auth.py`

**Interfaces:**
- Consumes: runner migrazioni S2 (`apply_migrations`), ruoli DB.
- Produces:
  - Schema `auth` con `auth.operator` e `auth.session` e i grant per `bussola_app`.
  - `models.Operator` (pubblico: `id, username, display_name, role, is_active, must_change_password`, `extra="forbid"`); `models.OperatorRecord` (dataclass interna con anche `password_hash, failed_attempts, locked_until`); DTO `LoginRequest`, `ChangePasswordRequest`, `CreateOperatorRequest`.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/auth/test_migration_auth.py`:

> I test della cartella `auth/` **non** importano `requires_db`. Consumano le fixture DB condivise (`owner_conn`/`app_conn`/`auditor_conn` da `backend/tests/conftest.py`), che **si skippano da sole a setup** se Postgres è giù (la fixture `test_database` chiama `pytest.skip`). Quindi basta `pytestmark = pytest.mark.usefixtures("db")`.

```python
import psycopg
import pytest

pytestmark = pytest.mark.usefixtures("db")


def test_auth_schema_and_tables_exist(owner_conn: psycopg.Connection):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT to_regclass('auth.operator'), to_regclass('auth.session')")
        operator_tbl, session_tbl = cur.fetchone()
    assert operator_tbl is not None
    assert session_tbl is not None


def test_app_can_write_auth_but_auditor_has_no_access(
    app_conn: psycopg.Connection, auditor_conn: psycopg.Connection
):
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO auth.operator (username, display_name, password_hash, role) "
            "VALUES ('u1', 'U One', 'h', 'operator')"
        )
    app_conn.commit()
    with auditor_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT count(*) FROM auth.operator")
    auditor_conn.rollback()
```

- [ ] **Step 2: Eseguire (deve fallire)** — `backend/.venv/bin/pytest backend/tests/auth/test_migration_auth.py -q` → FAIL (schema `auth` inesistente).

- [ ] **Step 3: Implementare la migrazione**

File `backend/src/bussola/data/migrations/0004_auth.sql`:
```sql
-- Operator accounts + server-side sessions. Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION bussola_owner;
-- app manages accounts/sessions; fine-grained who-can-do-what is enforced in
-- the application via RBAC. auditor gets NO access (absence of grant).
GRANT USAGE ON SCHEMA auth TO bussola_app;

CREATE TABLE auth.operator (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username             text NOT NULL UNIQUE,
    display_name         text NOT NULL,
    password_hash        text NOT NULL,
    role                 text NOT NULL,
    is_active            boolean NOT NULL DEFAULT true,
    must_change_password boolean NOT NULL DEFAULT true,
    failed_attempts      integer NOT NULL DEFAULT 0,
    locked_until         timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    created_by           text,
    disabled_at          timestamptz,
    disabled_by          text
);

CREATE TABLE auth.session (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token_hash    text NOT NULL UNIQUE,
    operator_id   bigint NOT NULL REFERENCES auth.operator(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    revoked_at    timestamptz
);
CREATE INDEX session_operator_idx ON auth.session (operator_id);

-- No DELETE: accounts are disabled (not deleted), sessions revoked (not deleted).
GRANT SELECT, INSERT, UPDATE ON auth.operator TO bussola_app;
GRANT SELECT, INSERT, UPDATE ON auth.session TO bussola_app;
```

- [ ] **Step 4: Estendere il troncamento in `backend/tests/conftest.py`**

Nel fixture `db`, dopo il blocco che tronca `audit`/`profiles`, aggiungere (dentro lo stesso `with owner.cursor() as cur:`):
```python
            cur.execute("SELECT to_regclass('auth.session'), to_regclass('auth.operator')")
            session_tbl, operator_tbl = cur.fetchone()
            if session_tbl is not None:
                cur.execute("TRUNCATE auth.session RESTART IDENTITY")
            if operator_tbl is not None:
                cur.execute("TRUNCATE auth.operator RESTART IDENTITY CASCADE")
```

- [ ] **Step 5: Implementare i modelli**

File `backend/src/bussola/auth/models.py`:
```python
"""Auth DTOs. `Operator` is the safe public view (no password hash). The
internal `OperatorRecord` carries the fields login needs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from bussola.auth.rbac import Role

_STRICT = ConfigDict(extra="forbid")


class Operator(BaseModel):
    model_config = _STRICT
    id: int
    username: str
    display_name: str
    role: Role
    is_active: bool
    must_change_password: bool


@dataclass(frozen=True)
class OperatorRecord:
    """Internal login view (never leaves the auth layer)."""

    id: int
    username: str
    display_name: str
    role: Role
    is_active: bool
    must_change_password: bool
    password_hash: str
    failed_attempts: int
    locked_until: datetime | None


class LoginRequest(BaseModel):
    model_config = _STRICT
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    model_config = _STRICT
    old_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class CreateOperatorRequest(BaseModel):
    model_config = _STRICT
    username: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    role: Role
```

- [ ] **Step 6: Eseguire (devono passare)** — `backend/.venv/bin/pytest backend/tests/auth/test_migration_auth.py -q` → PASS.

- [ ] **Step 7: Committare**
```bash
git add backend/src/bussola/data/migrations/0004_auth.sql backend/src/bussola/auth/models.py backend/tests/conftest.py backend/tests/auth/test_migration_auth.py
git commit -m "feat(auth): schema DB auth (operator+session) + modelli + troncamento fixture"
```

---

### Task 3: `accounts.py` — `AccountRepository`

**Files:**
- Create: `backend/src/bussola/auth/accounts.py`, `backend/src/bussola/auth/errors.py`
- Test: `backend/tests/auth/test_accounts.py`

**Interfaces:**
- Consumes: `models.Operator`/`OperatorRecord`, `rbac.Role`, `passwords`.
- Produces:
  - `errors.UsernameExists(Exception)`, `errors.OperatorNotFound(Exception)`.
  - `AccountRepository(conn)` con: `create(*, username, display_name, role, password_hash, created_by, must_change_password=True) -> Operator`; `get_by_username(username) -> OperatorRecord | None`; `get_by_id(operator_id) -> OperatorRecord | None`; `list_all() -> list[Operator]`; `set_active(operator_id, active, *, by) -> None`; `set_password(operator_id, password_hash, *, must_change) -> None`; `record_failed_attempt(operator_id, attempts, locked_until) -> None`; `clear_failures(operator_id) -> None`. Nessun `commit` interno: il chiamante controlla la transazione.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/auth/test_accounts.py`:
```python
import psycopg
import pytest

from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import UsernameExists
from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _repo(app_conn: psycopg.Connection) -> AccountRepository:
    return AccountRepository(app_conn)


def test_create_and_get(app_conn: psycopg.Connection):
    repo = _repo(app_conn)
    op = repo.create(
        username="alice", display_name="Alice", role=Role.OPERATOR,
        password_hash="h", created_by="admin",
    )
    app_conn.commit()
    assert op.username == "alice"
    assert op.role is Role.OPERATOR
    assert op.is_active is True
    assert op.must_change_password is True
    rec = repo.get_by_username("alice")
    assert rec is not None and rec.password_hash == "h"


def test_duplicate_username_rejected(app_conn: psycopg.Connection):
    repo = _repo(app_conn)
    repo.create(username="bob", display_name="Bob", role=Role.ADMIN, password_hash="h", created_by="admin")
    app_conn.commit()
    with pytest.raises(UsernameExists):
        repo.create(username="bob", display_name="Bob2", role=Role.ADMIN, password_hash="h2", created_by="admin")
    app_conn.rollback()


def test_disable_and_list(app_conn: psycopg.Connection):
    repo = _repo(app_conn)
    op = repo.create(username="carl", display_name="Carl", role=Role.OPERATOR, password_hash="h", created_by="admin")
    app_conn.commit()
    repo.set_active(op.id, False, by="admin")
    app_conn.commit()
    rec = repo.get_by_id(op.id)
    assert rec is not None and rec.is_active is False
    assert any(o.username == "carl" for o in repo.list_all())


def test_get_missing_returns_none(app_conn: psycopg.Connection):
    assert _repo(app_conn).get_by_username("nobody") is None
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL (modulo inesistente).

- [ ] **Step 3: Implementare**

File `backend/src/bussola/auth/errors.py`:
```python
"""Auth domain errors (mapped to HTTP status codes at the API boundary)."""

from __future__ import annotations


class AuthError(Exception):
    """Base for auth failures."""


class InvalidCredentials(AuthError):
    """Generic login failure — never reveals whether the username exists."""


class UsernameExists(AuthError):
    pass


class OperatorNotFound(AuthError):
    pass


class PermissionDenied(AuthError):
    pass
```

File `backend/src/bussola/auth/accounts.py`:
```python
"""CRUD for operator accounts (auth.operator). No internal commit: the caller
owns the transaction, so an account change and its audit record commit together."""

from __future__ import annotations

from datetime import datetime

import psycopg

from bussola.auth.errors import UsernameExists
from bussola.auth.models import Operator, OperatorRecord
from bussola.auth.rbac import Role

_RECORD_COLS = (
    "id, username, display_name, role, is_active, must_change_password, "
    "password_hash, failed_attempts, locked_until"
)


def _to_record(row: tuple) -> OperatorRecord:
    return OperatorRecord(
        id=row[0],
        username=row[1],
        display_name=row[2],
        role=Role(row[3]),
        is_active=row[4],
        must_change_password=row[5],
        password_hash=row[6],
        failed_attempts=row[7],
        locked_until=row[8],
    )


def _to_operator(rec: OperatorRecord) -> Operator:
    return Operator(
        id=rec.id,
        username=rec.username,
        display_name=rec.display_name,
        role=rec.role,
        is_active=rec.is_active,
        must_change_password=rec.must_change_password,
    )


class AccountRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(
        self,
        *,
        username: str,
        display_name: str,
        role: Role,
        password_hash: str,
        created_by: str,
        must_change_password: bool = True,
    ) -> Operator:
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth.operator "
                    "(username, display_name, password_hash, role, must_change_password, created_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING " + _RECORD_COLS,
                    (username, display_name, password_hash, role.value, must_change_password, created_by),
                )
                row = cur.fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise UsernameExists(username) from exc
        assert row is not None
        return _to_operator(_to_record(row))

    def get_by_username(self, username: str) -> OperatorRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _RECORD_COLS + " FROM auth.operator WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
        return _to_record(row) if row is not None else None

    def get_by_id(self, operator_id: int) -> OperatorRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _RECORD_COLS + " FROM auth.operator WHERE id = %s",
                (operator_id,),
            )
            row = cur.fetchone()
        return _to_record(row) if row is not None else None

    def list_all(self) -> list[Operator]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT " + _RECORD_COLS + " FROM auth.operator ORDER BY username")
            rows = cur.fetchall()
        return [_to_operator(_to_record(r)) for r in rows]

    def set_active(self, operator_id: int, active: bool, *, by: str) -> None:
        with self._conn.cursor() as cur:
            if active:
                cur.execute(
                    "UPDATE auth.operator SET is_active = true, disabled_at = NULL, "
                    "disabled_by = NULL, failed_attempts = 0, locked_until = NULL WHERE id = %s",
                    (operator_id,),
                )
            else:
                cur.execute(
                    "UPDATE auth.operator SET is_active = false, disabled_at = now(), "
                    "disabled_by = %s WHERE id = %s",
                    (by, operator_id),
                )

    def set_password(self, operator_id: int, password_hash: str, *, must_change: bool) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.operator SET password_hash = %s, must_change_password = %s, "
                "failed_attempts = 0, locked_until = NULL WHERE id = %s",
                (password_hash, must_change, operator_id),
            )

    def record_failed_attempt(
        self, operator_id: int, attempts: int, locked_until: datetime | None
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.operator SET failed_attempts = %s, locked_until = %s WHERE id = %s",
                (attempts, locked_until, operator_id),
            )

    def clear_failures(self, operator_id: int) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.operator SET failed_attempts = 0, locked_until = NULL WHERE id = %s",
                (operator_id,),
            )
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/auth/accounts.py backend/src/bussola/auth/errors.py backend/tests/auth/test_accounts.py
git commit -m "feat(auth): AccountRepository (CRUD operatori, senza commit interno)"
```

---

### Task 4: Audit unità-di-lavoro + `auth_audit.py`

**Files:**
- Modify: `backend/src/bussola/data/audit.py` (parametro `commit: bool = True`)
- Create: `backend/src/bussola/auth/auth_audit.py`
- Test: `backend/tests/auth/test_auth_audit.py`

**Interfaces:**
- Consumes: `append_audit`.
- Produces:
  - `append_audit(..., commit: bool = True)` — se `False`, non fa commit (partecipa alla transazione del chiamante).
  - `auth_audit.record_auth_event(conn, *, action: str, actor: str | None, target_operator: str | None = None, role: str | None = None) -> None` — costruisce un `details` **whitelist** e chiama `append_audit(..., commit=False)`.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/auth/test_auth_audit.py`:
```python
import psycopg
import pytest

from bussola.auth.auth_audit import record_auth_event

pytestmark = pytest.mark.usefixtures("db")


def _count(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log")
        return cur.fetchone()[0]


def test_event_participates_in_caller_transaction_and_rolls_back(app_conn: psycopg.Connection):
    assert _count(app_conn) == 0
    record_auth_event(app_conn, action="login_succeeded", actor="alice")
    # not committed yet -> visible in-tx, absent after rollback
    assert _count(app_conn) == 1
    app_conn.rollback()
    assert _count(app_conn) == 0


def test_details_are_whitelisted(app_conn: psycopg.Connection):
    record_auth_event(
        app_conn, action="operator_created", actor="admin",
        target_operator="bob", role="operator",
    )
    app_conn.commit()
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, action, target_pseudonym, details FROM audit.audit_log ORDER BY id DESC LIMIT 1"
        )
        actor, action, target_pseudonym, details = cur.fetchone()
    assert actor == "admin"
    assert action == "operator_created"
    assert target_pseudonym is None
    assert set(details) <= {"target_operator", "role"}
    assert details["target_operator"] == "bob"
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare — modifica `append_audit`**

In `backend/src/bussola/data/audit.py`, cambiare la firma e il commit finale:
```python
def append_audit(
    conn: psycopg.Connection,
    *,
    action: str,
    actor: str | None = None,
    target_pseudonym: str | None = None,
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    """Append one audit record, chained to the previous one.

    When ``commit`` is False the record is appended within the caller's
    transaction (no own commit), so an operation and its audit record commit
    atomically together.
    """
```
E in fondo, sostituire `conn.commit()` con:
```python
    if commit:
        conn.commit()
```

File `backend/src/bussola/auth/auth_audit.py`:
```python
"""Constrained audit for auth events (§7.3). Details are a strict whitelist
(operator usernames + role only) — never free text or personal data. Appended
within the caller's transaction so the account change and its record are atomic."""

from __future__ import annotations

import psycopg

from bussola.data.audit import append_audit

# Fixed vocabulary of auth actions.
LOGIN_SUCCEEDED = "login_succeeded"
LOGIN_FAILED = "login_failed"
LOGOUT = "logout"
PASSWORD_CHANGED = "password_changed"
OPERATOR_CREATED = "operator_created"
OPERATOR_DISABLED = "operator_disabled"
OPERATOR_ENABLED = "operator_enabled"
OPERATOR_PASSWORD_RESET = "operator_password_reset"


def record_auth_event(
    conn: psycopg.Connection,
    *,
    action: str,
    actor: str | None,
    target_operator: str | None = None,
    role: str | None = None,
) -> None:
    details: dict[str, str] = {}
    if target_operator is not None:
        details["target_operator"] = target_operator
    if role is not None:
        details["role"] = role
    append_audit(
        conn,
        action=action,
        actor=actor,
        target_pseudonym=None,
        details=details,
        commit=False,
    )
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS. Rieseguire i test S2 dell'audit per non-regressione: `backend/.venv/bin/pytest backend/tests/data/test_audit.py -q`.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/data/audit.py backend/src/bussola/auth/auth_audit.py backend/tests/auth/test_auth_audit.py
git commit -m "feat(auth): audit unità-di-lavoro (commit opzionale) + eventi auth vincolati"
```

---

### Task 5: `sessions.py` — `SessionStore`

**Files:**
- Create: `backend/src/bussola/auth/sessions.py`, `backend/src/bussola/auth/config.py`
- Test: `backend/tests/auth/test_sessions.py`

**Interfaces:**
- Produces:
  - `config.SESSION_TTL_SECONDS`, `config.SESSION_IDLE_SECONDS`, `config.MAX_FAILED_ATTEMPTS`, `config.LOCKOUT_SECONDS` (da env con default 43200/1800/5/900).
  - `SessionStore(conn, *, now: Callable[[], datetime] | None = None)` con: `create(operator_id) -> str` (ritorna il token grezzo, salva solo l'hash); `lookup(token) -> int | None` (ritorna `operator_id` se valida — non scaduta/idle/revocata — e aggiorna `last_seen_at`; altrimenti None); `revoke(token) -> None`; `revoke_all_for_operator(operator_id) -> None`. Nessun commit interno.
  - `sessions.hash_token(token: str) -> str` (SHA-256).

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/auth/test_sessions.py`:
```python
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from bussola.auth.accounts import AccountRepository
from bussola.auth.rbac import Role
from bussola.auth.sessions import SessionStore, hash_token

pytestmark = pytest.mark.usefixtures("db")


def _make_operator(conn: psycopg.Connection) -> int:
    op = AccountRepository(conn).create(
        username="u", display_name="U", role=Role.OPERATOR, password_hash="h", created_by="admin"
    )
    conn.commit()
    return op.id


def test_create_returns_raw_token_stored_only_as_hash(app_conn: psycopg.Connection):
    oid = _make_operator(app_conn)
    store = SessionStore(app_conn)
    token = store.create(oid)
    app_conn.commit()
    assert token and len(token) > 20
    with app_conn.cursor() as cur:
        cur.execute("SELECT token_hash FROM auth.session")
        stored = cur.fetchone()[0]
    assert stored == hash_token(token)
    assert stored != token


def test_lookup_valid_returns_operator(app_conn: psycopg.Connection):
    oid = _make_operator(app_conn)
    store = SessionStore(app_conn)
    token = store.create(oid)
    app_conn.commit()
    assert store.lookup(token) == oid


def test_lookup_unknown_returns_none(app_conn: psycopg.Connection):
    assert SessionStore(app_conn).lookup("nope") is None


def test_expired_session_is_invalid(app_conn: psycopg.Connection):
    oid = _make_operator(app_conn)
    # a clock fixed in the past so the created session is already expired
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    store = SessionStore(app_conn, now=lambda: past)
    token = store.create(oid)
    app_conn.commit()
    # look it up with the real clock -> expired
    assert SessionStore(app_conn).lookup(token) is None


def test_revoke_and_revoke_all(app_conn: psycopg.Connection):
    oid = _make_operator(app_conn)
    store = SessionStore(app_conn)
    t1 = store.create(oid)
    t2 = store.create(oid)
    app_conn.commit()
    store.revoke(t1)
    app_conn.commit()
    assert store.lookup(t1) is None
    assert store.lookup(t2) == oid
    store.revoke_all_for_operator(oid)
    app_conn.commit()
    assert store.lookup(t2) is None
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/auth/config.py`:
```python
"""Auth tunables, from environment with safe defaults (§3)."""

from __future__ import annotations

import os

from bussola.env import load_project_dotenv

load_project_dotenv()

SESSION_TTL_SECONDS = int(os.environ.get("BUSSOLA_SESSION_TTL_SECONDS", "43200"))  # 12h
SESSION_IDLE_SECONDS = int(os.environ.get("BUSSOLA_SESSION_IDLE_SECONDS", "1800"))  # 30m
MAX_FAILED_ATTEMPTS = int(os.environ.get("BUSSOLA_MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_SECONDS = int(os.environ.get("BUSSOLA_LOCKOUT_SECONDS", "900"))  # 15m
```

File `backend/src/bussola/auth/sessions.py`:
```python
"""Server-side sessions. Only the SHA-256 of the opaque token is stored, so a
DB leak cannot hand out live sessions. No internal commit (caller owns the tx)."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import psycopg

from bussola.auth import config


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionStore:
    def __init__(
        self, conn: psycopg.Connection, *, now: Callable[[], datetime] | None = None
    ) -> None:
        self._conn = conn
        self._now = now or _utcnow

    def create(self, operator_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = self._now()
        expires_at = now + timedelta(seconds=config.SESSION_TTL_SECONDS)
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO auth.session (token_hash, operator_id, created_at, expires_at, last_seen_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (hash_token(token), operator_id, now, expires_at, now),
            )
        return token

    def lookup(self, token: str) -> int | None:
        now = self._now()
        idle_cutoff = now - timedelta(seconds=config.SESSION_IDLE_SECONDS)
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, operator_id FROM auth.session "
                "WHERE token_hash = %s AND revoked_at IS NULL "
                "AND expires_at > %s AND last_seen_at > %s",
                (hash_token(token), now, idle_cutoff),
            )
            row = cur.fetchone()
            if row is None:
                return None
            session_id, operator_id = row
            cur.execute(
                "UPDATE auth.session SET last_seen_at = %s WHERE id = %s", (now, session_id)
            )
        return int(operator_id)

    def revoke(self, token: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.session SET revoked_at = %s WHERE token_hash = %s AND revoked_at IS NULL",
                (self._now(), hash_token(token)),
            )

    def revoke_all_for_operator(self, operator_id: int) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.session SET revoked_at = %s WHERE operator_id = %s AND revoked_at IS NULL",
                (self._now(), operator_id),
            )
```

> Nota sul test dell'idle: `test_expired_session_is_invalid` copre la scadenza assoluta (clock passato alla creazione). L'idle-timeout è coperto implicitamente dalla stessa clausola `last_seen_at > idle_cutoff`; un test dedicato all'idle è opzionale (creare con clock passato di > idle ma < ttl). Non indebolire la query.

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/auth/sessions.py backend/src/bussola/auth/config.py backend/tests/auth/test_sessions.py
git commit -m "feat(auth): SessionStore server-side (token solo-hash, scadenza/idle/revoca)"
```

---

### Task 6: `service.py` — autenticazione (login/logout/authenticate/change-password)

**Files:**
- Create: `backend/src/bussola/auth/service.py`
- Test: `backend/tests/auth/test_service_login.py`

**Interfaces:**
- Consumes: `AccountRepository`, `SessionStore`, `passwords`, `auth_audit`, `config`, `models`, `errors`.
- Produces:
  - `@dataclass LoginResult(token: str, operator: Operator, must_change_password: bool)`.
  - `AuthService(conn)` con: `login(username, password) -> LoginResult` (solleva `InvalidCredentials` su qualsiasi fallimento, generico; gestisce lockout, dummy-verify, azzeramento fallimenti, audit; **commit** a fine operazione riuscita); `authenticate(token) -> Operator | None`; `logout(token) -> None`; `change_password(operator_id, old, new) -> None`.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/auth/test_service_login.py`:
```python
import psycopg
import pytest

from bussola.auth import passwords
from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import InvalidCredentials
from bussola.auth.rbac import Role
from bussola.auth.service import AuthService
from bussola.auth import config

pytestmark = pytest.mark.usefixtures("db")


def _seed(conn: psycopg.Connection, *, pw: str = "correct-horse", must_change: bool = False) -> None:
    AccountRepository(conn).create(
        username="alice", display_name="Alice", role=Role.OPERATOR,
        password_hash=passwords.hash_password(pw), created_by="admin",
        must_change_password=must_change,
    )
    conn.commit()


def test_login_success_returns_token_and_operator(app_conn: psycopg.Connection):
    _seed(app_conn)
    result = AuthService(app_conn).login("alice", "correct-horse")
    assert result.token
    assert result.operator.username == "alice"
    assert AuthService(app_conn).authenticate(result.token).username == "alice"


def test_wrong_password_raises_generic(app_conn: psycopg.Connection):
    _seed(app_conn)
    with pytest.raises(InvalidCredentials):
        AuthService(app_conn).login("alice", "nope")


def test_unknown_user_raises_same_generic(app_conn: psycopg.Connection):
    with pytest.raises(InvalidCredentials):
        AuthService(app_conn).login("ghost", "whatever")


def test_lockout_after_repeated_failures(app_conn: psycopg.Connection):
    _seed(app_conn)
    svc = AuthService(app_conn)
    for _ in range(config.MAX_FAILED_ATTEMPTS):
        with pytest.raises(InvalidCredentials):
            svc.login("alice", "nope")
    # now locked: even the RIGHT password is refused during the lockout window
    with pytest.raises(InvalidCredentials):
        svc.login("alice", "correct-horse")


def test_login_success_is_audited(app_conn: psycopg.Connection):
    _seed(app_conn)
    AuthService(app_conn).login("alice", "correct-horse")
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor = cur.fetchone()
    assert action == "login_succeeded"
    assert actor == "alice"


def test_logout_revokes_session(app_conn: psycopg.Connection):
    _seed(app_conn)
    svc = AuthService(app_conn)
    token = svc.login("alice", "correct-horse").token
    svc.logout(token)
    assert svc.authenticate(token) is None


def test_change_password_updates_and_clears_must_change(app_conn: psycopg.Connection):
    _seed(app_conn, must_change=True)
    svc = AuthService(app_conn)
    rec = AccountRepository(app_conn).get_by_username("alice")
    svc.change_password(rec.id, "correct-horse", "brand-new-pw")
    token = svc.login("alice", "brand-new-pw").token
    assert svc.authenticate(token).must_change_password is False
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/auth/service.py`:
```python
"""AuthService: login, session auth, logout, self password change. Every login
outcome is audited; account state and audit commit in ONE transaction. Login
failures are generic (no user-enumeration) with timing equalized via dummy-verify."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg

from bussola.auth import auth_audit, config, passwords
from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import InvalidCredentials
from bussola.auth.models import Operator, OperatorRecord
from bussola.auth.sessions import SessionStore


@dataclass(frozen=True)
class LoginResult:
    token: str
    operator: Operator
    must_change_password: bool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn
        self._accounts = AccountRepository(conn)
        self._sessions = SessionStore(conn)

    def _fail(self, actor: str | None) -> None:
        auth_audit.record_auth_event(self._conn, action=auth_audit.LOGIN_FAILED, actor=actor)
        self._conn.commit()
        raise InvalidCredentials()

    def login(self, username: str, password: str) -> LoginResult:
        rec = self._accounts.get_by_username(username)
        now = _utcnow()
        if rec is None or not rec.is_active:
            passwords.dummy_verify()
            self._fail(username)
        assert rec is not None
        if rec.locked_until is not None and rec.locked_until > now:
            passwords.dummy_verify()
            self._fail(username)
        if not passwords.verify_password(rec.password_hash, password):
            attempts = rec.failed_attempts + 1
            locked_until = (
                now + timedelta(seconds=config.LOCKOUT_SECONDS)
                if attempts >= config.MAX_FAILED_ATTEMPTS
                else rec.locked_until
            )
            self._accounts.record_failed_attempt(rec.id, attempts, locked_until)
            self._fail(username)
        # success
        self._accounts.clear_failures(rec.id)
        token = self._sessions.create(rec.id)
        auth_audit.record_auth_event(
            self._conn, action=auth_audit.LOGIN_SUCCEEDED, actor=rec.username
        )
        self._conn.commit()
        return LoginResult(
            token=token,
            operator=_operator_from_record(rec),
            must_change_password=rec.must_change_password,
        )

    def authenticate(self, token: str) -> Operator | None:
        operator_id = self._sessions.lookup(token)
        if operator_id is None:
            self._conn.commit()  # persist last_seen_at update (no-op if none)
            return None
        rec = self._accounts.get_by_id(operator_id)
        self._conn.commit()
        if rec is None or not rec.is_active:
            return None
        return _operator_from_record(rec)

    def logout(self, token: str) -> None:
        self._sessions.revoke(token)
        auth_audit.record_auth_event(self._conn, action=auth_audit.LOGOUT, actor=None)
        self._conn.commit()

    def change_password(self, operator_id: int, old_password: str, new_password: str) -> None:
        rec = self._accounts.get_by_id(operator_id)
        if rec is None or not passwords.verify_password(rec.password_hash, old_password):
            raise InvalidCredentials()
        self._accounts.set_password(
            operator_id, passwords.hash_password(new_password), must_change=False
        )
        self._sessions.revoke_all_for_operator(operator_id)
        auth_audit.record_auth_event(
            self._conn, action=auth_audit.PASSWORD_CHANGED, actor=rec.username
        )
        self._conn.commit()


def _operator_from_record(rec: OperatorRecord) -> Operator:
    return Operator(
        id=rec.id,
        username=rec.username,
        display_name=rec.display_name,
        role=rec.role,
        is_active=rec.is_active,
        must_change_password=rec.must_change_password,
    )
```

> Nota: `change_password` revoca tutte le sessioni dell'operatore (cambio credenziali → riautenticazione). Se il chiamante HTTP vuole tenere viva la sessione corrente lo gestirà il router (fuori scope qui).

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/auth/service.py backend/tests/auth/test_service_login.py
git commit -m "feat(auth): AuthService login/logout/authenticate/change-password (lockout, no-enumeration, audit)"
```

---

### Task 7: `service.py` — gestione account (create/disable/enable/reset)

**Files:**
- Modify: `backend/src/bussola/auth/service.py` (aggiunge i metodi admin)
- Test: `backend/tests/auth/test_service_accounts.py`

**Interfaces:**
- Produces (su `AuthService`): `create_operator(*, actor, username, display_name, role) -> tuple[Operator, str]` (ritorna l'operatore + password temporanea generata, `must_change_password=True`); `disable_operator(*, actor, operator_id) -> None` (revoca tutte le sessioni); `enable_operator(*, actor, operator_id) -> None`; `reset_password(*, actor, operator_id) -> str` (ritorna nuova password temporanea, revoca sessioni). Tutti auditati e atomici; sollevano `OperatorNotFound` dove serve.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/auth/test_service_accounts.py`:
```python
import psycopg
import pytest

from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import OperatorNotFound
from bussola.auth.rbac import Role
from bussola.auth.service import AuthService

pytestmark = pytest.mark.usefixtures("db")


def test_create_operator_returns_temp_password_and_forces_change(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, temp = svc.create_operator(
        actor="admin", username="newop", display_name="New Op", role=Role.OPERATOR
    )
    assert op.username == "newop" and op.must_change_password is True
    assert temp and len(temp) >= 8
    # the temp password actually works
    assert svc.login("newop", temp).operator.username == "newop"


def test_create_is_audited_with_whitelisted_details(app_conn: psycopg.Connection):
    AuthService(app_conn).create_operator(
        actor="admin", username="op2", display_name="Op Two", role=Role.SUPERVISOR
    )
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor, details FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor, details = cur.fetchone()
    assert action == "operator_created" and actor == "admin"
    assert details["target_operator"] == "op2" and details["role"] == "supervisor"


def test_disable_revokes_sessions_immediately(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, temp = svc.create_operator(actor="admin", username="todisable", display_name="X", role=Role.OPERATOR)
    token = svc.login("todisable", temp).token
    assert svc.authenticate(token) is not None
    svc.disable_operator(actor="admin", operator_id=op.id)
    assert svc.authenticate(token) is None  # session dead + account inactive


def test_reset_password_issues_new_temp_and_revokes(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, temp = svc.create_operator(actor="admin", username="toreset", display_name="X", role=Role.OPERATOR)
    token = svc.login("toreset", temp).token
    new_temp = svc.reset_password(actor="admin", operator_id=op.id)
    assert new_temp != temp
    assert svc.authenticate(token) is None  # old sessions revoked
    assert svc.login("toreset", new_temp).operator.username == "toreset"


def test_operations_on_missing_operator_raise(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    with pytest.raises(OperatorNotFound):
        svc.disable_operator(actor="admin", operator_id=999999)
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare** — aggiungere a `service.py`:

In cima, aggiungere gli import:
```python
import secrets

from bussola.auth.errors import OperatorNotFound
from bussola.auth.rbac import Role
```
E i metodi in `AuthService`:
```python
    def create_operator(
        self, *, actor: str, username: str, display_name: str, role: Role
    ) -> tuple[Operator, str]:
        temp_password = secrets.token_urlsafe(9)  # >= 12 chars
        operator = self._accounts.create(
            username=username,
            display_name=display_name,
            role=role,
            password_hash=passwords.hash_password(temp_password),
            created_by=actor,
            must_change_password=True,
        )
        auth_audit.record_auth_event(
            self._conn,
            action=auth_audit.OPERATOR_CREATED,
            actor=actor,
            target_operator=username,
            role=role.value,
        )
        self._conn.commit()
        return operator, temp_password

    def disable_operator(self, *, actor: str, operator_id: int) -> None:
        rec = self._require(operator_id)
        self._accounts.set_active(operator_id, False, by=actor)
        self._sessions.revoke_all_for_operator(operator_id)
        auth_audit.record_auth_event(
            self._conn,
            action=auth_audit.OPERATOR_DISABLED,
            actor=actor,
            target_operator=rec.username,
        )
        self._conn.commit()

    def enable_operator(self, *, actor: str, operator_id: int) -> None:
        rec = self._require(operator_id)
        self._accounts.set_active(operator_id, True, by=actor)
        auth_audit.record_auth_event(
            self._conn,
            action=auth_audit.OPERATOR_ENABLED,
            actor=actor,
            target_operator=rec.username,
        )
        self._conn.commit()

    def reset_password(self, *, actor: str, operator_id: int) -> str:
        rec = self._require(operator_id)
        temp_password = secrets.token_urlsafe(9)
        self._accounts.set_password(
            operator_id, passwords.hash_password(temp_password), must_change=True
        )
        self._sessions.revoke_all_for_operator(operator_id)
        auth_audit.record_auth_event(
            self._conn,
            action=auth_audit.OPERATOR_PASSWORD_RESET,
            actor=actor,
            target_operator=rec.username,
        )
        self._conn.commit()
        return temp_password

    def _require(self, operator_id: int) -> OperatorRecord:
        rec = self._accounts.get_by_id(operator_id)
        if rec is None:
            raise OperatorNotFound(str(operator_id))
        return rec
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS. Rieseguire Task 6: `backend/.venv/bin/pytest backend/tests/auth -q`.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/auth/service.py backend/tests/auth/test_service_accounts.py
git commit -m "feat(auth): gestione account (create/disable/enable/reset) atomica e auditata"
```

---

### Task 8: Layer HTTP — `api/app.py`, `api/deps.py`, `api/errors.py`

**Files:**
- Modify: `backend/pyproject.toml` (aggiunge `fastapi`, `uvicorn`)
- Create: `backend/src/bussola/api/__init__.py`, `app.py`, `deps.py`, `errors.py`
- Test: `backend/tests/api/__init__.py`, `backend/tests/api/test_deps.py`

**Interfaces:**
- Produces:
  - `create_app() -> FastAPI` (registra router auth+operators e gli error handler).
  - `deps.get_conn() -> Iterator[psycopg.Connection]` (connessione `bussola_app`, chiusa a fine richiesta).
  - `deps.current_operator(...)` → `Operator` da header `Authorization: Bearer <token>` (401 se assente/invalida).
  - `deps.require_permission(permission)` → dependency factory (403 se il ruolo non ha il permesso).
  - `errors`: mapping `InvalidCredentials`→401, `PermissionDenied`→403, `UsernameExists`→409, `OperatorNotFound`→404.

- [ ] **Step 1: Aggiungere le dipendenze**

In `pyproject.toml` `dependencies`: aggiungere `"fastapi>=0.115,<0.116",` e `"uvicorn>=0.30,<0.35",`. Installare: `backend/.venv/bin/pip install -e "backend[dev]"`.

- [ ] **Step 2: Scrivere il test (fallisce)**

File `backend/tests/api/__init__.py`: (vuoto)

File `backend/tests/api/test_deps.py`:
```python
import psycopg
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from bussola.api import deps
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission, Role
from bussola.auth.service import AuthService

pytestmark = pytest.mark.usefixtures("db")


def _client(app_conn: psycopg.Connection) -> TestClient:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(op: Operator = Depends(deps.current_operator)) -> dict:
        return {"username": op.username}

    @app.get("/admin-only")
    def admin_only(
        op: Operator = Depends(deps.require_permission(Permission.MANAGE_OPERATORS)),
    ) -> dict:
        return {"ok": True}

    # Route the request-scoped DB dependency to the test connection WITHOUT
    # closing it (get_conn would otherwise close the shared conn after req #1).
    def _test_conn():
        yield app_conn

    app.dependency_overrides[deps.get_conn] = _test_conn
    return TestClient(app)


def test_no_token_is_401(app_conn):
    assert _client(app_conn).get("/whoami").status_code == 401


def test_valid_session_reaches_route(app_conn):
    _op, temp = AuthService(app_conn).create_operator(
        actor="admin", username="alice", display_name="A", role=Role.OPERATOR
    )
    session = AuthService(app_conn).login("alice", temp).token
    r = _client(app_conn).get("/whoami", headers={"Authorization": f"Bearer {session}"})
    assert r.status_code == 200 and r.json()["username"] == "alice"


def test_permission_denied_is_403(app_conn):
    _op, temp = AuthService(app_conn).create_operator(
        actor="admin", username="op", display_name="O", role=Role.OPERATOR
    )
    session = AuthService(app_conn).login("op", temp).token
    r = _client(app_conn).get("/admin-only", headers={"Authorization": f"Bearer {session}"})
    assert r.status_code == 403
```

> Nota: i test iniettano la connessione di test via `app.dependency_overrides[deps.get_conn]`, che fa `yield app_conn` **senza chiuderla** (il `get_conn` reale la chiuderebbe a fine richiesta, rompendo la connessione condivisa del test). Così ogni richiesta HTTP usa la STESSA connessione/transazione del test contro `bussola_test`. Non serve toccare `deps._open_conn`.

- [ ] **Step 3: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 4: Implementare**

File `backend/src/bussola/api/__init__.py`: (vuoto)

File `backend/src/bussola/api/deps.py`:
```python
"""FastAPI dependencies: per-request DB connection, current operator from the
bearer token, and permission gating."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import psycopg
from fastapi import Depends, Header, HTTPException, status

from bussola.auth.models import Operator
from bussola.auth.rbac import Permission, has_permission
from bussola.auth.service import AuthService
from bussola.data import config


def _open_conn() -> psycopg.Connection:
    return psycopg.connect(config.dsn("app"))


def get_conn() -> Iterator[psycopg.Connection]:
    conn = _open_conn()
    try:
        yield conn
    finally:
        conn.close()


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return authorization[len("Bearer ") :]


def raw_bearer(authorization: str | None = Header(default=None)) -> str:
    """The raw bearer token (for logout, which must revoke the exact token)."""
    return _bearer_token(authorization)


def current_operator(
    authorization: str | None = Header(default=None),
    conn: psycopg.Connection = Depends(get_conn),
) -> Operator:
    token = _bearer_token(authorization)
    operator = AuthService(conn).authenticate(token)
    if operator is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired session")
    return operator


def require_permission(permission: Permission) -> Callable[..., Operator]:
    def _dep(operator: Operator = Depends(current_operator)) -> Operator:
        if not has_permission(operator.role, permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient privileges")
        return operator

    return _dep
```

File `backend/src/bussola/api/errors.py`:
```python
"""Map auth domain errors to HTTP responses (no internal detail leakage)."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bussola.auth.errors import (
    InvalidCredentials,
    OperatorNotFound,
    PermissionDenied,
    UsernameExists,
)

_STATUS = {
    InvalidCredentials: status.HTTP_401_UNAUTHORIZED,
    PermissionDenied: status.HTTP_403_FORBIDDEN,
    OperatorNotFound: status.HTTP_404_NOT_FOUND,
    UsernameExists: status.HTTP_409_CONFLICT,
}

_MESSAGE = {
    InvalidCredentials: "credenziali non valide",
    PermissionDenied: "privilegi insufficienti",
    OperatorNotFound: "operatore inesistente",
    UsernameExists: "username già esistente",
}


def register_error_handlers(app: FastAPI) -> None:
    for exc_type, code in _STATUS.items():

        async def _handler(_request: Request, exc: Exception, _code: int = code) -> JSONResponse:
            message = _MESSAGE.get(type(exc), "errore")
            return JSONResponse(status_code=_code, content={"detail": message})

        app.add_exception_handler(exc_type, _handler)
```

File `backend/src/bussola/api/app.py`:
```python
"""FastAPI application factory (auth-only surface for this subsystem)."""

from __future__ import annotations

from fastapi import FastAPI

from bussola.api.errors import register_error_handlers
from bussola.api.routers import auth as auth_router
from bussola.api.routers import operators as operators_router


def create_app() -> FastAPI:
    app = FastAPI(title="Bussola — Auth API")
    register_error_handlers(app)
    app.include_router(auth_router.router)
    app.include_router(operators_router.router)
    return app
```

> Nota: `app.py` importa i router dei Task 9/10; se implementi Task 8 da solo, crea temporaneamente `routers/__init__.py` vuoto e stub dei due router, oppure implementa 8→9→10 di seguito prima di eseguire `create_app()`. Il test del Task 8 (`test_deps.py`) NON usa `create_app()` — costruisce un'app-sonda locale — quindi passa senza i router.

- [ ] **Step 5: Eseguire (devono passare)** — `backend/.venv/bin/pytest backend/tests/api/test_deps.py -q` → PASS.

- [ ] **Step 6: Committare**
```bash
git add backend/pyproject.toml backend/src/bussola/api/__init__.py backend/src/bussola/api/deps.py backend/src/bussola/api/errors.py backend/src/bussola/api/app.py backend/tests/api/__init__.py backend/tests/api/test_deps.py
git commit -m "feat(api): app FastAPI + dipendenze (conn, current_operator, require_permission) + error handler"
```

---

### Task 9: Router `routers/auth.py` (login/logout/me/change-password)

**Files:**
- Create: `backend/src/bussola/api/routers/__init__.py`, `backend/src/bussola/api/routers/auth.py`
- Test: `backend/tests/api/conftest.py`, `backend/tests/api/test_auth_router.py`

**Interfaces:**
- Consumes: `AuthService`, `deps`, `models` (LoginRequest, ChangePasswordRequest, Operator).
- Produces: router con `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password`.

- [ ] **Step 1: Scrivere conftest + test (falliscono)**

File `backend/tests/api/conftest.py`:
```python
from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from bussola.api import deps
from bussola.api.app import create_app
from bussola.auth.rbac import Role
from bussola.auth.service import AuthService


@pytest.fixture
def client(app_conn: psycopg.Connection) -> TestClient:
    # Route every request's DB connection to the test connection WITHOUT closing
    # it (the real get_conn would close the shared conn after the first request).
    app = create_app()

    def _test_conn():
        yield app_conn

    app.dependency_overrides[deps.get_conn] = _test_conn
    return TestClient(app)


@pytest.fixture
def make_operator(app_conn: psycopg.Connection):
    def _make(username: str, role: Role = Role.OPERATOR) -> tuple[str, str]:
        _op, temp = AuthService(app_conn).create_operator(
            actor="bootstrap", username=username, display_name=username.title(), role=role
        )
        return username, temp

    return _make
```

File `backend/tests/api/test_auth_router.py`:
```python
import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def test_login_me_logout_flow(client, make_operator):
    username, temp = make_operator("alice", Role.OPERATOR)
    r = client.post("/auth/login", json={"username": username, "password": temp})
    assert r.status_code == 200
    token = r.json()["token"]
    assert r.json()["must_change_password"] is True

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["username"] == "alice"

    out = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert out.status_code == 204
    # session now dead
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_login_wrong_password_is_401_generic(client, make_operator):
    make_operator("bob")
    r = client.post("/auth/login", json={"username": "bob", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "credenziali non valide"


def test_change_password_then_login_with_new(client, make_operator):
    username, temp = make_operator("carl")
    token = client.post("/auth/login", json={"username": username, "password": temp}).json()["token"]
    r = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": temp, "new_password": "a-brand-new-pw"},
    )
    assert r.status_code == 204
    assert client.post("/auth/login", json={"username": username, "password": "a-brand-new-pw"}).status_code == 200
```

- [ ] **Step 2: Eseguire (devono fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/api/routers/__init__.py`: (vuoto)

File `backend/src/bussola/api/routers/auth.py`:
```python
"""Authentication endpoints: login, logout, whoami, self password change."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from bussola.api.deps import current_operator, get_conn, raw_bearer
from bussola.auth.models import ChangePasswordRequest, LoginRequest, Operator
from bussola.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginResponse(BaseModel):
    token: str
    operator: Operator
    must_change_password: bool


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, conn: psycopg.Connection = Depends(get_conn)) -> LoginResponse:
    result = AuthService(conn).login(body.username, body.password)
    return LoginResponse(
        token=result.token,
        operator=result.operator,
        must_change_password=result.must_change_password,
    )


@router.get("/me", response_model=Operator)
def me(operator: Operator = Depends(current_operator)) -> Operator:
    return operator


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: str = Depends(raw_bearer),
    conn: psycopg.Connection = Depends(get_conn),
    operator: Operator = Depends(current_operator),
) -> Response:
    AuthService(conn).logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    conn: psycopg.Connection = Depends(get_conn),
    operator: Operator = Depends(current_operator),
) -> Response:
    AuthService(conn).change_password(operator.id, body.old_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

> Il logout usa `raw_bearer` (definito in `deps.py` al Task 8) per revocare esattamente il token presentato, e `current_operator` per garantire che la sessione fosse valida.

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/api/routers/__init__.py backend/src/bussola/api/routers/auth.py backend/tests/api/conftest.py backend/tests/api/test_auth_router.py
git commit -m "feat(api): router auth (login/me/logout/change-password)"
```

---

### Task 10: Router `routers/operators.py` (gestione account, admin-only)

**Files:**
- Create: `backend/src/bussola/api/routers/operators.py`
- Test: `backend/tests/api/test_operators_router.py`

**Interfaces:**
- Consumes: `AuthService`, `deps.require_permission(Permission.MANAGE_OPERATORS)`, `models`.
- Produces: `POST /operators` (create → 201 con temp password), `GET /operators` (list), `POST /operators/{id}/disable|enable|reset-password`.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/api/test_operators_router.py`:
```python
import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password}).json()["token"]


def test_admin_creates_operator(client, make_operator):
    admin_user, admin_temp = make_operator("admin1", Role.ADMIN)
    admin_token = _login(client, admin_user, admin_temp)
    r = client.post(
        "/operators",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "newbie", "display_name": "New Bie", "role": "operator"},
    )
    assert r.status_code == 201
    assert r.json()["operator"]["username"] == "newbie"
    assert r.json()["temp_password"]


def test_non_admin_cannot_manage_operators(client, make_operator):
    op_user, op_temp = make_operator("plainop", Role.OPERATOR)
    token = _login(client, op_user, op_temp)
    r = client.post(
        "/operators",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "x", "display_name": "X", "role": "operator"},
    )
    assert r.status_code == 403


def test_disable_kills_target_sessions(client, make_operator):
    admin_user, admin_temp = make_operator("admin2", Role.ADMIN)
    admin_token = _login(client, admin_user, admin_temp)
    created = client.post(
        "/operators",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "victim", "display_name": "V", "role": "operator"},
    ).json()
    victim_token = _login(client, "victim", created["temp_password"])
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {victim_token}"}).status_code == 200
    oid = created["operator"]["id"]
    client.post(f"/operators/{oid}/disable", headers={"Authorization": f"Bearer {admin_token}"})
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {victim_token}"}).status_code == 401
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/api/routers/operators.py`:
```python
"""Operator account management (Amministratore only)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import CreateOperatorRequest, Operator
from bussola.auth.rbac import Permission
from bussola.auth.service import AuthService

router = APIRouter(prefix="/operators", tags=["operators"])
_manage = require_permission(Permission.MANAGE_OPERATORS)


class CreatedOperator(BaseModel):
    operator: Operator
    temp_password: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatedOperator)
def create_operator(
    body: CreateOperatorRequest,
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> CreatedOperator:
    operator, temp = AuthService(conn).create_operator(
        actor=admin.username,
        username=body.username,
        display_name=body.display_name,
        role=body.role,
    )
    return CreatedOperator(operator=operator, temp_password=temp)


@router.get("", response_model=list[Operator])
def list_operators(
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[Operator]:
    from bussola.auth.accounts import AccountRepository

    return AccountRepository(conn).list_all()


@router.post("/{operator_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_operator(
    operator_id: int,
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> Response:
    AuthService(conn).disable_operator(actor=admin.username, operator_id=operator_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{operator_id}/enable", status_code=status.HTTP_204_NO_CONTENT)
def enable_operator(
    operator_id: int,
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> Response:
    AuthService(conn).enable_operator(actor=admin.username, operator_id=operator_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ResetResponse(BaseModel):
    temp_password: str


@router.post("/{operator_id}/reset-password", response_model=ResetResponse)
def reset_password(
    operator_id: int,
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> ResetResponse:
    temp = AuthService(conn).reset_password(actor=admin.username, operator_id=operator_id)
    return ResetResponse(temp_password=temp)
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Committare**
```bash
git add backend/src/bussola/api/routers/operators.py backend/tests/api/test_operators_router.py
git commit -m "feat(api): router operators (gestione account admin-only)"
```

---

### Task 11: Bootstrap del primo Amministratore (`bootstrap.py`)

**Files:**
- Create: `backend/src/bussola/auth/bootstrap.py`
- Test: `backend/tests/auth/test_bootstrap.py`

**Interfaces:**
- Produces: `bootstrap.create_first_admin(conn, *, username, display_name, password) -> Operator` — crea il primo admin **solo se non esiste già alcun admin**; solleva `errors.AuthError` altrimenti. Auditato (`actor="bootstrap"`). CLI `python -m bussola.auth.bootstrap` legge username/display/password da variabili d'ambiente (`BUSSOLA_ADMIN_USERNAME`, `BUSSOLA_ADMIN_DISPLAY_NAME`, `BUSSOLA_ADMIN_PASSWORD`) e apre una connessione owner.

- [ ] **Step 1: Scrivere il test (fallisce)**

File `backend/tests/auth/test_bootstrap.py`:
```python
import psycopg
import pytest

from bussola.auth import bootstrap
from bussola.auth.errors import AuthError

pytestmark = pytest.mark.usefixtures("db")


def test_creates_first_admin(app_conn: psycopg.Connection):
    admin = bootstrap.create_first_admin(
        app_conn, username="root", display_name="Root", password="a-strong-pw"
    )
    assert admin.role.value == "admin"
    assert admin.must_change_password is True


def test_refuses_when_an_admin_already_exists(app_conn: psycopg.Connection):
    bootstrap.create_first_admin(app_conn, username="root", display_name="Root", password="pw12345678")
    with pytest.raises(AuthError):
        bootstrap.create_first_admin(app_conn, username="root2", display_name="Root2", password="pw12345678")
    app_conn.rollback()
```

- [ ] **Step 2: Eseguire (deve fallire)** — FAIL.

- [ ] **Step 3: Implementare**

File `backend/src/bussola/auth/bootstrap.py`:
```python
"""Create the very first Amministratore. No default credentials are shipped:
the deployer runs `python -m bussola.auth.bootstrap` with the account details
in the environment. Refuses if an admin already exists."""

from __future__ import annotations

import os
import sys

import psycopg

from bussola.auth import auth_audit, passwords
from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import AuthError
from bussola.auth.models import Operator
from bussola.auth.rbac import Role
from bussola.data import config


def _admin_exists(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM auth.operator WHERE role = %s LIMIT 1", (Role.ADMIN.value,))
        return cur.fetchone() is not None


def create_first_admin(
    conn: psycopg.Connection, *, username: str, display_name: str, password: str
) -> Operator:
    if _admin_exists(conn):
        raise AuthError("an administrator already exists; bootstrap refused")
    operator = AccountRepository(conn).create(
        username=username,
        display_name=display_name,
        role=Role.ADMIN,
        password_hash=passwords.hash_password(password),
        created_by="bootstrap",
        must_change_password=True,
    )
    auth_audit.record_auth_event(
        conn,
        action=auth_audit.OPERATOR_CREATED,
        actor="bootstrap",
        target_operator=username,
        role=Role.ADMIN.value,
    )
    conn.commit()
    return operator


def main() -> int:
    username = os.environ.get("BUSSOLA_ADMIN_USERNAME")
    display_name = os.environ.get("BUSSOLA_ADMIN_DISPLAY_NAME", username or "")
    password = os.environ.get("BUSSOLA_ADMIN_PASSWORD")
    if not username or not password:
        print(
            "Set BUSSOLA_ADMIN_USERNAME and BUSSOLA_ADMIN_PASSWORD in the environment.",
            file=sys.stderr,
        )
        return 2
    with psycopg.connect(config.dsn("app")) as conn:
        try:
            operator = create_first_admin(
                conn, username=username, display_name=display_name, password=password
            )
        except AuthError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"Created administrator '{operator.username}' (must change password at first login).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Eseguire (devono passare)** — PASS.

- [ ] **Step 5: Gate completo + commit**
```bash
backend/.venv/bin/pytest backend/tests -q
backend/.venv/bin/ruff check backend/ && backend/.venv/bin/ruff format --check backend/src/bussola/auth backend/src/bussola/api backend/tests/auth backend/tests/api
backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/src
git add backend/src/bussola/auth/bootstrap.py backend/tests/auth/test_bootstrap.py
git commit -m "feat(auth): bootstrap CLI del primo amministratore (rifiuta se esiste)"
```

---

## Note di chiusura (scelte di ambito)

- **Endpoint di business del portale** (richieste di lavoro, matching, profili, metriche, export): Sottosistema «Portale operatore».
- **Cookie httpOnly + CSRF, kiosk**: S7 (frontend). Qui il contratto è bearer token.
- **MFA**, **reset self-service via email**: Fase 2.
- **`uvicorn`** è aggiunto per il serving reale; i test usano `TestClient` (non serve avviare il server). Un test end-to-end del server avviato è opzionale/manuale.

## Verifica di copertura (spec → task)

| Requisito (spec/§) | Task |
|---|---|
| Hashing argon2id (§3.3) | 1 |
| RBAC ruoli/permessi (§3.5, §6) | 1, 8 |
| Schema DB auth + privilegi (§5) | 2 |
| Account provisioning/lifecycle (§3.4, §7) | 3, 7, 10 |
| Audit vincolato + atomico (§3.8, §7.3) | 4, 6, 7 |
| Sessioni server-side + revoca (§3.2) | 5, 6, 7 |
| Login: no-enumeration, lockout (§3.7) | 6 |
| Layer HTTP + auth su ogni endpoint (§3.1) | 8, 9, 10 |
| Bootstrap senza credenziali di default (§3.9) | 11 |
| TDD, dati sintetici, codice inglese (§9/§11) | Tutti |
