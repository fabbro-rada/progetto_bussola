"""System status / configuration endpoint (admin role, read-only). §2/§9: no
secrets, no security controls exposed."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.system.service import SystemConfig, compute_system_config

router = APIRouter(prefix="/system-config", tags=["system"])
_configure = require_permission(Permission.CONFIGURE_SYSTEM)


@router.get("", response_model=SystemConfig)
def get_system_config(
    operator: Operator = Depends(_configure),
    conn: psycopg.Connection = Depends(get_conn),
) -> SystemConfig:
    config = compute_system_config()
    append_audit(conn, action="system_config_viewed", actor=operator.username, target_pseudonym=None)
    return config
