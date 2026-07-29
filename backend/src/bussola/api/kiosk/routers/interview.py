"""Person-facing interview endpoints (kiosk). Thin HTTP over the S4 Interview
state machine; the session registry owns the Interview and its DB connection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from bussola.api.kiosk.deps import (
    REGISTRY,
    build_followup_interview,
    build_interview,
    open_kiosk_conn,
    require_kiosk,
)
from bussola.followup.service import FollowupTokenService
from bussola.interview.interview import Interview

router = APIRouter(prefix="/kiosk/interview", tags=["kiosk"], dependencies=[Depends(require_kiosk)])

# Follow-up tokens don't carry a language selection (a work profile has no
# language field — §5), so the follow-up interview defaults the same way
# `ProfileRepository`'s own `language` parameter does elsewhere.
_FOLLOWUP_LANGUAGE = "it"


class StartRequest(BaseModel):
    language: str = Field(min_length=2, max_length=5)


class StartFollowupRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class SubmitRequest(BaseModel):
    session_token: str
    answer: str = Field(min_length=1, max_length=4000)


class StepOut(BaseModel):
    kind: str
    text: str


class StartResponse(BaseModel):
    session_token: str
    step: StepOut


class SubmitResponse(BaseModel):
    step: StepOut


@router.post("/start", response_model=StartResponse)
def start(body: StartRequest) -> StartResponse:
    interview, on_evict = build_interview(body.language)
    try:
        step = interview.start()
    except Exception:
        on_evict()
        raise
    token = REGISTRY.create(interview, on_evict=on_evict)
    return StartResponse(session_token=token, step=StepOut(kind=step.kind, text=step.text))


@router.post("/start-followup", response_model=StartResponse)
def start_followup(body: StartFollowupRequest) -> StartResponse:
    conn = open_kiosk_conn()
    pseudonym = FollowupTokenService(conn).consume(body.token)
    if pseudonym is None:
        # Fail-closed: unknown/used/expired token -> no session, no leak
        # about which of the three it was.
        conn.close()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    # LOAD-BEARING (single-use durability): `consume()` marks the token used
    # via an UPDATE but does NOT commit (the caller owns the transaction,
    # like every other service in this codebase — see auth.service.authenticate
    # for the same commit-right-after idiom). Commit HERE, immediately, and
    # BEFORE any subsequent step that could raise. If anything below raised
    # first, the connection would close without committing, the `used_at`
    # mark would roll back, and the token would become reusable — defeating
    # single-use.
    conn.commit()
    interview = build_followup_interview(conn, _FOLLOWUP_LANGUAGE)
    try:
        step = interview.start_followup(pseudonym)
    except Exception:
        conn.close()
        raise
    token = REGISTRY.create(interview, on_evict=conn.close)
    return StartResponse(session_token=token, step=StepOut(kind=step.kind, text=step.text))


@router.post("/submit", response_model=SubmitResponse)
def submit(body: SubmitRequest) -> SubmitResponse:
    interview = REGISTRY.get(body.session_token)
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    assert isinstance(interview, Interview)
    step = interview.submit(body.answer)
    if step.kind == "completed":
        REGISTRY.discard(body.session_token)
    return SubmitResponse(step=StepOut(kind=step.kind, text=step.text))
