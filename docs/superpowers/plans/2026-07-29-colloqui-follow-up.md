# Colloqui di follow-up (Fase 2·A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Colloqui successivi che aggiornano un profilo esistente con l'esperienza lavorativa in corso, ri-collegando la persona al suo profilo pseudonimizzato tramite un token monouso emesso dall'operatore — senza che il sistema memorizzi mai persona↔pseudonimo (§5).

**Architecture:** L'operatore emette un **token di follow-up** (hash+TTL+monouso, `token→pseudonimo`) dal portale. La persona lo usa al kiosk: il motore colloquio S4 gira in **modalità follow-up** — carica il `WorkProfile` esistente, percorre sezioni ridotte (esperienza → competenze → aspirazioni), e aggiorna il profilo **in-place** con semantica **append/upgrade** (le esperienze si aggiungono, l'evidenza delle competenze sale). Volontario (§4); ogni azione auditata.

**Tech Stack:** Python 3.12 (FastAPI, Pydantic v2 `extra="forbid"`, psycopg3, Postgres); kiosk `frontend/` (React 18 + Vite + TS + react-i18next); portale `operator-portal/`.

## Global Constraints

- **§5 — nessuna mappa persona↔pseudonimo nel sistema.** La tabella token memorizza SOLO `token_hash`, `pseudonym_id`, timestamp — **nessuna colonna anagrafica/identità**. Il legame persona↔pseudonimo resta nel registro esterno (`data/pseudonym.py`: «that register lives outside the system»).
- **§5 — minimizzazione:** aggiornamento **in-place**, nessuna storicizzazione delle versioni. **§5 — confermato dalla persona:** i meccanismi S4 (riepilogo+conferma, chiarimento) restano.
- **§4 — volontarietà/non-coercizione:** il follow-up al kiosk si apre con consenso/recap; la persona può rifiutare senza conseguenze; «Ferma» sempre attivo.
- **Token:** `secrets.token_urlsafe`, in DB solo `sha256` (mirror `auth/sessions.py`), TTL breve, **monouso** (consumato al primo uso riuscito), `consume` **fail-closed** su token ignoto/scaduto/usato.
- **Append/upgrade (mai perdita di dati):** una nuova esperienza è **aggiunta** (le precedenti restano); una competenza già presente **non retrocede** di evidenza (si prende il grado più alto); le aspirazioni si aggiornano in unione. §5.
- **Additivo — primo colloquio invariato:** la modalità primo-colloquio (S4/S8/S9) resta **identica**; le sue suite restano verdi **senza modifiche alle asserzioni**. Se un'asserzione S4/S8 dovesse cambiare → STOP/BLOCKED.
- **RBAC:** `POST /followups` gated su nuovo `Permission.PROVISION_FOLLOWUP` (solo operatore); il server è l'autorità (403). Il kiosk resta dietro `X-Kiosk-Token`.
- **§2:** solo-lavoro; nessun punteggio/sorveglianza. **§11:** codice inglese; stringhe UI i18n. **§9:** TDD; solo dati sintetici; i test di token/§5 e volontarietà vengono per primi.
- **Gate backend:** `pytest -q && ruff check . && mypy src` (da `backend/`, `.venv`, DB up). **Gate kiosk:** `npm test && npm run typecheck && npm run lint && npm run build` (da `frontend/`). **Gate portale:** idem da `operator-portal/`.

---

## File Structure

**Backend** (`backend/src/bussola/`):
- `data/migrations/0008_followup.sql` (nuovo) — tabella `followup_token`.
- `followup/__init__.py`, `followup/service.py` (nuovi) — `FollowupTokenService` (issue/consume).
- `interview/session.py` (modifica) — supporto modalità follow-up (profilo esistente, sezioni ridotte, merge append/upgrade).
- `interview/interview.py` (modifica additiva) — `start_followup(pseudonym_id)` (o costruzione in modalità follow-up).
- `auth/rbac.py` (modifica) — `Permission.PROVISION_FOLLOWUP` → operatore.
- `api/routers/followups.py` (nuovo) — `POST /followups` (operatore).
- `api/kiosk/routers/interview.py` (modifica) — `POST /kiosk/interview/start-followup`.

**Kiosk** (`frontend/src/`): schermata inserimento token + consenso/recap follow-up + riuso flusso colloquio; `kioskClient.startFollowup(token)`; i18n.
**Portale** (`operator-portal/src/`): azione «Nuovo follow-up» nel dettaglio profilo (S13) → modale token una-tantum (pattern temp-password S14); `operatorClient.createFollowup(pseudonym)`.

---

