export type Role = 'operator' | 'supervisor' | 'admin' | 'auditor'

export interface Operator {
  id: number
  username: string
  display_name: string
  role: Role
  is_active: boolean
  must_change_password: boolean
}

export type LoginResult =
  | { status: 'ok'; token: string; operator: Operator; mustChangePassword: boolean }
  | { status: 'invalid' }
  | { status: 'error' }

export type MeResult = { status: 'ok'; operator: Operator } | { status: 'unauthorized' } | { status: 'error' }

export type ChangeResult = { status: 'ok' } | { status: 'unauthorized' } | { status: 'error' }

export type LanguageLevel = 'basic' | 'intermediate' | 'fluent' | 'native'
export type Availability = 'full_time' | 'part_time' | 'flexible'

export interface RequiredLanguage {
  language: string
  min_level: LanguageLevel
}

export interface JobRequestCreate {
  title: string
  sector: string
  description: string
  required_skills: string[]
  required_languages: RequiredLanguage[]
  required_availability: Availability | null
  involves_night_shifts: boolean
  training_prerequisites: string[]
}

export interface JobRequest extends JobRequestCreate {
  id: number
  created_by: string
}

export interface RequirementVerdict {
  requirement: string
  satisfied: boolean
  evidence: string | null
}
export interface ConstraintOutcome {
  compatible: boolean
  reasons: string[]
}
export interface GapItem {
  requirement: string
  recommended_training: string
}
export interface MatchResult {
  pseudonym_id: string
  score: number
  requirements: RequirementVerdict[]
  constraint: ConstraintOutcome
  gaps: GapItem[]
}

export type ListJobRequestsResult =
  | { status: 'ok'; jobs: JobRequest[] }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type GetJobRequestResult =
  | { status: 'ok'; job: JobRequest }
  | { status: 'not-found' }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type CreateJobRequestResult =
  | { status: 'ok'; job: JobRequest }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type MatchResultsResult =
  | { status: 'ok'; results: MatchResult[] }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }

export interface OperatorClient {
  login(username: string, password: string): Promise<LoginResult>
  me(): Promise<MeResult>
  logout(): Promise<void>
  changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult>
  listJobRequests(): Promise<ListJobRequestsResult>
  getJobRequest(id: number): Promise<GetJobRequestResult>
  createJobRequest(body: JobRequestCreate): Promise<CreateJobRequestResult>
  runMatch(id: number): Promise<MatchResultsResult>
}
