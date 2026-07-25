import { getToken } from '../auth/session'
import type {
  ChangeResult,
  CreateJobRequestResult,
  GetJobRequestResult,
  JobRequest,
  JobRequestCreate,
  ListJobRequestsResult,
  LoginResult,
  MatchResult,
  MatchResultsResult,
  MeResult,
  Operator,
  OperatorClient,
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

export const operatorClient: OperatorClient = {
  login,
  me,
  logout,
  changePassword,
  listJobRequests,
  getJobRequest,
  createJobRequest,
  runMatch,
}
