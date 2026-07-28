import { afterEach, expect, test, vi } from 'vitest'
import { operatorClient } from './operatorClient'
import { setToken } from '../auth/session'

afterEach(() => {
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

function res(status: number, body?: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response
}

const OP = { id: 1, username: 'mrossi', display_name: 'M. Rossi', role: 'operator', is_active: true, must_change_password: false }

test('login maps 200 to ok with token+operator', async () => {
  const fetchMock = vi.fn().mockResolvedValue(res(200, { token: 'tok', operator: OP, must_change_password: true }))
  vi.stubGlobal('fetch', fetchMock)
  const r = await operatorClient.login('mrossi', 'pw')
  expect(r).toEqual({ status: 'ok', token: 'tok', operator: OP, mustChangePassword: true })
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/auth/login')
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ username: 'mrossi', password: 'pw' })
})

test('login maps 401 to invalid and 5xx/throw to error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.login('x', 'y')).toEqual({ status: 'invalid' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(500)))
  expect(await operatorClient.login('x', 'y')).toEqual({ status: 'error' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.login('x', 'y')).toEqual({ status: 'error' })
})

test('me sends the Bearer token from sessionStorage and maps 200/401', async () => {
  setToken('tok')
  const fetchMock = vi.fn().mockResolvedValue(res(200, OP))
  vi.stubGlobal('fetch', fetchMock)
  expect(await operatorClient.me()).toEqual({ status: 'ok', operator: OP })
  expect((fetchMock.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.me()).toEqual({ status: 'unauthorized' })
})

test('changePassword maps 204 to ok, 401 to unauthorized, other to error', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(204)))
  expect(await operatorClient.changePassword('old', 'newpassword')).toEqual({ status: 'ok' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.changePassword('old', 'newpassword')).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(400)))
  expect(await operatorClient.changePassword('old', 'x')).toEqual({ status: 'error' })
})

test('changePassword sends {old_password,new_password} with Bearer to /auth/change-password', async () => {
  setToken('tok')
  const fetchMock = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', fetchMock)
  await operatorClient.changePassword('oldpw', 'newpassword')
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/auth/change-password')
  expect((init!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ old_password: 'oldpw', new_password: 'newpassword' })
})

test('logout posts to /auth/logout with Bearer and never throws on failure', async () => {
  setToken('tok')
  const fetchMock = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', fetchMock)
  await operatorClient.logout()
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/auth/logout')
  expect((init!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  // best-effort: a rejected fetch must not throw
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  await expect(operatorClient.logout()).resolves.toBeUndefined()
})

const JOB = {
  id: 7, title: 'Aiuto cuoco', sector: 'Ristorazione', description: '', created_by: 'mrossi',
  required_skills: ['cucina'], required_languages: [{ language: 'it', min_level: 'intermediate' }],
  required_availability: 'full_time', involves_night_shifts: false, training_prerequisites: [],
}
const MATCH = {
  pseudonym_id: 'P-4F2A', score: 0.75,
  requirements: [{ requirement: 'Esperienza in cucina', satisfied: true, evidence: 'ho lavorato in un ristorante' }],
  constraint: { compatible: true, reasons: [] },
  gaps: [{ requirement: 'HACCP', recommended_training: 'Corso HACCP base' }],
}

test('listJobRequests: 200→ok with Bearer; 401→unauthorized; 403→forbidden', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, [JOB]))
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.listJobRequests()
  expect(r).toEqual({ status: 'ok', jobs: [JOB] })
  expect(String(f.mock.calls[0][0])).toContain('/job-requests')
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.listJobRequests()).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.listJobRequests()).toEqual({ status: 'forbidden' })
})

test('getJobRequest: 200→ok; 404→not-found', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(200, JOB)))
  expect(await operatorClient.getJobRequest(7)).toEqual({ status: 'ok', job: JOB })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(404)))
  expect(await operatorClient.getJobRequest(7)).toEqual({ status: 'not-found' })
})

