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

export type DigitalLiteracy = 'none' | 'basic' | 'intermediate' | 'advanced'
export type EvidenceGrade = 'stated' | 'demonstrated' | 'certified'
export type SkillKind = 'technical' | 'soft'
export type WorkConstraint = 'no_night_shifts' | 'part_time_only' | 'needs_training_first'
export type OperationalNoteCategory =
  | 'needs_language_support'
  | 'needs_literacy_support'
  | 'limited_availability'
  | 'prefers_team_work'
  | 'prefers_solo_work'

export interface LanguageKnown {
  language: string
  level: LanguageLevel
}
export interface Skill {
  name: string
  kind: SkillKind
  evidence: EvidenceGrade
}
export interface WorkExperience {
  role: string
  sector: string
  duration_months: number
}
export interface Aspiration {
  fields_of_interest: string[]
  availability: Availability | null
  constraints: WorkConstraint[]
}
export interface DesiredTraining {
  topic: string
}
export interface WorkProfile {
  pseudonym_id: string
  languages: LanguageKnown[]
  digital_literacy: DigitalLiteracy | null
  skills: Skill[]
  experiences: WorkExperience[]
  aspiration: Aspiration | null
  desired_training: DesiredTraining[]
  operational_notes: OperationalNoteCategory[]
}

export interface ProfileFilters {
  availability?: Availability
  language?: string
  note?: OperationalNoteCategory
  skill_query?: string
}

export type SearchProfilesResult =
  | { status: 'ok'; profiles: WorkProfile[] }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type GetProfileResult =
  | { status: 'ok'; profile: WorkProfile }
  | { status: 'not-found' }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }

export interface CreateOperatorRequest {
  username: string
  display_name: string
  role: Role
}
export interface CreatedOperator {
  operator: Operator
  temp_password: string
}
export interface ResetResponse {
  temp_password: string
}
export type ListOperatorsResult =
  | { status: 'ok'; operators: Operator[] }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type CreateOperatorResult =
  | { status: 'ok'; created: CreatedOperator }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type MutateOperatorResult =
  | { status: 'ok' }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }
export type ResetPasswordResult =
  | { status: 'ok'; temp_password: string }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }

export interface Metrics {
  total_profiles: number
  completed_profiles: number
  average_completeness: number
  total_job_requests: number
  matching_runs: number
}
export type MetricsResult =
  | { status: 'ok'; metrics: Metrics }
  | { status: 'unauthorized' }
  | { status: 'forbidden' }
  | { status: 'error' }

export type ExportStatus = 'pending' | 'approved' | 'denied'
export interface ExportRequest {
  id: number
  requested_by: string
  filters: ProfileFilters
  reason: string
  status: ExportStatus
  decided_by: string | null
  decided_at: string | null
  decision_reason: string | null
  created_at: string
}
export type CreateExportResult =
  | { status: 'ok'; request: ExportRequest }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
export type ListExportsResult =
  | { status: 'ok'; requests: ExportRequest[] }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
export type MutateExportResult =
  | { status: 'ok' }
  | { status: 'unauthorized' } | { status: 'forbidden' }
  | { status: 'not-found' } | { status: 'conflict' } | { status: 'error' }
export type DownloadExportResult =
  | { status: 'ok'; blob: Blob }
  | { status: 'unauthorized' } | { status: 'forbidden' }
  | { status: 'not-found' } | { status: 'not-approved' } | { status: 'error' }

export interface AuditEntry {
  id: number
  occurred_at: string
  actor: string | null
  action: string
  target_pseudonym: string | null
  details: Record<string, unknown>
}
export interface AuditFilters {
  before?: number
  limit?: number
  actor?: string
  action?: string
  from?: string
  to?: string
}
export interface AuditVerification {
  ok: boolean
  broken_at: number | null
  reason: string | null
}
export type AuditListResult =
  | { status: 'ok'; entries: AuditEntry[] }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }
export type VerifyAuditResult =
  | { status: 'ok'; verification: AuditVerification }
  | { status: 'unauthorized' } | { status: 'forbidden' } | { status: 'error' }

export interface OperatorClient {
  login(username: string, password: string): Promise<LoginResult>
  me(): Promise<MeResult>
  logout(): Promise<void>
  changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult>
  listJobRequests(): Promise<ListJobRequestsResult>
  getJobRequest(id: number): Promise<GetJobRequestResult>
  createJobRequest(body: JobRequestCreate): Promise<CreateJobRequestResult>
  runMatch(id: number): Promise<MatchResultsResult>
  searchProfiles(filters: ProfileFilters): Promise<SearchProfilesResult>
  getProfile(pseudonym: string): Promise<GetProfileResult>
  listOperators(): Promise<ListOperatorsResult>
  createOperator(body: CreateOperatorRequest): Promise<CreateOperatorResult>
  disableOperator(id: number): Promise<MutateOperatorResult>
  enableOperator(id: number): Promise<MutateOperatorResult>
  resetPassword(id: number): Promise<ResetPasswordResult>
  getMetrics(): Promise<MetricsResult>
  createExport(filters: ProfileFilters, reason: string): Promise<CreateExportResult>
  listExports(): Promise<ListExportsResult>
  listPendingExports(): Promise<ListExportsResult>
  approveExport(id: number): Promise<MutateExportResult>
  denyExport(id: number, reason: string): Promise<MutateExportResult>
  downloadExport(id: number): Promise<DownloadExportResult>
  listAudit(filters: AuditFilters): Promise<AuditListResult>
  verifyAudit(): Promise<VerifyAuditResult>
}
