import type { Role } from '../types'

export interface NavItem {
  path: string
  labelKey: string
}

// UX-only nav skeleton (§6). The server remains the authority (403). Section
// pages arrive in later sub-projects; here the items render as disabled
// placeholders.
export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  operator: [
    { path: '/job-requests', labelKey: 'nav.jobRequests' },
    { path: '/profiles', labelKey: 'nav.profiles' },
    { path: '/export', labelKey: 'nav.export' },
  ],
  supervisor: [
    { path: '/metrics', labelKey: 'nav.metrics' },
    { path: '/activity', labelKey: 'nav.activity' },
  ],
  admin: [
    { path: '/operators', labelKey: 'nav.operators' },
    { path: '/config', labelKey: 'nav.config' },
  ],
  auditor: [{ path: '/audit', labelKey: 'nav.audit' }],
}