## Task 1: Migrazione 0008 — `followup_token`

**Files:**
- Create: `backend/src/bussola/data/migrations/0008_followup.sql`
- Test: `backend/tests/data/test_migrations.py` (ADD un test; non modificare gli esistenti)

**Interfaces:**
- Produces: `followup_token(token_hash text PRIMARY KEY, pseudonym_id text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL, used_at timestamptz)`. Schema: scegli quello coerente con dove vivono i token (probabilmente un nuovo schema `followup` o lo schema `profiles`/un `interview` — **leggi `0004_auth.sql` e `0002_profiles.sql`** e usa la convenzione schema-per-file già in uso; GRANT `bussola_app` SELECT/INSERT/UPDATE; auditor NESSUN accesso).

- [ ] **Step 1: Test** (oggetti presenti + nessuna colonna anagrafica)

```python
def test_0008_adds_followup_token_without_identity_columns(owner_conn):  # use the real fixture name from this file
    from bussola.data.migrate import apply_migrations
    apply_migrations(owner_conn)
    with owner_conn.cursor() as cur:
        cur.execute("SELECT token_hash, pseudonym_id, expires_at, used_at FROM followup.followup_token WHERE false")
        cur.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='followup_token'")
        cols = {r[0] for r in cur.fetchall()}
        assert not cols & {"name", "surname", "person", "anagraphic", "identity", "cf"}  # §5: no identity
```

- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Scrivi `0008_followup.sql`** (DDL sopra; GRANT come i sibling; **nessuna** colonna identità).
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Commit** — `feat(followup): migration 0008 — followup_token (hash/TTL/single-use, no identity)`

---

## Task 2: `FollowupTokenService` — issue/consume

**Files:**
- Create: `backend/src/bussola/followup/__init__.py`, `backend/src/bussola/followup/service.py`
- Test: `backend/tests/followup/__init__.py`, `backend/tests/followup/test_token.py`

**Interfaces:**
- Consumes: la tabella 0008; il pattern hash di `auth/sessions.py` (`hash_token = sha256 hexdigest`, `secrets.token_urlsafe(32)`, `expires_at`).
- Produces:
  ```python
  class FollowupTokenService:
      def __init__(self, conn, *, ttl_seconds: int = 86400, audit: AuditFn | None = None) -> None: ...
      def issue(self, pseudonym_id: str, *, actor: str) -> str:  # returns cleartext token (shown once); stores hash+expiry; audit "followup_provisioned"
      def consume(self, token: str) -> str | None:  # returns pseudonym if valid+unexpired+unused (marks used, one txn); else None (fail-closed)
  ```

- [ ] **Step 1: Test (§5/§7.3 first)** — read `backend/tests/` for the DB fixture name and mirror `auth` token tests:

```python
def test_issue_then_consume_returns_pseudonym_once(db_conn):
    svc = FollowupTokenService(db_conn)
    tok = svc.issue("P-abc", actor="op1"); db_conn.commit()
    assert svc.consume(tok) == "P-abc"      # first use OK
    db_conn.commit()
    assert svc.consume(tok) is None          # single-use: second use rejected

def test_only_hash_stored_never_cleartext(db_conn):
    svc = FollowupTokenService(db_conn); tok = svc.issue("P-abc", actor="op1"); db_conn.commit()
    with db_conn.cursor() as cur:
        cur.execute("SELECT token_hash FROM followup.followup_token")
        stored = cur.fetchone()[0]
        assert stored != tok and len(stored) == 64  # sha256 hex, not the token

def test_expired_token_rejected(db_conn):
    svc = FollowupTokenService(db_conn, ttl_seconds=0)
    tok = svc.issue("P-abc", actor="op1"); db_conn.commit()
    assert svc.consume(tok) is None          # already expired

def test_unknown_token_rejected(db_conn):
    assert FollowupTokenService(db_conn).consume("nope") is None
```

- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa** `FollowupTokenService` — `issue`: `token = secrets.token_urlsafe(32)`, INSERT `(hash_token(token), pseudonym_id, now, now+ttl)`, audit `followup_provisioned` (target=pseudonym, no commit — caller commits); `consume`: SELECT by `token_hash` WHERE `used_at IS NULL AND expires_at > now`; if found, `UPDATE ... SET used_at=now WHERE token_hash=%s AND used_at IS NULL` (race-safe single-use), return pseudonym; else None. Reuse/duplicate `hash_token` from `auth/sessions.py` (import if public, else replicate the 1-liner).
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Gate** — `pytest tests/followup -q && ruff check . && mypy src`.
- [ ] **Step 6: Commit** — `feat(followup): FollowupTokenService (issue/consume, hashed, single-use, TTL)`

