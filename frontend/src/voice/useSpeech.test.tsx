import { renderHook, act } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { useSpeech } from './useSpeech'
import { makeVoiceClient } from '../test/fakeClient'

class MockAudio {
  static instances: MockAudio[] = []
  onended: (() => void) | null = null
  paused = true
  constructor(public src: string) {
    MockAudio.instances.push(this)
  }
  play() {
    this.paused = false
    return Promise.resolve()
  }
  pause() {
    this.paused = true
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  MockAudio.instances = []
})

function stubAudio() {
  vi.stubGlobal('Audio', MockAudio as unknown as typeof Audio)
  vi.stubGlobal('URL', { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })
}

test('play synthesizes and plays the returned audio', async () => {
  stubAudio()
  const client = makeVoiceClient({ audio: new Blob(['wav']) })
  const { result } = renderHook(() => useSpeech(client))
  await act(async () => {
    await result.current.play('Sai cucinare?', 'it')
  })
  expect(client.calls.synthesize).toEqual([{ text: 'Sai cucinare?', language: 'it' }])
  expect(MockAudio.instances).toHaveLength(1)
  expect(MockAudio.instances[0].paused).toBe(false)
  expect(result.current.speaking).toBe(true)
})

test('play with no audio (204) is a silent no-op — no Audio created', async () => {
  stubAudio()
  const client = makeVoiceClient({ audio: null })
  const { result } = renderHook(() => useSpeech(client))
  await act(async () => {
    await result.current.play('x', 'it')
  })
  expect(MockAudio.instances).toHaveLength(0)
  expect(result.current.speaking).toBe(false)
})

test('stop pauses the current audio', async () => {
  stubAudio()
  const client = makeVoiceClient({ audio: new Blob(['wav']) })
  const { result } = renderHook(() => useSpeech(client))
  await act(async () => {
    await result.current.play('x', 'it')
  })
  act(() => result.current.stop())
  expect(MockAudio.instances[0].paused).toBe(true)
  expect(result.current.speaking).toBe(false)
})

test('stop revokes the object URL to avoid leaking blobs on early stop', async () => {
  vi.stubGlobal('Audio', MockAudio as unknown as typeof Audio)
  const revoke = vi.fn()
  vi.stubGlobal('URL', { createObjectURL: () => 'blob:x', revokeObjectURL: revoke })
  const client = makeVoiceClient({ audio: new Blob(['wav']) })
  const { result } = renderHook(() => useSpeech(client))
  await act(async () => {
    await result.current.play('x', 'it')
  })
  act(() => result.current.stop())
  expect(revoke).toHaveBeenCalledWith('blob:x')
})

test('a later play cancels an earlier in-flight synthesize (queue-of-one)', async () => {
  stubAudio()
  let resolveA!: (b: Blob | null) => void
  let resolveB!: (b: Blob | null) => void
  const client = {
    transcribe: async () => ({ status: 'unavailable' as const }),
    synthesize: vi
      .fn()
      .mockImplementationOnce(() => new Promise<Blob | null>((r) => { resolveA = r }))
      .mockImplementationOnce(() => new Promise<Blob | null>((r) => { resolveB = r })),
  }
  const { result } = renderHook(() => useSpeech(client))
  let pA!: Promise<void>
  let pB!: Promise<void>
  act(() => { pA = result.current.play('A', 'it') })
  act(() => { pB = result.current.play('B', 'it') })
  await act(async () => { resolveB(new Blob(['b'])); await pB })
  await act(async () => { resolveA(new Blob(['a'])); await pA })
  expect(MockAudio.instances).toHaveLength(1)
})

test('synthesize resolving after stop() creates no audio', async () => {
  stubAudio()
  let resolveA!: (b: Blob | null) => void
  const client = {
    transcribe: async () => ({ status: 'unavailable' as const }),
    synthesize: () => new Promise<Blob | null>((r) => { resolveA = r }),
  }
  const { result } = renderHook(() => useSpeech(client))
  let pA!: Promise<void>
  act(() => { pA = result.current.play('A', 'it') })
  act(() => { result.current.stop() })
  await act(async () => { resolveA(new Blob(['a'])); await pA })
  expect(MockAudio.instances).toHaveLength(0)
})
