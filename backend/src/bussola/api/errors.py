"""Map auth domain errors to HTTP responses (no internal detail leakage)."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bussola.auth.errors import (
    InvalidCredentials,
    OperatorNotFound,
    PermissionDenied,
    UsernameExists,
)
from bussola.llm.client import LlmUnavailable
from bussola.matching.errors import JobRequestNotFound

_STATUS = {
    InvalidCredentials: status.HTTP_401_UNAUTHORIZED,
    PermissionDenied: status.HTTP_403_FORBIDDEN,
    OperatorNotFound: status.HTTP_404_NOT_FOUND,
    JobRequestNotFound: status.HTTP_404_NOT_FOUND,
    UsernameExists: status.HTTP_409_CONFLICT,
    LlmUnavailable: status.HTTP_503_SERVICE_UNAVAILABLE,
}

_MESSAGE: dict[type[Exception], str] = {
    InvalidCredentials: "credenziali non valide",
    PermissionDenied: "privilegi insufficienti",
    OperatorNotFound: "operatore inesistente",
    JobRequestNotFound: "richiesta di lavoro inesistente",
    UsernameExists: "username già esistente",
    LlmUnavailable: "servizio di matching temporaneamente non disponibile",
}


def register_error_handlers(app: FastAPI) -> None:
    for exc_type, code in _STATUS.items():

        async def _handler(_request: Request, exc: Exception, _code: int = code) -> JSONResponse:
            message = _MESSAGE.get(type(exc), "errore")
            return JSONResponse(status_code=_code, content={"detail": message})

        app.add_exception_handler(exc_type, _handler)
