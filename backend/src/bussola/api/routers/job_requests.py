"""Job request endpoints (operator role)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.matching.models import JobRequest, JobRequestCreate
from bussola.matching.requests import JobRequestRepository

router = APIRouter(prefix="/job-requests", tags=["job-requests"])
_manage = require_permission(Permission.MANAGE_JOB_REQUESTS)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=JobRequest)
def create_job_request(
    body: JobRequestCreate,
    operator: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> JobRequest:
    jr = JobRequestRepository(conn).create(body, created_by=operator.username)
    conn.commit()
    return jr


@router.get("", response_model=list[JobRequest])
def list_job_requests(
    operator: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[JobRequest]:
    return JobRequestRepository(conn).list_all()


@router.get("/{job_id}", response_model=JobRequest)
def get_job_request(
    job_id: int,
    operator: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> JobRequest:
    jr = JobRequestRepository(conn).get(job_id)
    if jr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job request not found")
    return jr
