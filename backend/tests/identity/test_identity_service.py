from __future__ import annotations

import psycopg
import pytest

from bussola.data.profiles import create_empty_profile
from bussola.identity.errors import MatricolaAlreadyLinked
from bussola.identity.service import IdentityService

pytestmark = pytest.mark.usefixtures("db")


def test_link_then_resolve_both_directions_and_audit(app_conn: psycopg.Connection):
    audited: list[dict[str, object]] = []
    p = create_empty_profile(app_conn)
    app_conn.commit()
    svc = IdentityService(app_conn, audit=lambda **kw: audited.append(kw))
    svc.link(p, "MAT-001", actor="op1")
    app_conn.commit()
    assert svc.resolve(p, actor="sup1") == "MAT-001"
    assert svc.resolve_matricola("MAT-001", actor="sup1") == p
    actions = [a["action"] for a in audited]
    assert actions.count("identity_link_created") == 1
    assert actions.count("identity_resolved") == 2


def test_duplicate_matricola_is_rejected(app_conn: psycopg.Connection):
    p1 = create_empty_profile(app_conn)
    p2 = create_empty_profile(app_conn)
    app_conn.commit()
    svc = IdentityService(app_conn)
    svc.link(p1, "MAT-DUP", actor="op1")
    app_conn.commit()
    with pytest.raises(MatricolaAlreadyLinked):
        svc.link(p2, "MAT-DUP", actor="op1")


def test_resolve_unknown_returns_none(app_conn: psycopg.Connection):
    svc = IdentityService(app_conn)
    assert svc.resolve("P-nope", actor="sup1") is None
    assert svc.resolve_matricola("MAT-nope", actor="sup1") is None
