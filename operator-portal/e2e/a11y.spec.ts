import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type Route } from '@playwright/test'

// End-to-end a11y audit of the operator portal in real Chromium. Complements
// the jsdom component audit (src/a11y.audit.test.tsx): here axe checks
// color-contrast (real layout + CSS) — the one thing jsdom cannot do. The API
// is mocked per-test; no backend needed. The portal is Italian-only (no RTL
// dimension, unlike the kiosk).
//
// AUTH: the portal bootstraps via AuthProvider calling GET /auth/me with a
// Bearer token read from sessionStorage (src/auth/session.ts). To reach a
// protected screen we seed that token with an init script BEFORE the app's
// own scripts run, and stub /auth/me to return an operator with the role
// that can see the screen (src/rbac/nav.ts).

const TOKEN_KEY = 'bussola.operator.token' // mirrors src/auth/session.ts

type Role = 'operator' | 'supervisor' | 'admin' | 'auditor'
interface Operator {
  id: number
  username: string
  display_name: string
  role: Role
  is_active: boolean
  must_change_password: boolean
}

const OPERATOR: Operator = {
  id: 1,
  username: 'mrossi',
  display_name: 'M. Rossi',
  role: 'operator',
  is_active: true,
  must_change_password: false,
}
function operatorWith(overrides: Partial<Operator> = {}): Operator {
  return { ...OPERATOR, ...overrides }
}
const ADMIN: Operator = {
  id: 9,
  username: 'admin',
  display_name: 'Amministratore',
  role: 'admin',
  is_active: true,
  must_change_password: false,
}
const OPERATORS: Operator[] = [
  { id: 1, username: 'm.rossi', display_name: 'Maria Rossi', role: 'operator', is_active: true, must_change_password: false },
  { id: 2, username: 'g.bianchi', display_name: 'Giulia Bianchi', role: 'supervisor', is_active: true, must_change_password: true },
  { id: 3, username: 'a.verdi', display_name: 'Aldo Verdi', role: 'operator', is_active: false, must_change_password: false },
]