---

## Task 3: `PROVISION_FOLLOWUP` + `POST /followups`

**Files:**
- Modify: `backend/src/bussola/auth/rbac.py` (+`PROVISION_FOLLOWUP` → `Role.OPERATOR`)
- Create: `backend/src/bussola/api/routers/followups.py`; register in `api/app.py`
- Test: `backend/tests/api/test_followups_router.py`

**Interfaces:**
- Consumes: `FollowupTokenService.issue`, `require_permission`, `append_audit`, `get_conn`.
- Produces: `POST /followups {pseudonym_id: str}` → `{token: str}` (201), gated `require_permission(Permission.PROVISION_FOLLOWUP)`. Audit occurs in the service (`followup_provisioned`).

- [ ] **Step 1: Test** — mirror an existing operator-router test (e.g. `test_profiles_router.py`/`test_metrics_router.py`) for the role helpers:

```python
def test_provision_followup_requires_operator(client_as):
    assert client_as("supervisor").post("/followups", json={"pseudonym_id": "P-x"}).status_code == 403
    assert client_as("auditor").post("/followups", json={"pseudonym_id": "P-x"}).status_code == 403
    r = client_as("operator").post("/followups", json={"pseudonym_id": "P-x"})
    assert r.status_code == 201 and r.json()["token"]

def test_provision_is_audited(client_as, db_conn):
    client_as("operator").post("/followups", json={"pseudonym_id": "P-x"})
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log WHERE action='followup_provisioned'")
        assert cur.fetchone()[0] >= 1
```

- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa** — add `PROVISION_FOLLOWUP` to `Permission` and to `Role.OPERATOR`'s set in `ROLE_PERMISSIONS`; router calls `FollowupTokenService(conn, audit=...).issue(pseudonym_id, actor=operator.username)` + `conn.commit()`, returns `{token}`. Register router in `app.py`.
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Gate** — `pytest -q && ruff check . && mypy src`. (Existing RBAC tests: adding a permission to operator must not change their assertions — if a test asserts operator's EXACT permission set, extend that fixture/expectation carefully; if it would change a spec-of-record assertion, that's expected for a new permission — confirm it's only the operator-permission-set test, not a behavioral one.)
- [ ] **Step 6: Commit** — `feat(followup): PROVISION_FOLLOWUP permission + POST /followups (operator, audited)`

---

## Task 4: Modalità follow-up del motore colloquio (load + sezioni ridotte + append/upgrade)

**Files:**
- Modify: `backend/src/bussola/interview/session.py` (follow-up session: profilo esistente, sezioni ridotte, merge append/upgrade)
- Modify: `backend/src/bussola/interview/interview.py` (`ProfileStore` Protocol +`get`; `start_followup`)
- Test: `backend/tests/interview/test_followup_mode.py`

**Interfaces:**
- Consumes: `ProfileRepository.get(pseudonym) -> WorkProfile | None`, `.save(profile)`; `SECTIONS` (`interview/sections.py`); `EvidenceGrade` (read its ordering — «take the higher grade»).
- Produces:
  - `InterviewSession.for_followup(profile: WorkProfile, language: str) -> InterviewSession` (or a ctor flag): starts on the EXISTING `profile`, walks a REDUCED section order **`(experiences, skills, aspirations)`**, and its `merge(extracted)` does **append/upgrade** instead of overwrite.
  - `Interview.start_followup(pseudonym_id: str) -> Step`: `profile = self._repo.get(pseudonym_id)`; if None → `unavailable` (fail-closed); else `self._session = InterviewSession.for_followup(profile, language)`; returns first question. Reuses `submit()` unchanged (same confirm/clarification path).
- Append/upgrade `merge` semantics (§5, no data loss):
  - **experiences:** `profile.experiences = profile.experiences + extracted.experiences` (append; never replace).
  - **skills:** merge by `name`: existing skill kept but its `evidence` is raised to `max(existing, extracted)` per the `EvidenceGrade` order; a genuinely new skill is appended. **languages/digital_literacy** in the skills section: union languages by `language` (don't drop existing); update `digital_literacy` only if the follow-up provides one.
  - **aspirations:** union `fields_of_interest` and `desired_training` with existing (dedupe); don't wipe prior.

- [ ] **Step 1: Tests (append/upgrade + no-loss first)**

```python
def test_followup_appends_experience_and_upgrades_evidence(fake_engine_repo):
    # existing profile: 1 experience, skill "cucina" evidence=declared
    # follow-up extracts: 1 new experience, skill "cucina" evidence=demonstrated
    itv = Interview(..., repository=repo)         # mirror existing interview tests' construction
    itv.start_followup("P-x")
    # ... drive experiences section: confirm -> profile.experiences has BOTH (old+new)
    # ... drive skills section: "cucina" evidence is now demonstrated (upgraded, not duplicated)
    saved = repo.get("P-x")
    assert len(saved.experiences) == 2
    assert _evidence_of(saved, "cucina") == EvidenceGrade.DEMONSTRATED  # upgraded, single entry

def test_followup_never_downgrades_or_drops(fake_engine_repo):
    # follow-up extracts "cucina" as declared while it's already demonstrated -> stays demonstrated
    # and a prior experience/skill absent from the follow-up is preserved

def test_start_followup_unknown_pseudonym_is_unavailable(...):
    assert Interview(..., repo_returning_none).start_followup("P-none").kind == "unavailable"

def test_first_interview_mode_unchanged(...):
    # start() still create_new() + full SECTIONS; a smoke assertion that the base path is untouched
```
(Mirror the construction/fakes used by the existing `backend/tests/interview/` tests — reuse their fake LLM/scope/repo doubles. Add `get` to the fake ProfileStore.)

- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa** — add `get` to the `ProfileStore` Protocol; `InterviewSession.for_followup` (existing profile + reduced sections + append/upgrade merge); `Interview.start_followup`. Do NOT change `start()`/`_submit()` behavior for the base flow.
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Gate + base-flow invariance** — `pytest tests/interview -q && ruff check . && mypy src`. The existing S4 interview suites stay green **with assertions unchanged**.
- [ ] **Step 6: Commit** — `feat(followup): interview follow-up mode (load profile, reduced sections, append/upgrade)`

---

## Task 5: `POST /kiosk/interview/start-followup` (consume → sessione)

**Files:**
- Modify: `backend/src/bussola/api/kiosk/routers/interview.py` (+ start-followup endpoint); the kiosk session registry (`api/kiosk/session.py`) as the existing `start` does.
- Test: `backend/tests/api/kiosk/test_followup_start.py`

**Interfaces:**
- Consumes: `FollowupTokenService.consume(token) -> pseudonym | None`, `Interview.start_followup`, the kiosk session registry + `X-Kiosk-Token` dep (as the existing `/kiosk/interview/start`).
- Produces: `POST /kiosk/interview/start-followup {token}` → `{session_token, step}` (like `start`) on a valid token, or fail-closed (`unauthorized`/`unavailable`) on invalid/used/expired. `submit` reuses the existing endpoint (the session drives follow-up mode).

- [ ] **Step 1: Test** — mirror `tests/api/kiosk/` start tests:

```python
def test_start_followup_with_valid_token_updates_that_profile(kiosk_client, issued_token_for_P):
    r = kiosk_client.post("/kiosk/interview/start-followup",
                          headers=KIOSK_HEADER, json={"token": issued_token_for_P})
    assert r.status_code == 200 and r.json()["step"]["kind"] == "question"

def test_start_followup_invalid_token_fails_closed(kiosk_client):
    r = kiosk_client.post("/kiosk/interview/start-followup",
                          headers=KIOSK_HEADER, json={"token": "bad"})
    assert r.status_code in (401, 503)  # never a session; never leaks

def test_start_followup_requires_kiosk_token(kiosk_client):
    assert kiosk_client.post("/kiosk/interview/start-followup", json={"token": "x"}).status_code == 401
```

- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa** — endpoint behind the kiosk-token dep: `pseudonym = FollowupTokenService(conn).consume(token)`; if None → 401/503 (fail-closed, no session created); else create a kiosk session (as `start` does, owning its conn) whose `Interview.start_followup(pseudonym)` produces the first step; return `{session_token, step}`. Audit `followup_completed` fires at interview completion (in the Interview or the submit path) — wire it consistently with the existing `interview_section_confirmed` audit.
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Gate** — `pytest -q && ruff check . && mypy src`. Existing kiosk `start`/`submit` tests unchanged.
- [ ] **Step 6: Commit** — `feat(followup): POST /kiosk/interview/start-followup (consume token -> follow-up session)`

---

## Task 6: Kiosk — inserimento token + consenso follow-up + flusso

**Files:**
- Create/modify (`frontend/src/`): a follow-up entry screen (token input) + a follow-up consent/recap screen; wire into the state machine; `api/kioskClient.ts` (+`startFollowup(token)`); `i18n/locales/*` (5 lingue) for the new strings.
- Test: Vitest/RTL specs mirroring existing screen tests.

**Interfaces:**
- Consumes: `POST /kiosk/interview/start-followup`.
- Produces: a kiosk path — enter follow-up token → **follow-up consent/recap** («vuoi aggiornare il tuo profilo con l'esperienza recente?», con rifiuto) → the existing interview flow (Question/Summary/Clarification/Completed). «Ferma» always mounted.

- [ ] **Step 1: Test** — fake client: valid token → reaches the first question after consent; **decline** on the follow-up consent → returns to a neutral state (no session), no profile touched (client-side: no submit); invalid token → gentle unavailable/text (fail-closed). Mirror `LanguagePicker`/`Consent` test harness.
- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa** — `kioskClient.startFollowup(token)` fail-closed (mirror `startInterview`); the token-entry + follow-up-consent screens; state-machine wiring reusing existing screens for the interview turns; strings in ALL FIVE locale files (§8/§11), RTL-safe. **Voluntariness (§4):** decline is a first-class, consequence-free path; «Ferma» resets.
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Gate kiosk** — `npm test && npm run typecheck && npm run lint && npm run build`. Existing kiosk screen tests unchanged.
- [ ] **Step 6: Commit** — `feat(kiosk): follow-up entry (token) + follow-up consent + flow`

---

## Task 7: Portale — «Nuovo follow-up» nel dettaglio profilo (token una-tantum)

**Files:**
- Modify (`operator-portal/src/`): `screens/profiles/ProfileDetail.tsx` (S13) + a one-time-token modal (reuse the S14 `TempPasswordModal` pattern); `api/operatorClient.ts` (+`createFollowup(pseudonym)`); `i18n/locales/it.ts`.
- Test: mirror `TempPasswordModal`/`ProfileDetail` tests.

**Interfaces:**
- Consumes: `POST /followups {pseudonym_id}` → `{token}` (Task 3).
- Produces: in the profile detail, a **«Nuovo follow-up»** action → calls `createFollowup(pseudonym)` → shows the returned token **once** in a modal (copy affordance like the temp-password; never re-persisted client-side), with a note to hand it to the person.

- [ ] **Step 1: Test** — operator client fake returns a token; the action opens the modal showing the token; the token is shown once (closing clears it). Mirror `TempPasswordModal.test.tsx`.
- [ ] **Step 2: Esegui — deve fallire.**
- [ ] **Step 3: Implementa** — `operatorClient.createFollowup(pseudonym)` fail-closed; the «Nuovo follow-up» button in `ProfileDetail`; the one-time-token modal (reuse `TempPasswordModal` pattern — `useId`/`aria-labelledby`, «Copiato» only on success, cleared on close); i18n strings.
- [ ] **Step 4: Esegui — deve passare.**
- [ ] **Step 5: Gate portale** — `npm test && npm run typecheck && npm run lint && npm run build`. Existing profile/modal tests unchanged.
- [ ] **Step 6: Commit** — `feat(operator-portal): "Nuovo follow-up" action -> one-time token in profile detail`

---

## Self-Review (autore)

- **Copertura spec:** §3.1 token → Task 1–2; §3.6 RBAC/emissione → Task 3; §3.3 motore follow-up (load+ridotte+append/upgrade) → Task 4; ri-collegamento kiosk → Task 5; §3.5 volontarietà/kiosk → Task 6; provisioning portale → Task 7. §3.4 append/upgrade in-place (no storico) → Task 4 (merge) + Task 5 (audit `followup_completed`).
- **§5:** tabella token senza colonne identità (Task 1 test); token→pseudonimo only; nessuno storico versioni (Task 4 update in-place).
- **§4:** rifiuto del follow-up = percorso di prima classe (Task 6 test); «Ferma» sempre attivo.
- **Additivo:** Task 4/5/6 non toccano il primo colloquio; regola STOP se una suite S4/S8/S9 cambia asserzione.
- **Type consistency:** `FollowupTokenService.issue/consume`, `ProfileStore.get`, `InterviewSession.for_followup`, `Interview.start_followup`, `Permission.PROVISION_FOLLOWUP` coerenti tra i task; token clear-text mostrato una volta (Task 2/3/7), hash in DB (Task 1/2).
- **Append/upgrade:** semantica esplicita (esperienze append, competenze max-evidence, aspirazioni union) in Task 4, con test no-loss/no-downgrade.

---

## Execution Handoff

Piano salvato in `docs/superpowers/plans/2026-07-29-colloqui-follow-up.md`. Due opzioni:

**1. Subagent-Driven (consigliata)** — implementer fresco per task + review a due stadi + review finale opus.

**2. Inline Execution** — a checkpoint in questa sessione.

Quale approccio?
