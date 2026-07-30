"""FastAPI application factory (auth-only surface for this subsystem)."""

from __future__ import annotations

from fastapi import FastAPI

from bussola.api.errors import register_error_handlers
from bussola.api.kiosk.routers import interview as kiosk_interview_router
from bussola.api.kiosk.routers import voice as kiosk_voice_router
from bussola.api.routers import activity as activity_router
from bussola.api.routers import audit as audit_router
from bussola.api.routers import auth as auth_router
from bussola.api.routers import exports as exports_router
from bussola.api.routers import followups as followups_router
from bussola.api.routers import health as health_router
from bussola.api.routers import job_requests as job_requests_router
from bussola.api.routers import matching as matching_router
from bussola.api.routers import metrics as metrics_router
from bussola.api.routers import operators as operators_router
from bussola.api.routers import profiles as profiles_router
from bussola.api.routers import report as report_router
from bussola.api.routers import system as system_router


def create_app() -> FastAPI:
    app = FastAPI(title="Bussola — Auth API")
    register_error_handlers(app)
    app.include_router(health_router.router)
    app.include_router(auth_router.router)
    app.include_router(activity_router.router)
    app.include_router(audit_router.router)
    app.include_router(operators_router.router)
    app.include_router(job_requests_router.router)
    app.include_router(matching_router.router)
    app.include_router(profiles_router.router)
    app.include_router(exports_router.router)
    app.include_router(metrics_router.router)
    app.include_router(report_router.router)
    app.include_router(system_router.router)
    app.include_router(followups_router.router)
    app.include_router(kiosk_interview_router.router)
    app.include_router(kiosk_voice_router.router)
    return app
