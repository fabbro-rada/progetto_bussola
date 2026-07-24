import { renderHook, act } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { useSpeech } from './useSpeech'
import { makeVoiceClient } from '../test/fakeClient'

class MockAudio {
  static instances: MockAudio[] = []
  static deferPlay = false
  onended: (() => void) | null = null
  paused = true
  playReject: ((e: unknown) => void) | null = null
  constructor(public src: string) {
    MockAudio.instances.push(this)
  }
  play() {
    this.paused = false
    if (MockAudio.deferPlay) {
      return new Promise<void>((_res, rej) => {
        this.playReject = rej
      })
    }
    return Promise.resolve()
  }
  pause() {
    this.paused = true
    // Note: does NOT auto-reject playReject here. In real browsers, the
    // rejection of a pending play() promise after pause() lands on its own
    // timing (not necessarily synchronous with pause()), so tests trigger
    // it explicitly to get deterministic, worst-case ordering.
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  MockAudio.instances = []
  MockAudio.deferPlay = false
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

test('a superseded play whose audio.play() rejects (after a newer play has taken over) does not clobber the current audio', async () => {
  stubAudio()
  MockAudio.deferPlay = true
  let resolveA!: (b: Blob | null) => void
  const client = {
    transcribe: async () => ({ status: 'unavailable' as const }),
    synthesize: vi
      .fn()
      .mockImplementationOnce(() => new Promise<Blob | null>((r) => { resolveA = r }))
      .mockImplementationOnce(() => Promise.resolve(new Blob(['b']))),
  }
  const { result } = renderHook(() => useSpeech(client))

  // Start A: synthesize is pending.
  let pA!: Promise<void>
  act(() => { pA = result.current.play('A', 'it') })

  // A's synthesize resolves -> A creates audioA and calls audioA.play(), which
  // stays pending (deferPlay) — as if the browser hasn't settled it yet.
  await act(async () => {
    resolveA(new Blob(['a']))
    await Promise.resolve()
    await Promise.resolve()
  })
  expect(MockAudio.instances).toHaveLength(1)
  const audioA = MockAudio.instances[0]
  expect(audioA.playReject).not.toBeNull()

  // Now a newer play('B') runs to full completion: stop() pauses audioA
  // (queue-of-one), B's synthesize/audio.play() both resolve, B becomes the
  // live, speaking generation. audioA.play() is STILL pending throughout.
  MockAudio.deferPlay = false // B's audio.play() resolves normally
  await act(async () => {
    await result.current.play('B', 'it')
  })
  const audioB = MockAudio.instances[1]
  expect(audioB).toBeDefined()
  expect(result.current.speaking).toBe(true) // B is the current, live generation

  // Only now does audioA's stale play() promise reject — simulating a real
  // browser settling an interrupted play() well after a newer play() has
  // already taken over. This drives play('A')'s catch branch.
  await act(async () => {
    audioA.playReject!(new DOMException('paused'))
    await pA.catch(() => {})
  })

  // The unguarded catch would null audioRef/urlRef and set speaking=false
  // here, even though B — not A — is the current, live generation: stop()
  // would then have nothing to pause, and B would keep playing forever.
  act(() => result.current.stop())
  expect(audioB.paused).toBe(true) // stop() must still control B (not clobbered by A's stale catch)
  expect(result.current.speaking).toBe(false)
})
