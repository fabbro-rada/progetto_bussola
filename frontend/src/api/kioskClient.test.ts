import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { kioskClient } from './kioskClient'

function mockFetch(status: number, body?: unknown) {
  return vi.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response)
}

function mockFetchBadJson(status = 200) {
  return vi.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    json: async () => {
      throw new Error('bad json')
    },
  } as unknown as Response)
}

beforeEach(() => vi.stubGlobal('fetch', mockFetch(200, { session_token: 't', step: { kind: 'question', text: 'Q' } })))
afterEach(() => vi.unstubAllGlobals())

// start(startCode, language) (Task 8, re-identification): the kiosk no
// longer self-starts anonymously -- it now consumes a one-time start code
// an operator gave the person, mirroring startFollowup's request shape
// exactly (see below).
test('start maps 200 to ok, posts the start code + language, and sends the kiosk token header', async () => {
  const fetchMock = mockFetch(200, { session_token: 'tok', step: { kind: 'question', text: 'Ciao' } })
  vi.stubGlobal('fetch', fetchMock)
  const res = await kioskClient.startInterview('S-CODE1', 'it')
  expect(res).toEqual({ status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Ciao' } })
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/kiosk/interview/start')
  expect((init as RequestInit).method).toBe('POST')
  expect((init!.headers as Record<string, string>)['X-Kiosk-Token']).toBeDefined()
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ start_code: 'S-CODE1', language: 'it' })
})

test('start maps 401 (invalid/used/expired start code, or a bad device token) to unauthorized', async () => {
  vi.stubGlobal('fetch', mockFetch(401))
  expect(await kioskClient.startInterview('S-CODE1', 'it')).toEqual({ status: 'unauthorized' })
})

test('start maps a thrown fetch (backend down) to unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
  expect(await kioskClient.startInterview('S-CODE1', 'it')).toEqual({ status: 'unavailable' })
})

test('start maps a 2xx response with an unparsable body to unavailable', async () => {
  vi.stubGlobal('fetch', mockFetchBadJson(200))
  expect(await kioskClient.startInterview('S-CODE1', 'it')).toEqual({ status: 'unavailable' })
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

test('submit maps a 2xx response with an unparsable body to unavailable', async () => {
  vi.stubGlobal('fetch', mockFetchBadJson(200))
  expect(await kioskClient.submitAnswer('tok', 'x')).toEqual({ status: 'unavailable' })
})

// startFollowup(token, language): mirrors startInterview's fail-closed shape
// exactly, but ALSO sends the person-chosen language (Task 6 correction —
// StartFollowupRequest carries both `token` and `language`, same field
// constraints as `/start`). A follow-up token carries no language of its
// own (§5), so dropping this would silently force the person back to
// Italian regardless of what they picked.
test('startFollowup posts both the token and the language, and sends the kiosk token header', async () => {
  const fetchMock = mockFetch(200, { session_token: 'tok', step: { kind: 'question', text: 'Bentornato' } })
  vi.stubGlobal('fetch', fetchMock)
  const res = await kioskClient.startFollowup('follow-tok', 'ar')
  expect(res).toEqual({ status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Bentornato' } })
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/kiosk/interview/start-followup')
  expect((init as RequestInit).method).toBe('POST')
  expect((init!.headers as Record<string, string>)['X-Kiosk-Token']).toBeDefined()
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ token: 'follow-tok', language: 'ar' })
})

test('startFollowup maps 401 (invalid/used/expired token) to unauthorized', async () => {
  vi.stubGlobal('fetch', mockFetch(401))
  expect(await kioskClient.startFollowup('bad-tok', 'it')).toEqual({ status: 'unauthorized' })
})

test('startFollowup maps a thrown fetch (backend down) to unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
  expect(await kioskClient.startFollowup('tok', 'it')).toEqual({ status: 'unavailable' })
})

test('startFollowup maps a 2xx response with an unparsable body to unavailable', async () => {
  vi.stubGlobal('fetch', mockFetchBadJson(200))
  expect(await kioskClient.startFollowup('tok', 'it')).toEqual({ status: 'unavailable' })
})
