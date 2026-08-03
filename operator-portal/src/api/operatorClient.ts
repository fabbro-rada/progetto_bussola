import { getToken } from '../auth/session'
import type {
  AuditEntry,
  AuditFilters,
  AuditListResult,
  AuditVerification,
  ChangeResult,
  CreateExportResult,
  CreateFollowupResult,
  CreateJobRequestResult,
  CreateOperatorRequest,
  CreateOperatorResult,
  CreatedOperator,
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
  ProvisionInterviewResult,
  Report,
  ReportResult,
  ResetPasswordResult,
  ResetResponse,
  SearchProfilesResult,
  SystemConfig,
  SystemConfigResult,
  VerifyAuditResult,
  WorkProfile,
} from '../types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

function headers(json: boolean): Record<string, string> {
  const h: Record<string, string> = {}
  if (json) h['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

async function login(username: string, password: string): Promise<LoginResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'invalid' }
  if (!res.ok) return { status: 'error' }
  try {
    const data = (await res.json()) as { token: string; operator: Operator; must_change_password: boolean }
    return { status: 'ok', token: data.token, operator: data.operator, mustChangePassword: data.must_change_password }
  } catch {
    return { status: 'error' }
  }
}

async function me(): Promise<MeResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/auth/me`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', operator: (await res.json()) as Operator }
  } catch {
    return { status: 'error' }
  }
}

async function logout(): Promise<void> {
  try {
    await fetch(`${BASE}/auth/logout`, { method: 'POST', headers: headers(false) })
  } catch {
    // best-effort: the caller clears the local session regardless
  }
}

async function changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/auth/change-password`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 204 || res.ok) return { status: 'ok' }
  return { status: 'error' }
}

async function listJobRequests(): Promise<ListJobRequestsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/job-requests`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', jobs: (await res.json()) as JobRequest[] }
  } catch {
    return { status: 'error' }
  }
}

async function getJobRequest(id: number): Promise<GetJobRequestResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/job-requests/${id}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 404) return { status: 'not-found' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', job: (await res.json()) as JobRequest }
  } catch {
    return { status: 'error' }
  }
}

async function createJobRequest(body: JobRequestCreate): Promise<CreateJobRequestResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/job-requests`, { method: 'POST', headers: headers(true), body: JSON.stringify(body) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', job: (await res.json()) as JobRequest }
  } catch {
    return { status: 'error' }
  }
}

async function runMatch(id: number): Promise<MatchResultsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/job-requests/${id}/match`, { method: 'POST', headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', results: (await res.json()) as MatchResult[] }
  } catch {
    return { status: 'error' }
  }
}

async function searchProfiles(filters: ProfileFilters): Promise<SearchProfilesResult> {
  const qs = new URLSearchParams()
  if (filters.availability) qs.set('availability', filters.availability)
  if (filters.language) qs.set('language', filters.language)
  if (filters.note) qs.set('note', filters.note)
  if (filters.skill_query) qs.set('skill_query', filters.skill_query)
  const q = qs.toString()
  let res: Response
  try {
    res = await fetch(`${BASE}/profiles${q ? `?${q}` : ''}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', profiles: (await res.json()) as WorkProfile[] }
  } catch {
    return { status: 'error' }
  }
}

async function getProfile(pseudonym: string): Promise<GetProfileResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/profiles/${encodeURIComponent(pseudonym)}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 404) return { status: 'not-found' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', profile: (await res.json()) as WorkProfile }
  } catch {
    return { status: 'error' }
  }
}

async function createFollowup(pseudonymId: string): Promise<CreateFollowupResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/followups`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ pseudonym_id: pseudonymId }),
    })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    const data = (await res.json()) as { token: string }
    return { status: 'ok', token: data.token }
  } catch {
    return { status: 'error' }
  }
}

async function provisionInterview(matricola: string): Promise<ProvisionInterviewResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/interviews/provision`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ matricola }),
    })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 409) return { status: 'conflict' }
  if (!res.ok) return { status: 'error' }
  try {
    const data = (await res.json()) as { start_code: string }
    return { status: 'ok', startCode: data.start_code }
  } catch {
    return { status: 'error' }
  }
}

async function listOperators(): Promise<ListOperatorsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operators`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', operators: (await res.json()) as Operator[] }
  } catch {
    return { status: 'error' }
  }
}

async function createOperator(body: CreateOperatorRequest): Promise<CreateOperatorResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operators`, { method: 'POST', headers: headers(true), body: JSON.stringify(body) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', created: (await res.json()) as CreatedOperator }
  } catch {
    return { status: 'error' }
  }
}

