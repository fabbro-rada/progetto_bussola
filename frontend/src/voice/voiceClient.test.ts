import { afterEach, expect, test, vi } from 'vitest'
import { voiceClient } from './voiceClient'

afterEach(() => vi.unstubAllGlobals())

test('transcribe posts multipart audio+language with the kiosk token and maps 200', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ text: 'so cucinare' }),
  } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const blob = new Blob(['x'], { type: 'audio/webm' })
  const res = await voiceClient.transcribe(blob, 'it')
  expect(res).toEqual({ status: 'ok', text: 'so cucinare' })
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/kiosk/voice/transcribe')
  expect((init!.headers as Record<string, string>)['X-Kiosk-Token']).toBeDefined()
  const body = (init as RequestInit).body as FormData
  expect(body).toBeInstanceOf(FormData)
  expect(body.get('language')).toBe('it')
  expect(body.get('audio')).toBeInstanceOf(Blob)
})

test('transcribe maps 503 and a thrown fetch to unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 } as Response))
  expect(await voiceClient.transcribe(new Blob(), 'it')).toEqual({ status: 'unavailable' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await voiceClient.transcribe(new Blob(), 'it')).toEqual({ status: 'unavailable' })
})

test('synthesize posts json and returns the audio blob on 200', async () => {
  const audio = new Blob(['wav'], { type: 'audio/wav' })
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    blob: async () => audio,
  } as unknown as Response)
  vi.stubGlobal('fetch', fetchMock)
  const res = await voiceClient.synthesize('Sai cucinare?', 'it')
  expect(res).toBe(audio)
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/kiosk/voice/synthesize')
  expect((init!.headers as Record<string, string>)['X-Kiosk-Token']).toBeDefined()
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ text: 'Sai cucinare?', language: 'it' })
})

test('synthesize maps 204 and a thrown fetch to null', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 204 } as Response))
  expect(await voiceClient.synthesize('x', 'it')).toBeNull()
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await voiceClient.synthesize('x', 'it')).toBeNull()
})
