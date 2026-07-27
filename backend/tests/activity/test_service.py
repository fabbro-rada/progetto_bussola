import psycopg
import pytest

from bussola.activity.service import compute_operator_activity
from bussola.data.audit import append_audit

pytestmark = pytest.mark.usefixtures("db")


def test_no_events_gives_empty_list(app_conn: psycopg.Connection):
    assert compute_operator_activity(app_conn) == []


def test_counts_work_actions_per_actor_and_excludes_non_work(app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-2")
    append_audit(app_conn, action="matching_run", actor="op1")
    append_audit(app_conn, action="profiles_searched", actor="op2")
    # non-work / other-role / kiosk events must NOT create rows or counts
    append_audit(app_conn, action="login_succeeded", actor="op1")
    append_audit(app_conn, action="operator_created", actor="admin")
    append_audit(app_conn, action="interview_section_confirmed", actor="kiosk", target_pseudonym="P-1")

    rows = {a.actor: a for a in compute_operator_activity(app_conn)}
    assert set(rows) == {"op1", "op2"}  # admin/kiosk absent (no work actions)
    assert rows["op1"].profiles_viewed == 2
    assert rows["op1"].matchings_run == 1
    assert rows["op1"].profiles_searched == 0
    assert rows["op1"].exports_requested == 0 and rows["op1"].exports_downloaded == 0
    assert rows["op2"].profiles_searched == 1
    assert rows["op1"].last_active is not None


def test_context_exports_counted(app_conn: psycopg.Connection):
    append_audit(app_conn, action="export_requested", actor="op3")
    append_audit(app_conn, action="export_downloaded", actor="op3")
    a = compute_operator_activity(app_conn)[0]
    assert a.actor == "op3"
    assert a.exports_requested == 1 and a.exports_downloaded == 1