// Fixtures mirror src/test/fakeClient.ts, translated into the RAW JSON shapes
// the real endpoints return (see src/api/operatorClient.ts — unlike the fake
// client's `{status, ...}` wrapper, the wire format is the bare payload).
const JOB = {
  id: 7,
  title: 'Aiuto cuoco',
  sector: 'Ristorazione',
  description: '',
  required_skills: ['cucina'],
  required_languages: [{ language: 'it', min_level: 'intermediate' }],
  required_availability: 'full_time',
  involves_night_shifts: false,
  training_prerequisites: [],
  created_by: 'mrossi',
}
const MATCH = {
  pseudonym_id: 'P-4F2A',
  score: 0.75,
  requirements: [
    { requirement: 'Esperienza in cucina', satisfied: true, evidence: 'ho lavorato in un ristorante' },
    { requirement: 'Attestato HACCP', satisfied: false, evidence: null },
  ],
  constraint: { compatible: true, reasons: [] },
  gaps: [{ requirement: 'Attestato HACCP', recommended_training: 'Corso HACCP base (8 ore)' }],
}
// Includes all three evidence grades so every SkillBadge color variant is
// exercised on the real page (S25's isolated SkillBadge test has no e2e
// equivalent otherwise — see report for the note).
const PROFILE = {
  pseudonym_id: 'P-4F2A',
  languages: [
    { language: 'it', level: 'fluent' },
    { language: 'ar', level: 'native' },
  ],
  digital_literacy: 'intermediate',
  skills: [
    { name: 'Cucina', kind: 'technical', evidence: 'certified' },
    { name: 'Assistenza clienti', kind: 'soft', evidence: 'demonstrated' },
    { name: 'Puntualità', kind: 'soft', evidence: 'stated' },
  ],
  experiences: [{ role: 'Aiuto cuoco', sector: 'Ristorazione', duration_months: 24 }],
  aspiration: { fields_of_interest: ['Ristorazione'], availability: 'full_time', constraints: ['no_night_shifts'] },
  desired_training: [{ topic: 'HACCP' }],
  operational_notes: ['needs_language_support'],
}
const METRICS = { total_profiles: 5, completed_profiles: 3, average_completeness: 0.6, total_job_requests: 2, matching_runs: 4 }
const REPORT = {
  coverage: { total_profiles: 5, completed_profiles: 3, average_completeness: 0.6, completeness_histogram: { '0-25%': '<5', '75-100%': 3 } },
  languages: { 'it (fluent)': 5, 'ar (native)': '<5' },
  skill_kinds: { technical: 4, soft: 3 },
  skill_evidence: { stated: 2, demonstrated: 2, certified: 1 },
  availability: { full_time: 3, part_time: '<5' },
  constraints: { no_night_shifts: '<5' },
  total_job_requests: 2,
  matching: { runs: 4, evaluated: 4, compatible: 3, compatible_rate: 0.75, top_gaps: { 'Attestato HACCP': '<5' } },
  trends: { profiles_by_week: { '2026-W10': 2 }, job_requests_by_week: { '2026-W10': 1 } },
}
// Three statuses so every `badge-status` color variant (pending/approved/denied)
// is exercised on the real page.
const EXPORT_PENDING = {
  id: 1, requested_by: 'm.rossi', filters: { skill_query: 'cucina' }, reason: 'Azienda X',
  status: 'pending', decided_by: null, decided_at: null, decision_reason: null, created_at: '2026-07-27T10:00:00Z', kind: 'profiles',
}
const EXPORT_APPROVED = {
  id: 2, requested_by: 'g.bianchi', filters: {}, reason: 'Cooperativa Y',
  status: 'approved', decided_by: 'admin', decided_at: '2026-07-27T11:00:00Z', decision_reason: 'ok', created_at: '2026-07-26T09:00:00Z', kind: 'profiles',
}
const EXPORT_DENIED = {
  id: 3, requested_by: 'a.verdi', filters: { language: 'ar' }, reason: 'Ente Z',
  status: 'denied', decided_by: 'admin', decided_at: '2026-07-27T12:00:00Z', decision_reason: 'Fuori ambito', created_at: '2026-07-25T09:00:00Z', kind: 'profiles',
}
const PENDING_PROFILES_EXPORT = {
  id: 4, requested_by: 'm.rossi', filters: { skill_query: 'cucina' }, reason: 'Azienda X',
  status: 'pending', decided_by: null, decided_at: null, decision_reason: null, created_at: '2026-07-27T10:00:00Z', kind: 'profiles',
}
const PENDING_REPORT_EXPORT = {
  id: 5, requested_by: 'g.bianchi', filters: {}, reason: 'Report mensile',
  status: 'pending', decided_by: null, decided_at: null, decision_reason: null, created_at: '2026-07-27T10:00:00Z', kind: 'report',
}
const AUDIT_ENTRIES = [
  { id: 3, occurred_at: '2026-07-27T10:00:00Z', actor: 'm.rossi', action: 'profile_viewed', target_pseudonym: 'P-4F2A', details: {} },
  { id: 2, occurred_at: '2026-07-27T09:00:00Z', actor: null, action: 'export_downloaded', target_pseudonym: null, details: { export_id: 1 } },
]
const ACTIVITY = [
  { actor: 'm.rossi', profiles_viewed: 4, profiles_searched: 2, matchings_run: 1, exports_requested: 1, exports_downloaded: 0, last_active: '2026-07-27T10:00:00Z' },
]
const SYSTEM_CONFIG = {
  llm_model: 'qwen2.5-7b-instruct', llm_base_url: 'http://127.0.0.1:8080', llm_timeout: 120, llm_reachable: true,
  languages: ['it', 'en', 'fr', 'es', 'ar'], stt_model: 'large-v3-turbo',
  tts_voices: { it: true, en: true, fr: true, es: true, ar: false },
  session_ttl_seconds: 43200, session_idle_seconds: 1800, max_failed_attempts: 5, lockout_seconds: 900,
}

function json(body: unknown, status = 200) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

