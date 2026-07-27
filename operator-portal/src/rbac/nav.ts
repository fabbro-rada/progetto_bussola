import type { Role } from '../types'

export interface NavItem {
  path: string
  labelKey: string
  built?: boolean
}

// UX-only nav skeleton (§6). The server remains the authority (403). Section
// pages arrive in later sub-projects; until then, items render as disabled
// placeholders. Once a section's screen exists, mark it `built` to render a
// real link.
export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  operator: [
    { path: '/job-requests', labelKey: 'nav.jobRequests', built: true },
    { path: '/profiles', labelKey: 'nav.profiles', built: true },
    { path: '/export', labelKey: 'nav.export', built: true },
  ],
  supervisor: [
    { path: '/metrics', labelKey: 'nav.metrics', built: true },
    { path: '/activity', labelKey: 'nav.activity' },
    { path: '/export-approvals', labelKey: 'nav.exportApprovals', built: true },
  ],
  admin: [
    { path: '/operators', labelKey: 'nav.operators', built: true },
    { path: '/config', labelKey: 'nav.config' },
  ],
  auditor: [{ path: '/audit', labelKey: 'nav.audit' }],
}