test('createJobRequest: posts the body and maps 201→ok', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(201, JOB))
  vi.stubGlobal('fetch', f)
  const body = { title: 'Aiuto cuoco', sector: 'Ristorazione', description: '', required_skills: ['cucina'], required_languages: [{ language: 'it', min_level: 'intermediate' as const }], required_availability: 'full_time' as const, involves_night_shifts: false, training_prerequisites: [] }
  const r = await operatorClient.createJobRequest(body)
  expect(r).toEqual({ status: 'ok', job: JOB })
  expect((f.mock.calls[0][1] as RequestInit).method).toBe('POST')
  expect(JSON.parse((f.mock.calls[0][1] as RequestInit).body as string)).toEqual(body)
})

test('runMatch: 200→ok with results; network→error', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(200, [MATCH])))
  expect(await operatorClient.runMatch(7)).toEqual({ status: 'ok', results: [MATCH] })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.runMatch(7)).toEqual({ status: 'error' })
})

const PROFILE = {
  pseudonym_id: 'P-4F2A',
  languages: [{ language: 'it', level: 'fluent' }],
  digital_literacy: 'intermediate',
  skills: [{ name: 'Cucina', kind: 'technical', evidence: 'certified' }],
  experiences: [{ role: 'Aiuto cuoco', sector: 'Ristorazione', duration_months: 24 }],
  aspiration: { fields_of_interest: ['Ristorazione'], availability: 'full_time', constraints: ['no_night_shifts'] },
  desired_training: [{ topic: 'HACCP' }],
  operational_notes: ['needs_language_support'],
}

test('searchProfiles sends only the set filters as query params, with Bearer', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, [PROFILE]))
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.searchProfiles({ availability: 'full_time', skill_query: 'cucina' })
  expect(r).toEqual({ status: 'ok', profiles: [PROFILE] })
  const url = String(f.mock.calls[0][0])
  expect(url).toContain('/profiles?')
  expect(url).toContain('availability=full_time')
  expect(url).toContain('skill_query=cucina')
  expect(url).not.toContain('language=')
  expect(url).not.toContain('note=')
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
})

test('searchProfiles with no filters hits /profiles (no query string) and maps 401/403', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.searchProfiles({})).toEqual({ status: 'ok', profiles: [] })
  expect(String(f.mock.calls[0][0])).toMatch(/\/profiles$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.searchProfiles({})).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.searchProfiles({})).toEqual({ status: 'forbidden' })
})

test('getProfile maps 200→ok and 404→not-found', async () => {
  setToken('tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(200, PROFILE)))
  expect(await operatorClient.getProfile('P-4F2A')).toEqual({ status: 'ok', profile: PROFILE })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(404)))
  expect(await operatorClient.getProfile('P-4F2A')).toEqual({ status: 'not-found' })
})

const OPS = [
  { id: 1, username: 'm.rossi', display_name: 'Maria Rossi', role: 'operator', is_active: true, must_change_password: false },
  { id: 3, username: 'a.verdi', display_name: 'Aldo Verdi', role: 'operator', is_active: false, must_change_password: false },
]

test('listOperators: 200→ok with Bearer; 401→unauthorized; 403→forbidden', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, OPS))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.listOperators()).toEqual({ status: 'ok', operators: OPS })
  expect(String(f.mock.calls[0][0])).toMatch(/\/operators$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.listOperators()).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.listOperators()).toEqual({ status: 'forbidden' })
})

test('createOperator: POSTs the body, maps 201→ok{created}', async () => {
  setToken('tok')
  const created = { operator: OPS[0], temp_password: '7Kq9-mZ2t-Rf4x' }
  const f = vi.fn().mockResolvedValue(res(201, created))
  vi.stubGlobal('fetch', f)
  const body = { username: 'm.rossi', display_name: 'Maria Rossi', role: 'operator' as const }
  expect(await operatorClient.createOperator(body)).toEqual({ status: 'ok', created })
  const [url, init] = f.mock.calls[0]
  expect(String(url)).toMatch(/\/operators$/)
  expect((init as RequestInit).method).toBe('POST')
  expect(JSON.parse((init as RequestInit).body as string)).toEqual(body)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.createOperator(body)).toEqual({ status: 'forbidden' })
})

