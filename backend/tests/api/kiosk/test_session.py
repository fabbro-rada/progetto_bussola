from datetime import datetime, timedelta, timezone

from bussola.api.kiosk.session import InterviewRegistry


def test_create_get_distinct_tokens():
    reg = InterviewRegistry(ttl_seconds=1800)
    t1 = reg.create("INTERVIEW_A")
    t2 = reg.create("INTERVIEW_B")
    assert t1 != t2
    assert reg.get(t1) == "INTERVIEW_A"
    assert reg.get(t2) == "INTERVIEW_B"


def test_get_unknown_returns_none():
    assert InterviewRegistry(ttl_seconds=1800).get("nope") is None


def test_discard_calls_on_evict_and_removes():
    reg = InterviewRegistry(ttl_seconds=1800)
    closed = []
    token = reg.create("X", on_evict=lambda: closed.append(True))
    reg.discard(token)
    assert reg.get(token) is None
    assert closed == [True]


def test_expired_session_is_swept_and_evicted():
    clock = {"now": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    reg = InterviewRegistry(ttl_seconds=60, now=lambda: clock["now"])
    closed = []
    token = reg.create("X", on_evict=lambda: closed.append(True))
    clock["now"] += timedelta(seconds=61)  # past TTL since last_seen
    assert reg.get(token) is None  # swept
    assert closed == [True]
