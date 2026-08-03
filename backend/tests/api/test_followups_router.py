import psycopg
import pytest
from psycopg.types.json import Jsonb

from bussola.auth.rbac import Role
from bussola.data.profiles import create_empty_profile
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _content_profile(app_conn: psycopg.Connection) -> str:
    """A pseudonym with a real, content-bearing profile — the only thing a
    follow-up can be provisioned for now (§5)."""
    pseudonym = create_empty_profile(app_conn)
    prof = WorkProfile(
        pseudonym_id=pseudonym,
        skills=[Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
    )
    with app_conn.cursor() as cur:
        cur.execute(
            "UPDATE profiles.work_profile SET profile = %s WHERE pseudonym_id = %s",
            (Jsonb(prof.model_dump(mode="json")), pseudonym),
        )
    app_conn.commit()
    return pseudonym


def test_provision_followup_requires_operator(client, make_operator, app_conn):
    pseudonym = _content_profile(app_conn)
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    sup_tok = _login(client, sup, sup_temp)
    r = client.post("/followups", json={"pseudonym_id": pseudonym}, headers=_auth(sup_tok))
    assert r.status_code == 403

    aud, aud_temp = make_operator("aud1", Role.AUDITOR)
    aud_tok = _login(client, aud, aud_temp)
    r = client.post("/followups", json={"pseudonym_id": pseudonym}, headers=_auth(aud_tok))
    assert r.status_code == 403

    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    r = client.post("/followups", json={"pseudonym_id": pseudonym}, headers=_auth(op_tok))
    assert r.status_code == 201
    assert r.json()["token"]


def test_provision_followup_rejects_missing_or_empty_profile(client, make_operator, app_conn):
    # The bug from real use: a token minted for a pseudonym with no (content)
    # profile makes the person hit the "unavailable" dead-end at start-followup.
    # Now the operator is refused up front (404).
    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    # (a) no profile row at all
    r = client.post("/followups", json={"pseudonym_id": "P-nope"}, headers=_auth(op_tok))
    assert r.status_code == 404
    # (b) a provisioned-but-empty profile (interview never ran)
    empty = create_empty_profile(app_conn)
    app_conn.commit()
    r = client.post("/followups", json={"pseudonym_id": empty}, headers=_auth(op_tok))
    assert r.status_code == 404
    # nothing minted
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM followup.followup_token")
        assert cur.fetchone()[0] == 0


def test_provision_is_audited(client, make_operator, owner_conn: psycopg.Connection, app_conn):
    # Use an INDEPENDENT connection (not the `app_conn` the handler writes
    # through) so this assertion is genuinely commit-sensitive: `client`
    # overrides `get_conn` to hand the handler `app_conn` itself, so reading
    # back via `app_conn` would see the handler's writes via read-your-own-
    # writes even if the handler never committed. `owner_conn` is a separate
    # session/connection, so it only sees rows once the handler's `conn.commit()`
    # has actually happened — if that commit were ever dropped, these SELECTs
    # would find nothing and the test would fail.
    pseudonym = _content_profile(app_conn)
    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    r = client.post("/followups", json={"pseudonym_id": pseudonym}, headers=_auth(op_tok))
    assert r.status_code == 201

    with owner_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym FROM audit.audit_log "
            "WHERE action = 'followup_provisioned' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == op
    assert row[1] == pseudonym

    with owner_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM followup.followup_token")
        assert cur.fetchone()[0] == 1
    owner_conn.rollback()
