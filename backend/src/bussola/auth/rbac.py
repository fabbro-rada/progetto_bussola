"""Role-based access control. Roles map to a fixed set of permissions (§6).

This subsystem ENFORCES only MANAGE_OPERATORS (+ self-service, which needs no
permission, just a valid session). The business permissions are DECLARED here
so the RBAC engine is complete; later subsystems (portal) enforce them.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    AUDITOR = "auditor"


class Permission(str, Enum):
    MANAGE_OPERATORS = "manage_operators"  # enforced now
    # declared; enforced by later subsystems
    READ_PROFILES = "read_profiles"
    MANAGE_JOB_REQUESTS = "manage_job_requests"
    RUN_MATCHING = "run_matching"
    EXPORT_DATA = "export_data"
    VIEW_METRICS = "view_metrics"
    VIEW_OPERATOR_ACTIVITY = "view_operator_activity"
    READ_AUDIT = "read_audit"
    CONFIGURE_SYSTEM = "configure_system"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OPERATOR: frozenset(
        {
            Permission.READ_PROFILES,
            Permission.MANAGE_JOB_REQUESTS,
            Permission.RUN_MATCHING,
            Permission.EXPORT_DATA,
        }
    ),
    Role.SUPERVISOR: frozenset({Permission.VIEW_METRICS, Permission.VIEW_OPERATOR_ACTIVITY}),
    Role.ADMIN: frozenset({Permission.MANAGE_OPERATORS, Permission.CONFIGURE_SYSTEM}),
    Role.AUDITOR: frozenset({Permission.READ_AUDIT}),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