// Several API paths coincide with the SPA's own client-side routes (e.g. the
// frontend route "/metrics" and the "GET /metrics" endpoint are the same
// path). page.route() intercepts EVERY request matching its pattern,
// including the initial document navigation — without this guard, the mocked
// JSON would be served as the top-level document instead of index.html, and
// the app would never boot. Real fetch()/XHR calls have resourceType
// 'fetch'/'xhr'; the browser's own navigation request has resourceType
// 'document' — only intercept the former, let the latter through to the
// preview server so the SPA shell loads normally.
function apiRoute(page: Page, pattern: RegExp, respond: (route: Route) => unknown): Promise<void> {
  return page.route(pattern, (route) => {
    const type = route.request().resourceType()
    if (type !== 'fetch' && type !== 'xhr') return route.continue()
    return respond(route)
  })
}

// Seed the bearer token BEFORE the app boots (AuthProvider reads it on the
// first render) and stub GET /auth/me with the given operator. Pass `null`
// to reach the portal fully logged out (Login screen).
async function mockAuth(page: Page, operator: Operator | null): Promise<void> {
  if (!operator) return
  await page.addInitScript(
    ([key, token]) => sessionStorage.setItem(key, token),
    [TOKEN_KEY, 'e2e-token'] as const,
  )
  await apiRoute(page, /\/auth\/me$/, (route) => route.fulfill(json(operator)))
}

async function audit(page: Page, label: string): Promise<void> {
  // WCAG 2 A/AA, INCLUDING color-contrast — the whole reason for a real browser.
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  const summary = violations.map((v) => ({ id: v.id, help: v.help, nodes: v.nodes.map((n) => n.target) }))
  expect(violations, `${label} a11y violations:\n${JSON.stringify(summary, null, 2)}`).toEqual([])
}

test('Login has no a11y violations', async ({ page }) => {
  // No token seeded: AuthProvider never calls /auth/me, portal stays logged out.
  await page.goto('/login')
  await expect(page.getByLabel('Nome utente')).toBeVisible()
  await audit(page, 'login')
})

test('ChangePassword has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ must_change_password: true }))
  await page.goto('/change-password')
  await expect(page.getByLabel('Password attuale')).toBeVisible()
  await audit(page, 'change-password')
})

test('Home (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await page.goto('/')
  await expect(page.getByText('Benvenuto/a, M. Rossi')).toBeVisible()
  await audit(page, 'home')
})

test('Unauthorized has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await page.goto('/unauthorized')
  await expect(page.getByRole('alert')).toBeVisible()
  await audit(page, 'unauthorized')
})

test('MetricsPanel (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ role: 'supervisor' }))
  await apiRoute(page, /\/metrics$/, (route) => route.fulfill(json(METRICS)))
  await page.goto('/metrics')
  await expect(page.getByText('60%')).toBeVisible()
  await audit(page, 'metrics')
})

test('ReportPanel (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ role: 'supervisor' }))
  await apiRoute(page, /\/report$/, (route) => route.fulfill(json(REPORT)))
  await apiRoute(page, /\/report\/export$/, (route) => route.fulfill(json({ ...EXPORT_PENDING, kind: 'report' })))
  await page.goto('/report')
  await expect(page.getByText('60%')).toBeVisible()
  // Also drive the export button so the "pending" follow-up message renders.
  await page.getByRole('button', { name: 'Esporta report' }).click()
  await expect(page.getByText('Richiesta inviata, in attesa di approvazione')).toBeVisible()
  await audit(page, 'report')
})

test('OperatorActivityPanel (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ role: 'supervisor' }))
  await apiRoute(page, /\/operator-activity$/, (route) => route.fulfill(json(ACTIVITY)))
  await page.goto('/activity')
  await expect(page.getByText('m.rossi')).toBeVisible()
  await audit(page, 'activity')
})

test('SystemConfigPanel (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ role: 'admin' }))
  await apiRoute(page, /\/system-config$/, (route) => route.fulfill(json(SYSTEM_CONFIG)))
  await page.goto('/config')
  await expect(page.getByText('qwen2.5-7b-instruct')).toBeVisible()
  await audit(page, 'system-config')
})

