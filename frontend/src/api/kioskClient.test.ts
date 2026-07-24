import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { kioskClient } from './kioskClient'

function mockFetch(status: number, body?: unknown) {
  return vi.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response)
}

beforeEach(() => vi.stubGlobal('fetch', mockFetch(200, { session_token: 't', step: { kind: 'question', text: 'Q' } })))
afterEach(() => vi.unstubAllGlobals())

test('start maps 200 to ok and sends the kiosk token header', async () => {
  const fetchMock = mockFetch(200, { session_token: 'tok', step: { kind: 'question', text: 'Ciao' } })
  vi.stubGlobal('fetch', fetchMock)
  const res = await kioskClient.startInterview('it')
  expect(res).toEqual({ status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Ciao' } })
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/kiosk/interview/start')
  expect((init as RequestInit).method).toBe('POST')
  expect((init!.headers as Record<string, string>)['X-Kiosk-Token']).toBeDefined()
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ language: 'it' })
})

test('start maps 401 to unauthorized', async () => {
  vi.stubGlobal('fetch', mockFetch(401))
  expect(await kioskClient.startInterview('it')).toEqual({ status: 'unauthorized' })
})

test('start maps a thrown fetch (backend down) to unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
  expect(await kioskClient.startInterview('it')).toEqual({ status: 'unavailable' })
})

test('submit maps 200 to ok with the step', async () => {
  vi.stubGlobal('fetch', mockFetch(200, { step: { kind: 'summary', text: 'Riepilogo' } }))
  expect(await kioskClient.submitAnswer('tok', 'ciao')).toEqual({ status: 'ok', step: { kind: 'summary', text: 'Riepilogo' } })
})

test('submit maps 404 to session-expired and 401 to unauthorized', async () => {
  vi.stubGlobal('fetch', mockFetch(404))
  expect(await kioskClient.submitAnswer('tok', 'x')).toEqual({ status: 'session-expired' })
  vi.stubGlobal('fetch', mockFetch(401))
  expect(await kioskClient.submitAnswer('tok', 'x')).toEqual({ status: 'unauthorized' })
})

test('submit maps 5xx to unavailable', async () => {
  vi.stubGlobal('fetch', mockFetch(503))
  expect(await kioskClient.submitAnswer('tok', 'x')).toEqual({ status: 'unavailable' })
})