test('disableOperator/enableOperator: POST to the right path, 204→ok', async () => {
  setToken('tok')
  const fd = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', fd)
  expect(await operatorClient.disableOperator(3)).toEqual({ status: 'ok' })
  expect(String(fd.mock.calls[0][0])).toMatch(/\/operators\/3\/disable$/)
  expect((fd.mock.calls[0][1] as RequestInit).method).toBe('POST')
  const fe = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', fe)
  expect(await operatorClient.enableOperator(3)).toEqual({ status: 'ok' })
  expect(String(fe.mock.calls[0][0])).toMatch(/\/operators\/3\/enable$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(401)))
  expect(await operatorClient.disableOperator(3)).toEqual({ status: 'unauthorized' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.enableOperator(3)).toEqual({ status: 'error' })
})

test('resetPassword: 200→ok{temp_password}; 403→forbidden', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, { temp_password: 'NEW-pw-123' }))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.resetPassword(1)).toEqual({ status: 'ok', temp_password: 'NEW-pw-123' })
  expect(String(f.mock.calls[0][0])).toMatch(/\/operators\/1\/reset-password$/)
  expect((f.mock.calls[0][1] as RequestInit).method).toBe('POST')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.resetPassword(1)).toEqual({ status: 'forbidden' })
})

test('getMetrics: 200→ok with Bearer; 403→forbidden; network→error', async () => {
  setToken('tok')
  const M = { total_profiles: 1, completed_profiles: 1, average_completeness: 1, total_job_requests: 0, matching_runs: 0 }
  const f = vi.fn().mockResolvedValue(res(200, M))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.getMetrics()).toEqual({ status: 'ok', metrics: M })
  expect(String(f.mock.calls[0][0])).toMatch(/\/metrics$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.getMetrics()).toEqual({ status: 'forbidden' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.getMetrics()).toEqual({ status: 'error' })
})

test('createExport POSTs {filters, reason} and maps 201→ok', async () => {
  setToken('tok')
  const REQ = { id: 1, requested_by: 'm.rossi', filters: { skill_query: 'cucina' }, reason: 'Azienda X', status: 'pending', decided_by: null, decided_at: null, decision_reason: null, created_at: '2026-07-27T10:00:00Z' }
  const f = vi.fn().mockResolvedValue(res(201, REQ))
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.createExport({ skill_query: 'cucina' }, 'Azienda X')
  expect(r).toEqual({ status: 'ok', request: REQ })
  const [url, init] = f.mock.calls[0]
  expect(String(url)).toMatch(/\/exports$/)
  expect((init as RequestInit).method).toBe('POST')
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ filters: { skill_query: 'cucina' }, reason: 'Azienda X' })
  expect((init!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
})

test('listExports and listPendingExports hit the right paths and map status', async () => {
  setToken('tok')
  const f1 = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f1)
  expect(await operatorClient.listExports()).toEqual({ status: 'ok', requests: [] })
  expect(String(f1.mock.calls[0][0])).toMatch(/\/exports$/)
  const f2 = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f2)
  expect(await operatorClient.listPendingExports()).toEqual({ status: 'ok', requests: [] })
  expect(String(f2.mock.calls[0][0])).toMatch(/\/exports\/pending$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.listPendingExports()).toEqual({ status: 'forbidden' })
})

test('approveExport 204→ok (POST /exports/{id}/approve with Bearer), 409→conflict, 404→not-found', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.approveExport(5)).toEqual({ status: 'ok' })
  const [url, init] = f.mock.calls[0]
  expect(String(url)).toMatch(/\/exports\/5\/approve$/)
  expect((init as RequestInit).method).toBe('POST')
  expect((init!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(409)))
  expect(await operatorClient.approveExport(5)).toEqual({ status: 'conflict' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(404)))
  expect(await operatorClient.approveExport(5)).toEqual({ status: 'not-found' })
})

test('denyExport POSTs {reason} and maps 204→ok', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(204))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.denyExport(5, 'fuori scopo')).toEqual({ status: 'ok' })
  const [url, init] = f.mock.calls[0]
  expect(String(url)).toMatch(/\/exports\/5\/deny$/)
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ reason: 'fuori scopo' })
})