test('AuditLog (loaded, chain verified) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ role: 'auditor' }))
  await apiRoute(page, /\/audit(\?.*)?$/, (route) => route.fulfill(json(AUDIT_ENTRIES)))
  await apiRoute(page, /\/audit\/verify$/, (route) => route.fulfill(json({ ok: true, broken_at: null, reason: null })))
  await page.goto('/audit')
  await expect(page.getByText('profile_viewed')).toBeVisible()
  await page.getByRole('button', { name: 'Verifica integrità' }).click()
  await expect(page.getByText('Catena integra')).toBeVisible()
  await audit(page, 'audit-log-verified')
})

test('AuditLog — broken-chain badge has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ role: 'auditor' }))
  await apiRoute(page, /\/audit(\?.*)?$/, (route) => route.fulfill(json(AUDIT_ENTRIES)))
  await apiRoute(page, /\/audit\/verify$/, (route) => route.fulfill(json({ ok: false, broken_at: 2, reason: 'hash mismatch' })))
  await page.goto('/audit')
  await expect(page.getByText('profile_viewed')).toBeVisible()
  await page.getByRole('button', { name: 'Verifica integrità' }).click()
  await expect(page.getByText(/Manomissione rilevata/)).toBeVisible()
  await audit(page, 'audit-log-broken')
})

test('ExportRequests (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await apiRoute(page, /\/exports$/, (route) =>
    route.request().method() === 'GET' ? route.fulfill(json([EXPORT_PENDING, EXPORT_APPROVED, EXPORT_DENIED])) : route.continue(),
  )
  await page.goto('/export')
  await expect(page.getByText('cucina')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Scarica' })).toBeVisible() // the approved row
  await audit(page, 'export-requests')
})

test('ExportRequests — new export form (NewExportForm) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await apiRoute(page, /\/exports$/, (route) =>
    route.request().method() === 'GET' ? route.fulfill(json([EXPORT_PENDING])) : route.continue(),
  )
  await page.goto('/export')
  await expect(page.getByText('cucina')).toBeVisible()
  await page.getByRole('button', { name: '+ Nuova richiesta' }).click()
  await expect(page.getByLabel('Motivo / destinatario')).toBeVisible()
  await audit(page, 'export-requests-new-form')
})

test('ExportApprovals (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ role: 'supervisor' }))
  await apiRoute(page, /\/exports\/pending$/, (route) => route.fulfill(json([PENDING_PROFILES_EXPORT, PENDING_REPORT_EXPORT])))
  await page.goto('/export-approvals')
  await expect(page.getByText('m.rossi')).toBeVisible()
  await expect(page.getByText('Report aggregato')).toBeVisible() // requestScope() report-kind branch
  await audit(page, 'export-approvals')
})

test('ExportApprovals — deny dialog (DenyDialog) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith({ role: 'supervisor' }))
  await apiRoute(page, /\/exports\/pending$/, (route) => route.fulfill(json([PENDING_PROFILES_EXPORT])))
  await page.goto('/export-approvals')
  await expect(page.getByText('m.rossi')).toBeVisible()
  await page.getByRole('button', { name: 'Nega' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await audit(page, 'export-approvals-deny-dialog')
})

test('JobRequestList (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await apiRoute(page, /\/job-requests$/, (route) =>
    route.request().method() === 'GET' ? route.fulfill(json([JOB])) : route.continue(),
  )
  await page.goto('/job-requests')
  await expect(page.getByText('Aiuto cuoco')).toBeVisible()
  await audit(page, 'job-request-list')
})

test('JobRequestCreate has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await page.goto('/job-requests/new')
  await expect(page.getByLabel('Titolo')).toBeVisible()
  // Exercise the dynamic language fieldset (the more complex part of the form).
  await page.getByRole('button', { name: 'Aggiungi lingua' }).click()
  await expect(page.getByLabel('Lingua 1')).toBeVisible()
  await audit(page, 'job-request-create')
})

