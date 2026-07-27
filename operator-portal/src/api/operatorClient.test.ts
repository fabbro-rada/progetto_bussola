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
