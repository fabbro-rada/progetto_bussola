import type {
  AuditEntry,
  AuditFilters,
  AuditListResult,
  ChangeResult,
  CreateExportResult,
  CreateJobRequestResult,
  CreateOperatorRequest,
  CreateOperatorResult,
  DownloadExportResult,
  ExportRequest,
  GetJobRequestResult,
  GetProfileResult,
  JobRequest,
  JobRequestCreate,
  ListExportsResult,
  ListJobRequestsResult,
  ListOperatorsResult,
  LoginResult,
  MatchResult,
  MatchResultsResult,
  MeResult,
  Metrics,
  MetricsResult,
  MutateExportResult,
  MutateOperatorResult,
  Operator,
  OperatorActivity,
  OperatorActivityResult,
  OperatorClient,
  ProfileFilters,
  Report,
  ReportResult,
  ResetPasswordResult,
  Role,
  SearchProfilesResult,
  SystemConfig,
  SystemConfigResult,
  VerifyAuditResult,
  WorkProfile,
} from '../types'

export const OPERATOR: Operator = {
  id: 1,
  username: 'mrossi',
  display_name: 'M. Rossi',
  role: 'operator',
  is_active: true,
  must_change_password: false,
}

export function operatorWith(overrides: Partial<Operator> = {}): Operator {
  return { ...OPERATOR, ...overrides }
}

export const ADMIN: Operator = {
  id: 9, username: 'admin', display_name: 'Amministratore', role: 'admin', is_active: true, must_change_password: false,
}
export const OPERATORS: Operator[] = [
  { id: 1, username: 'm.rossi', display_name: 'Maria Rossi', role: 'operator', is_active: true, must_change_password: false },
  { id: 2, username: 'g.bianchi', display_name: 'Giulia Bianchi', role: 'supervisor', is_active: true, must_change_password: true },
  { id: 3, username: 'a.verdi', display_name: 'Aldo Verdi', role: 'operator', is_active: false, must_change_password: false },
]

