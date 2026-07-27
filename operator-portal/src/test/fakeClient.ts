import type {
  ChangeResult,
  CreateJobRequestResult,
  CreateOperatorRequest,
  CreateOperatorResult,
  GetJobRequestResult,
  GetProfileResult,
  JobRequest,
  JobRequestCreate,
  ListJobRequestsResult,
  ListOperatorsResult,
  LoginResult,
  MatchResult,
  MatchResultsResult,
  MeResult,
  MutateOperatorResult,
  Operator,
  OperatorClient,
  ProfileFilters,
  ResetPasswordResult,
  Role,
  SearchProfilesResult,
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
  }
  created: JobRequestCreate[]
  searched: ProfileFilters[]
  createdOperators: CreateOperatorRequest[]
  disabledIds: number[]
  enabledIds: number[]
  resetIds: number[]
} {
  const calls = {
    login: 0, me: 0, logout: 0, change: 0, list: 0, get: 0, create: 0, match: 0, psearch: 0, pget: 0,
    lops: 0, opcreate: 0, opdisable: 0, openable: 0, opreset: 0,
  }
  const created: JobRequestCreate[] = []
  const searched: ProfileFilters[] = []
  const createdOperators: CreateOperatorRequest[] = []
  const disabledIds: number[] = []
  const enabledIds: number[] = []
  const resetIds: number[] = []
  return {
    calls,
    created,
    searched,
    createdOperators,
    disabledIds,
    enabledIds,
    resetIds,
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
  }
}

export const ROLES: Role[] = ['operator', 'supervisor', 'admin', 'auditor']
