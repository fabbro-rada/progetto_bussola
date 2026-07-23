"""FastAPI application factory (auth-only surface for this subsystem)."""

from __future__ import annotations

from fastapi import FastAPI

from bussola.api.errors import register_error_handlers
from bussola.api.routers import auth as auth_router
from bussola.api.routers import job_requests as job_requests_router
from bussola.api.routers import matching as matching_router
from bussola.api.routers import operators as operators_router
from bussola.api.routers import profiles as profiles_router


def create_app() -> FastAPI:
    app = FastAPI(title="Bussola — Auth API")
    register_error_handlers(app)
    app.include_router(auth_router.router)
    app.include_router(operators_router.router)
    app.include_router(job_requests_router.router)
    app.include_router(matching_router.router)
    app.include_router(profiles_router.router)
    return app
