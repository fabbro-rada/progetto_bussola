"""Export workflow errors (mapped to HTTP status by the router)."""

from __future__ import annotations


class ExportError(Exception):
    """Base class for export workflow errors."""


class ExportNotFound(ExportError):
    """No such request, or not owned by the caller."""


class ExportNotPending(ExportError):
    """The request has already been decided."""


class ExportNotApproved(ExportError):
    """The request is not in the approved state (cannot download)."""