test('downloadExport returns a Blob on 200, not-approved on 409, not-found on 404', async () => {
  setToken('tok')
  const blob = new Blob(['[]'], { type: 'application/json' })
  const f = vi.fn().mockResolvedValue({ status: 200, ok: true, blob: async () => blob })
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.downloadExport(5)
  expect(r).toEqual({ status: 'ok', blob })
  expect(String(f.mock.calls[0][0])).toMatch(/\/exports\/5\/download$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 409, ok: false, blob: async () => new Blob() }))
  expect(await operatorClient.downloadExport(5)).toEqual({ status: 'not-approved' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 404, ok: false, blob: async () => new Blob() }))
  expect(await operatorClient.downloadExport(5)).toEqual({ status: 'not-found' })
})

test('listAudit sends set filters + before/limit and maps 200→ok', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f)
  const r = await operatorClient.listAudit({ actor: 'm.rossi', action: 'profile_viewed', before: 51, limit: 50 })
  expect(r).toEqual({ status: 'ok', entries: [] })
  const url = String(f.mock.calls[0][0])
  expect(url).toContain('/audit?')
  expect(url).toContain('actor=m.rossi')
  expect(url).toContain('action=profile_viewed')
  expect(url).toContain('before=51')
  expect(url).toContain('limit=50')
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
})

test('listAudit with no filters hits /audit and maps 403/network', async () => {
  setToken('tok')
  const f = vi.fn().mockResolvedValue(res(200, []))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.listAudit({})).toEqual({ status: 'ok', entries: [] })
  expect(String(f.mock.calls[0][0])).toMatch(/\/audit$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.listAudit({})).toEqual({ status: 'forbidden' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.listAudit({})).toEqual({ status: 'error' })
})

test('verifyAudit hits /audit/verify and maps 200→ok{verification}, 403→forbidden', async () => {
  setToken('tok')
  const v = { ok: true, broken_at: null, reason: null }
  const f = vi.fn().mockResolvedValue(res(200, v))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.verifyAudit()).toEqual({ status: 'ok', verification: v })
  expect(String(f.mock.calls[0][0])).toMatch(/\/audit\/verify$/)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.verifyAudit()).toEqual({ status: 'forbidden' })
})

test('getOperatorActivity: 200→ok with Bearer; 403→forbidden; network→error', async () => {
  setToken('tok')
  const A = [{ actor: 'op1', profiles_viewed: 2, profiles_searched: 1, matchings_run: 0, exports_requested: 0, exports_downloaded: 0, last_active: '2026-07-27T10:00:00Z' }]
  const f = vi.fn().mockResolvedValue(res(200, A))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.getOperatorActivity()).toEqual({ status: 'ok', activity: A })
  expect(String(f.mock.calls[0][0])).toMatch(/\/operator-activity$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.getOperatorActivity()).toEqual({ status: 'forbidden' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.getOperatorActivity()).toEqual({ status: 'error' })
})

test('getSystemConfig: 200→ok with Bearer; 403→forbidden; network→error', async () => {
  setToken('tok')
  const C = { llm_model: 'qwen2.5-7b-instruct', llm_base_url: 'http://127.0.0.1:8080', llm_timeout: 120, llm_reachable: true, languages: ['it','en','fr','es','ar'], stt_model: 'large-v3-turbo', tts_voices: { it: true, en: true, fr: true, es: true, ar: false }, session_ttl_seconds: 43200, session_idle_seconds: 1800, max_failed_attempts: 5, lockout_seconds: 900 }
  const f = vi.fn().mockResolvedValue(res(200, C))
  vi.stubGlobal('fetch', f)
  expect(await operatorClient.getSystemConfig()).toEqual({ status: 'ok', config: C })
  expect(String(f.mock.calls[0][0])).toMatch(/\/system-config$/)
  expect((f.mock.calls[0][1]!.headers as Record<string, string>)['Authorization']).toBe('Bearer tok')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(403)))
  expect(await operatorClient.getSystemConfig()).toEqual({ status: 'forbidden' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await operatorClient.getSystemConfig()).toEqual({ status: 'error' })
})
