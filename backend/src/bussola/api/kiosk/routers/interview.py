"""Person-facing interview endpoints (kiosk). Thin HTTP over the S4 Interview
state machine; the session registry owns the Interview and its DB connection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from bussola.api.kiosk.deps import REGISTRY, build_interview, require_kiosk
from bussola.interview.interview import Interview

router = APIRouter(prefix="/kiosk/interview", tags=["kiosk"], dependencies=[Depends(require_kiosk)])


class StartRequest(BaseModel):
    language: str = Field(min_length=2, max_length=5)


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
    step = interview.start()
    token = REGISTRY.create(interview, on_evict=on_evict)
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