export const JOB: JobRequest = {
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
export const MATCH: MatchResult = {
  pseudonym_id: 'P-4F2A',
  score: 0.75,
  requirements: [
    { requirement: 'Esperienza in cucina', satisfied: true, evidence: 'ho lavorato in un ristorante' },
    { requirement: 'Attestato HACCP', satisfied: false, evidence: null },
  ],
  constraint: { compatible: true, reasons: [] },
  gaps: [{ requirement: 'Attestato HACCP', recommended_training: 'Corso HACCP base (8 ore)' }],
}

export const PROFILE: WorkProfile = {
  pseudonym_id: 'P-4F2A',
  languages: [{ language: 'it', level: 'fluent' }, { language: 'ar', level: 'native' }],
  digital_literacy: 'intermediate',
  skills: [
    { name: 'Cucina', kind: 'technical', evidence: 'certified' },
    { name: 'Puntualità', kind: 'soft', evidence: 'stated' },
  ],
  experiences: [{ role: 'Aiuto cuoco', sector: 'Ristorazione', duration_months: 24 }],
  aspiration: { fields_of_interest: ['Ristorazione'], availability: 'full_time', constraints: ['no_night_shifts'] },
  desired_training: [{ topic: 'HACCP' }],
  operational_notes: ['needs_language_support'],
}

export const METRICS: Metrics = {
  total_profiles: 5, completed_profiles: 3, average_completeness: 0.6, total_job_requests: 2, matching_runs: 4,
}

export const EXPORT_REQUEST: ExportRequest = {
  id: 1, requested_by: 'm.rossi', filters: { skill_query: 'cucina' }, reason: 'Azienda X',
  status: 'pending', decided_by: null, decided_at: null, decision_reason: null, created_at: '2026-07-27T10:00:00Z',
  kind: 'profiles',
}

export const REPORT: Report = {
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

export const AUDIT_ENTRY: AuditEntry = {
  id: 3, occurred_at: '2026-07-27T10:00:00Z', actor: 'm.rossi', action: 'profile_viewed', target_pseudonym: 'P-4F2A', details: {},
}

export const ACTIVITY: OperatorActivity[] = [
  { actor: 'm.rossi', profiles_viewed: 4, profiles_searched: 2, matchings_run: 1, exports_requested: 1, exports_downloaded: 0, last_active: '2026-07-27T10:00:00Z' },
]

export const SYSTEM_CONFIG: SystemConfig = {
  llm_model: 'qwen2.5-7b-instruct', llm_base_url: 'http://127.0.0.1:8080', llm_timeout: 120, llm_reachable: true,
  languages: ['it', 'en', 'fr', 'es', 'ar'], stt_model: 'large-v3-turbo',
  tts_voices: { it: true, en: true, fr: true, es: true, ar: false },
  session_ttl_seconds: 43200, session_idle_seconds: 1800, max_failed_attempts: 5, lockout_seconds: 900,
}

// Deterministic fake; each method returns its canned result and records calls.
export function makeFakeClient(opts: {
  login?: LoginResult
  me?: MeResult
  change?: ChangeResult
  jobs?: ListJobRequestsResult
  job?: GetJobRequestResult
  create?: CreateJobRequestResult
  match?: MatchResultsResult
  profiles?: SearchProfilesResult
  profile?: GetProfileResult
  operators?: ListOperatorsResult
  createOp?: CreateOperatorResult
  disable?: MutateOperatorResult
  enable?: MutateOperatorResult
  reset?: ResetPasswordResult
  metrics?: MetricsResult
  report?: ReportResult
  createReportExp?: CreateExportResult
  exports?: ListExportsResult
  pending?: ListExportsResult
  createExp?: CreateExportResult
  approveExp?: MutateExportResult
  denyExp?: MutateExportResult
  download?: DownloadExportResult
  audit?: AuditListResult
  auditPages?: AuditListResult[]
  verify?: VerifyAuditResult
  activity?: OperatorActivityResult
  systemConfig?: SystemConfigResult
} = {}): OperatorClient & {
  calls: {
    login: number
    me: number
    logout: number
    change: number
    list: number
    get: number
    create: number
    match: number
    psearch: number
    pget: number
    lops: number
    opcreate: number
    opdisable: number
    openable: number
    opreset: number
    metrics: number
    report: number
    reportExport: number
    expList: number
    expPending: number
    expCreate: number
    expApprove: number
    expDeny: number
    expDownload: number
    audList: number
    audVerify: number
    activity: number
    systemConfig: number
  }
  created: JobRequestCreate[]
  searched: ProfileFilters[]
  createdOperators: CreateOperatorRequest[]
  disabledIds: number[]
  enabledIds: number[]
  resetIds: number[]
  createdExports: { filters: ProfileFilters; reason: string }[]
  approvedIds: number[]
  deniedExports: { id: number; reason: string }[]
  downloadedIds: number[]
  auditQueries: AuditFilters[]
} {
  const calls = {
    login: 0, me: 0, logout: 0, change: 0, list: 0, get: 0, create: 0, match: 0, psearch: 0, pget: 0,
    lops: 0, opcreate: 0, opdisable: 0, openable: 0, opreset: 0, metrics: 0, report: 0, reportExport: 0,
    expList: 0, expPending: 0, expCreate: 0, expApprove: 0, expDeny: 0, expDownload: 0,
    audList: 0, audVerify: 0, activity: 0, systemConfig: 0,
  }
  const created: JobRequestCreate[] = []
  const searched: ProfileFilters[] = []
  const createdOperators: CreateOperatorRequest[] = []
  const disabledIds: number[] = []
  const enabledIds: number[] = []
  const resetIds: number[] = []
  const createdExports: { filters: ProfileFilters; reason: string }[] = []
  const approvedIds: number[] = []
  const deniedExports: { id: number; reason: string }[] = []
  const downloadedIds: number[] = []
  const auditQueries: AuditFilters[] = []
  let auditPageIdx = 0
  return {
    calls,
    created,
    searched,
    createdOperators,
    disabledIds,
    enabledIds,
    resetIds,
    createdExports,
    approvedIds,
    deniedExports,
    downloadedIds,
    auditQueries,
    async login() {
      calls.login++
      return opts.login ?? { status: 'ok', token: 'tok', operator: OPERATOR, mustChangePassword: false }
    },
    async me() {
      calls.me++
      return opts.me ?? { status: 'unauthorized' }
    },
    async logout() {
      calls.logout++
    },
    async changePassword() {
      calls.change++
      return opts.change ?? { status: 'ok' }
    },
    async listJobRequests() {
      calls.list++
      return opts.jobs ?? { status: 'ok', jobs: [JOB] }
    },
    async getJobRequest() {
      calls.get++
      return opts.job ?? { status: 'ok', job: JOB }
    },
    async createJobRequest(body) {
      calls.create++
      created.push(body)
      return opts.create ?? { status: 'ok', job: JOB }
    },
    async runMatch() {
      calls.match++
      return opts.match ?? { status: 'ok', results: [MATCH] }
    },
    async searchProfiles(filters) {
      calls.psearch++
      searched.push(filters)
      return opts.profiles ?? { status: 'ok', profiles: [PROFILE] }
    },
    async getProfile() {
      calls.pget++
      return opts.profile ?? { status: 'ok', profile: PROFILE }
    },
    async listOperators() {
      calls.lops++
      return opts.operators ?? { status: 'ok', operators: OPERATORS }
    },
    async createOperator(body) {
      calls.opcreate++
      createdOperators.push(body)
      return opts.createOp ?? { status: 'ok', created: { operator: { id: 10, ...body, is_active: true, must_change_password: true }, temp_password: '7Kq9-mZ2t-Rf4x' } }
    },
    async disableOperator(id) {
      calls.opdisable++
      disabledIds.push(id)
      return opts.disable ?? { status: 'ok' }
    },
    async enableOperator(id) {
      calls.openable++
      enabledIds.push(id)
      return opts.enable ?? { status: 'ok' }
    },
    async resetPassword(id) {
      calls.opreset++
      resetIds.push(id)
      return opts.reset ?? { status: 'ok', temp_password: 'NEW-pw-123' }
    },
    async getMetrics() {
      calls.metrics++
      return opts.metrics ?? { status: 'ok', metrics: METRICS }
    },
    async getReport() {
      calls.report++
      return opts.report ?? { status: 'ok', report: REPORT }
    },
    async createReportExport() {
      calls.reportExport++
      return opts.createReportExp ?? { status: 'ok', request: { ...EXPORT_REQUEST, kind: 'report' } }
    },
    async createExport(filters, reason) {
      calls.expCreate++
      createdExports.push({ filters, reason })
      return opts.createExp ?? { status: 'ok', request: EXPORT_REQUEST }
    },
    async listExports() {
      calls.expList++
      return opts.exports ?? { status: 'ok', requests: [EXPORT_REQUEST] }
    },
    async listPendingExports() {
      calls.expPending++
      return opts.pending ?? { status: 'ok', requests: [EXPORT_REQUEST] }
    },
    async approveExport(id) {
      calls.expApprove++
      approvedIds.push(id)
      return opts.approveExp ?? { status: 'ok' }
    },
    async denyExport(id, reason) {
      calls.expDeny++
      deniedExports.push({ id, reason })
      return opts.denyExp ?? { status: 'ok' }
    },
    async downloadExport(id) {
      calls.expDownload++
      downloadedIds.push(id)
      return opts.download ?? { status: 'ok', blob: new Blob(['[]'], { type: 'application/json' }) }
    },
    async listAudit(filters) {
      calls.audList++
      auditQueries.push(filters)
      if (opts.auditPages) return opts.auditPages[Math.min(auditPageIdx++, opts.auditPages.length - 1)]
      return opts.audit ?? { status: 'ok', entries: [AUDIT_ENTRY] }
    },
    async verifyAudit() {
      calls.audVerify++
      return opts.verify ?? { status: 'ok', verification: { ok: true, broken_at: null, reason: null } }
    },
    async getOperatorActivity() {
      calls.activity++
      return opts.activity ?? { status: 'ok', activity: ACTIVITY }
    },
    async getSystemConfig() {
      calls.systemConfig++
      return opts.systemConfig ?? { status: 'ok', config: SYSTEM_CONFIG }
    },
  }
}

export const ROLES: Role[] = ['operator', 'supervisor', 'admin', 'auditor']