async function mutateOperator(id: number, action: 'disable' | 'enable'): Promise<MutateOperatorResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operators/${id}/${action}`, { method: 'POST', headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 204 || res.ok) return { status: 'ok' }
  return { status: 'error' }
}

function disableOperator(id: number): Promise<MutateOperatorResult> {
  return mutateOperator(id, 'disable')
}

function enableOperator(id: number): Promise<MutateOperatorResult> {
  return mutateOperator(id, 'enable')
}

async function resetPassword(id: number): Promise<ResetPasswordResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operators/${id}/reset-password`, { method: 'POST', headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', temp_password: ((await res.json()) as ResetResponse).temp_password }
  } catch {
    return { status: 'error' }
  }
}

async function getMetrics(): Promise<MetricsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/metrics`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', metrics: (await res.json()) as Metrics }
  } catch {
    return { status: 'error' }
  }
}

async function getReport(): Promise<ReportResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/report`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', report: (await res.json()) as Report }
  } catch {
    return { status: 'error' }
  }
}

async function createReportExport(): Promise<CreateExportResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/report/export`, { method: 'POST', headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', request: (await res.json()) as ExportRequest }
  } catch {
    return { status: 'error' }
  }
}

async function createExport(filters: ProfileFilters, reason: string): Promise<CreateExportResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/exports`, { method: 'POST', headers: headers(true), body: JSON.stringify({ filters, reason }) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', request: (await res.json()) as ExportRequest }
  } catch {
    return { status: 'error' }
  }
}

async function listExportsAt(path: string): Promise<ListExportsResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', requests: (await res.json()) as ExportRequest[] }
  } catch {
    return { status: 'error' }
  }
}

function listExports(): Promise<ListExportsResult> {
  return listExportsAt('/exports')
}

function listPendingExports(): Promise<ListExportsResult> {
  return listExportsAt('/exports/pending')
}

async function decideExport(id: number, action: 'approve' | 'deny', reason?: string): Promise<MutateExportResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/exports/${id}/${action}`, {
      method: 'POST',
      headers: headers(reason !== undefined),
      body: reason !== undefined ? JSON.stringify({ reason }) : undefined,
    })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 404) return { status: 'not-found' }
  if (res.status === 409) return { status: 'conflict' }
  if (res.status === 204 || res.ok) return { status: 'ok' }
  return { status: 'error' }
}

function approveExport(id: number): Promise<MutateExportResult> {
  return decideExport(id, 'approve')
}

function denyExport(id: number, reason: string): Promise<MutateExportResult> {
  return decideExport(id, 'deny', reason)
}

async function downloadExport(id: number): Promise<DownloadExportResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/exports/${id}/download`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (res.status === 404) return { status: 'not-found' }
  if (res.status === 409) return { status: 'not-approved' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', blob: await res.blob() }
  } catch {
    return { status: 'error' }
  }
}

async function listAudit(filters: AuditFilters): Promise<AuditListResult> {
  const qs = new URLSearchParams()
  if (filters.before !== undefined) qs.set('before', String(filters.before))
  if (filters.limit !== undefined) qs.set('limit', String(filters.limit))
  if (filters.actor) qs.set('actor', filters.actor)
  if (filters.action) qs.set('action', filters.action)
  if (filters.from) qs.set('from', filters.from)
  if (filters.to) qs.set('to', filters.to)
  const q = qs.toString()
  let res: Response
  try {
    res = await fetch(`${BASE}/audit${q ? `?${q}` : ''}`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', entries: (await res.json()) as AuditEntry[] }
  } catch {
    return { status: 'error' }
  }
}

async function verifyAudit(): Promise<VerifyAuditResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/audit/verify`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', verification: (await res.json()) as AuditVerification }
  } catch {
    return { status: 'error' }
  }
}

async function getOperatorActivity(): Promise<OperatorActivityResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/operator-activity`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', activity: (await res.json()) as OperatorActivity[] }
  } catch {
    return { status: 'error' }
  }
}

async function getSystemConfig(): Promise<SystemConfigResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/system-config`, { headers: headers(false) })
  } catch {
    return { status: 'error' }
  }
  if (res.status === 401) return { status: 'unauthorized' }
  if (res.status === 403) return { status: 'forbidden' }
  if (!res.ok) return { status: 'error' }
  try {
    return { status: 'ok', config: (await res.json()) as SystemConfig }
  } catch {
    return { status: 'error' }
  }
}

export const operatorClient: OperatorClient = {
  login,
  me,
  logout,
  changePassword,
  listJobRequests,
  getJobRequest,
  createJobRequest,
  runMatch,
  searchProfiles,
  getProfile,
  createFollowup,
  provisionInterview,
  listOperators,
  createOperator,
  disableOperator,
  enableOperator,
  resetPassword,
  getMetrics,
  getReport,
  createReportExport,
  createExport,
  listExports,
  listPendingExports,
  approveExport,
  denyExport,
  downloadExport,
  listAudit,
  verifyAudit,
  getOperatorActivity,
  getSystemConfig,
}