test('JobRequestDetail + MatchResults (expanded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await apiRoute(page, /\/job-requests\/\d+\/match$/, (route) => route.fulfill(json([MATCH])))
  await apiRoute(page, /\/job-requests\/\d+$/, (route) => route.fulfill(json(JOB)))
  await page.goto('/job-requests/7')
  await expect(page.getByRole('heading', { name: 'Aiuto cuoco' })).toBeVisible()
  await page.getByRole('button', { name: 'Esegui matching' }).click()
  await expect(page.getByText('P-4F2A')).toBeVisible()
  // Expand the match card to also audit the verdicts/gaps detail markup.
  await page.getByRole('button', { name: 'Dettagli' }).click()
  await expect(page.getByText('Gap → formazione consigliata')).toBeVisible()
  await audit(page, 'job-request-detail-match-expanded')
})

test('ProfileSearch (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await apiRoute(page, /\/profiles(\?.*)?$/, (route) => route.fulfill(json([PROFILE])))
  await page.goto('/profiles')
  await expect(page.getByRole('link', { name: 'P-4F2A' })).toBeVisible()
  await audit(page, 'profile-search')
})

test('ProfileDetail (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await apiRoute(page, /\/profiles\/[^/?]+$/, (route) => route.fulfill(json(PROFILE)))
  await page.goto('/profiles/P-4F2A')
  await expect(page.getByRole('heading', { name: 'P-4F2A' })).toBeVisible()
  await expect(page.getByText('Certificata')).toBeVisible()
  await expect(page.getByText('Dimostrata')).toBeVisible()
  await expect(page.getByText('Dichiarata')).toBeVisible()
  await audit(page, 'profile-detail')
})

test('ProfileDetail — follow-up token modal (FollowupTokenModal) has no a11y violations', async ({ page }) => {
  await mockAuth(page, operatorWith())
  await apiRoute(page, /\/profiles\/[^/?]+$/, (route) => route.fulfill(json(PROFILE)))
  await apiRoute(page, /\/followups$/, (route) => route.fulfill(json({ token: 'FUP-9K2M-7QRT' })))
  await page.goto('/profiles/P-4F2A')
  await expect(page.getByRole('heading', { name: 'P-4F2A' })).toBeVisible()
  await page.getByRole('button', { name: 'Nuovo follow-up' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('FUP-9K2M-7QRT')).toBeVisible()
  await audit(page, 'profile-detail-followup-modal')
})

test('OperatorList (loaded) has no a11y violations', async ({ page }) => {
  await mockAuth(page, ADMIN)
  await apiRoute(page, /\/operators$/, (route) =>
    route.request().method() === 'GET' ? route.fulfill(json(OPERATORS)) : route.continue(),
  )
  await page.goto('/operators')
  await expect(page.getByText('Maria Rossi')).toBeVisible()
  await audit(page, 'operator-list')
})

test('OperatorList — create form (CreateOperatorForm) has no a11y violations', async ({ page }) => {
  await mockAuth(page, ADMIN)
  await apiRoute(page, /\/operators$/, (route) =>
    route.request().method() === 'GET' ? route.fulfill(json(OPERATORS)) : route.continue(),
  )
  await page.goto('/operators')
  await expect(page.getByText('Maria Rossi')).toBeVisible()
  await page.getByRole('button', { name: '+ Nuovo operatore' }).click()
  await expect(page.getByLabel('Nome utente')).toBeVisible()
  await audit(page, 'operator-list-create-form')
})

test('OperatorList — reset password (ConfirmDialog + TempPasswordModal) has no a11y violations', async ({ page }) => {
  await mockAuth(page, ADMIN)
  await apiRoute(page, /\/operators$/, (route) =>
    route.request().method() === 'GET' ? route.fulfill(json(OPERATORS)) : route.continue(),
  )
  await apiRoute(page, /\/operators\/\d+\/reset-password$/, (route) => route.fulfill(json({ temp_password: 'NEW-pw-123' })))
  await page.goto('/operators')
  await expect(page.getByText('Maria Rossi')).toBeVisible()
  await page.getByRole('row', { name: /m\.rossi/ }).getByRole('button', { name: 'Reset password' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Conferma' }).click()
  await expect(page.getByText('NEW-pw-123')).toBeVisible()
  await audit(page, 'operator-list-reset-password')
})
