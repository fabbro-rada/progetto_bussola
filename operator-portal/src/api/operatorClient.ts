import { getToken } from '../auth/session'
import type { ChangeResult, LoginResult, MeResult, Operator, OperatorClient } from '../types'

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

export const operatorClient: OperatorClient = { login, me, logout, changePassword }
