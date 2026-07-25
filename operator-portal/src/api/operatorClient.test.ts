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
