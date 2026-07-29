"""POST /kiosk/interview/start-followup: consume the one-time follow-up
token and start a kiosk follow-up session on the person's EXISTING profile.

Runs against the real test DB (unlike test_interview_endpoints.py's fully
faked doubles) because `FollowupTokenService.consume` needs a real, atomic
UPDATE ... RETURNING to prove single-use durability: the load-bearing
property under test is that the endpoint commits the `used_at` mark right
after a successful consume, so a second call with the SAME token is rejected
even though the first call's `Interview.start_followup` runs (and could, in
principle, raise) afterwards. `open_kiosk_conn` is monkeypatched to point at
`bussola_test` the same way `test_kiosk_live.py` overrides `build_interview`."""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from bussola.api.app import create_app
from bussola.api.kiosk import config
from bussola.api.kiosk.deps import REGISTRY
from bussola.api.kiosk.routers import interview as interview_router
from bussola.data import config as db_config
from bussola.data.profiles import ProfileRepository
from bussola.followup.service import FollowupTokenService

pytestmark = pytest.mark.usefixtures("db")

TOKEN = "secret-kiosk"


class _NoRedact:
    def redact(self, text: str, language: str = "it") -> str:
        return text


def _open_test_conn() -> psycopg.Connection:
    return psycopg.connect(db_config.dsn("app", dbname="bussola_test"))


@pytest.fixture
def kiosk_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)
    monkeypatch.setattr(interview_router, "open_kiosk_conn", _open_test_conn)
    return TestClient(create_app())


def _h() -> dict[str, str]:
    return {"X-Kiosk-Token": TOKEN}


@pytest.fixture
def existing_pseudonym(app_conn: psycopg.Connection) -> str:
    # A follow-up token only ever exists for a pseudonym that already has a
    # profile (provisioned by an operator, Task 3); `create_new` commits
    # internally, matching how `ProfileRepository` is used elsewhere.
    return ProfileRepository(app_conn, _NoRedact()).create_new()


@pytest.fixture
def issued_token_for_p(app_conn: psycopg.Connection, existing_pseudonym: str) -> str:
    token = FollowupTokenService(app_conn).issue(existing_pseudonym, actor="op-test")
    app_conn.commit()
    return token


def test_start_followup_with_valid_token_starts_that_profiles_session(
    kiosk_client: TestClient, issued_token_for_p: str
) -> None:
    r = kiosk_client.post(
        "/kiosk/interview/start-followup", headers=_h(), json={"token": issued_token_for_p}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["step"]["kind"] == "question"
    assert body["session_token"]
    REGISTRY.discard(body["session_token"])  # close the real conn this session opened


def test_start_followup_invalid_token_fails_closed(kiosk_client: TestClient) -> None:
    r = kiosk_client.post(
        "/kiosk/interview/start-followup", headers=_h(), json={"token": "not-a-real-token"}
    )
    assert r.status_code in (401, 503)  # never a session; never leaks why


def test_start_followup_expired_token_fails_closed(
    kiosk_client: TestClient, app_conn: psycopg.Connection, existing_pseudonym: str
) -> None:
    expired = FollowupTokenService(app_conn, ttl_seconds=0).issue(
        existing_pseudonym, actor="op-test"
    )
    app_conn.commit()
    r = kiosk_client.post("/kiosk/interview/start-followup", headers=_h(), json={"token": expired})
    assert r.status_code in (401, 503)


def test_start_followup_requires_kiosk_token(kiosk_client: TestClient) -> None:
    r = kiosk_client.post("/kiosk/interview/start-followup", json={"token": "x"})
    assert r.status_code == 401


def test_start_followup_second_call_with_same_token_is_rejected(
    kiosk_client: TestClient, issued_token_for_p: str
) -> None:
    # Single-use durability (the load-bearing property): the FIRST call must
    # commit the `used_at` mark immediately, before `Interview.start_followup`
    # runs. This assertion only holds if that commit actually happened -- if
    # the endpoint forgot to commit, the connection close at the end of the
    # first request would roll the mark back and the second call would
    # succeed again.
    first = kiosk_client.post(
        "/kiosk/interview/start-followup", headers=_h(), json={"token": issued_token_for_p}
    )
    assert first.status_code == 200
    REGISTRY.discard(first.json()["session_token"])

    second = kiosk_client.post(
        "/kiosk/interview/start-followup", headers=_h(), json={"token": issued_token_for_p}
    )
    assert second.status_code in (401, 503)
