import type { Role } from '../types'

export interface NavItem {
  path: string
  labelKey: string
  built?: boolean
}

// UX-only nav skeleton (§6). The server remains the authority (403). Every
// section is currently built; the `built` flag stays so a future not-yet-built
// section can render as a disabled placeholder instead of a real link.
export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  operator: [
    { path: '/new-interview', labelKey: 'nav.newInterview', built: true },
    { path: '/job-requests', labelKey: 'nav.jobRequests', built: true },
    { path: '/profiles', labelKey: 'nav.profiles', built: true },
    { path: '/export', labelKey: 'nav.export', built: true },
  ],
  supervisor: [
    { path: '/metrics', labelKey: 'nav.metrics', built: true },
    { path: '/report', labelKey: 'nav.report', built: true },
    { path: '/activity', labelKey: 'nav.activity', built: true },
    { path: '/export-approvals', labelKey: 'nav.exportApprovals', built: true },
    { path: '/deanonymize', labelKey: 'nav.deanonymize', built: true },
  ],
  admin: [
    { path: '/operators', labelKey: 'nav.operators', built: true },
    { path: '/config', labelKey: 'nav.config', built: true },
  ],
  auditor: [{ path: '/audit', labelKey: 'nav.audit', built: true }],
}
