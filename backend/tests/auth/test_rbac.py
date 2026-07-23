from bussola.auth.rbac import Permission, Role, has_permission


def test_admin_can_manage_operators_others_cannot():
    assert has_permission(Role.ADMIN, Permission.MANAGE_OPERATORS) is True
    for role in (Role.OPERATOR, Role.SUPERVISOR, Role.AUDITOR):
        assert has_permission(role, Permission.MANAGE_OPERATORS) is False


def test_operator_business_permissions():
    assert has_permission(Role.OPERATOR, Permission.READ_PROFILES) is True
    assert has_permission(Role.OPERATOR, Permission.RUN_MATCHING) is True
    assert has_permission(Role.OPERATOR, Permission.READ_AUDIT) is False


def test_auditor_only_reads_audit():
    assert has_permission(Role.AUDITOR, Permission.READ_AUDIT) is True
    assert has_permission(Role.AUDITOR, Permission.READ_PROFILES) is False


def test_supervisor_sees_metrics_not_profiles():
    assert has_permission(Role.SUPERVISOR, Permission.VIEW_METRICS) is True
    assert has_permission(Role.SUPERVISOR, Permission.READ_PROFILES) is False
