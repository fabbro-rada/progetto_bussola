import type {
  ChangeResult,
  CreateJobRequestResult,
  GetJobRequestResult,
  GetProfileResult,
  JobRequest,
  JobRequestCreate,
  ListJobRequestsResult,
  LoginResult,
  MatchResult,
  MatchResultsResult,
  MeResult,
  Operator,
  OperatorClient,
  ProfileFilters,
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
  }
  created: JobRequestCreate[]
  searched: ProfileFilters[]
} {
  const calls = { login: 0, me: 0, logout: 0, change: 0, list: 0, get: 0, create: 0, match: 0, psearch: 0, pget: 0 }
  const created: JobRequestCreate[] = []
  const searched: ProfileFilters[] = []
  return {
    calls,
    created,
    searched,
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
  }
}

export const ROLES: Role[] = ['operator', 'supervisor', 'admin', 'auditor']
