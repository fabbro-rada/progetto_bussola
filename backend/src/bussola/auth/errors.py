"""Auth domain errors (mapped to HTTP status codes at the API boundary)."""

from __future__ import annotations


class AuthError(Exception):
    """Base for auth failures."""


class InvalidCredentials(AuthError):
    """Generic login failure — never reveals whether the username exists."""


class UsernameExists(AuthError):
    pass


class OperatorNotFound(AuthError):
    pass


class PermissionDenied(AuthError):
    pass
