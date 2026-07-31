import { renderHook, act, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { StrictMode, type ReactNode } from 'react'
import { useRecorder } from './useRecorder'
import { VoiceProvider } from './VoiceContext'
import { makeVoiceClient } from '../test/fakeClient'
import { stubMedia, MockMediaRecorder } from '../test/media'
import type { VoiceClient } from './voiceClient'

function wrapper(client: VoiceClient) {
  return ({ children }: { children: ReactNode }) => (
    <VoiceProvider language="it" client={client}>
      {children}
    </VoiceProvider>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  MockMediaRecorder.instances = []
})

test('record → stop → transcribe fills text via onText and returns to idle', async () => {
  stubMedia(true)
  const client = makeVoiceClient({ transcript: 'so cucinare' })
  const onText = vi.fn()
  const { result } = renderHook(() => useRecorder({ onText }), { wrapper: wrapper(client) })
  await act(async () => {
    await result.current.start()
  })
  expect(result.current.state).toBe('recording')
  await act(async () => {
    result.current.stop()
  })
  await waitFor(() => expect(onText).toHaveBeenCalledWith('so cucinare'))
  expect(result.current.state).toBe('idle')
})

test('survives React StrictMode remount: start() still reaches recording', async () => {
  // Regression: the mount effect only had a cleanup, so StrictMode's
  // mount→unmount→remount (dev) left mountedRef stuck false, and start() bailed
  // after getUserMedia — mic prompt showed, nothing recorded. Rendering under
  // <StrictMode> reproduces the double-mount; the fix resets mountedRef on mount.
  stubMedia(true)
  const client = makeVoiceClient({ transcript: 'so cucinare' })
  const onText = vi.fn()
  const strictWrapper = ({ children }: { children: ReactNode }) => (
    <StrictMode>
      <VoiceProvider language="it" client={client}>
        {children}
      </VoiceProvider>
    </StrictMode>
  )
  const { result } = renderHook(() => useRecorder({ onText }), { wrapper: strictWrapper })
  await act(async () => {
    await result.current.start()
  })
  expect(result.current.state).toBe('recording') // was stuck at 'requesting' before the fix
})

test('permission denied → state denied, onText never called', async () => {
  stubMedia(false)
  const onText = vi.fn()
  const { result } = renderHook(() => useRecorder({ onText }), { wrapper: wrapper(makeVoiceClient({})) })
  await act(async () => {
    await result.current.start()
  })
  expect(result.current.state).toBe('denied')
  expect(onText).not.toHaveBeenCalled()
})

test('transcribe unavailable (503) → state unavailable', async () => {
  stubMedia(true)
  const client = makeVoiceClient({}) // transcript undefined → unavailable
  const onText = vi.fn()
  const { result } = renderHook(() => useRecorder({ onText }), { wrapper: wrapper(client) })
  await act(async () => {
    await result.current.start()
  })
  await act(async () => {
    result.current.stop()
  })
  await waitFor(() => expect(result.current.state).toBe('unavailable'))
  expect(onText).not.toHaveBeenCalled()
})

test('re-entrant start() while requesting/recording is ignored (no orphaned stream)', async () => {
  stubMedia(true)
  const onText = vi.fn()
  const { result } = renderHook(() => useRecorder({ onText }), {
    wrapper: wrapper(makeVoiceClient({ transcript: 'x' })),
  })
  await act(async () => {
    await Promise.all([result.current.start(), result.current.start()])
  })
  expect(MockMediaRecorder.instances.length).toBe(1)
})

test('unmount mid-capture releases the mic (stops the stream tracks)', async () => {
  const trackStop = vi.fn()
  const stream = { getTracks: () => [{ stop: trackStop }] } as unknown as MediaStream
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } })
  vi.stubGlobal('MediaRecorder', MockMediaRecorder as unknown as typeof MediaRecorder)
  const { result, unmount } = renderHook(() => useRecorder({ onText: vi.fn() }), {
    wrapper: wrapper(makeVoiceClient({ transcript: 'x' })),
  })
  await act(async () => {
    await result.current.start()
  })
  unmount()
  expect(trackStop).toHaveBeenCalled()
})

test('MediaRecorder constructor throwing releases the mic, sets unavailable, and does not get stuck busy', async () => {
  // Last «mic-hot» edge (STATO_TECNICO §14): getUserMedia succeeded, but the
  // MediaRecorder constructor throws. The mic must NOT stay hot, and the
  // re-entrancy guard must reset so a later attempt can proceed.
  const trackStop = vi.fn()
  const stream = { getTracks: () => [{ stop: trackStop }] } as unknown as MediaStream
  let ctorCalls = 0
  class ThrowingThenOk {
    static instances: ThrowingThenOk[] = []
    state: 'inactive' | 'recording' = 'inactive'
    ondataavailable: ((e: { data: Blob }) => void) | null = null
    onstop: (() => void) | null = null
    mimeType = 'audio/webm'
    constructor(public s: MediaStream) {
      ctorCalls += 1
      if (ctorCalls === 1) throw new Error('MediaRecorder construction failed')
      ThrowingThenOk.instances.push(this)
    }
    start() {
      this.state = 'recording'
    }
    stop() {
      this.state = 'inactive'
    }
  }
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } })
  vi.stubGlobal('MediaRecorder', ThrowingThenOk as unknown as typeof MediaRecorder)
  const { result } = renderHook(() => useRecorder({ onText: vi.fn() }), {
    wrapper: wrapper(makeVoiceClient({ transcript: 'x' })),
  })

  // First attempt: the constructor throws.
  await act(async () => {
    await result.current.start()
  })
  expect(result.current.state).toBe('unavailable') // not stuck at 'requesting'
  expect(trackStop).toHaveBeenCalled() // mic released, not left hot

  // Second attempt: proves busyRef was reset (the guard did not permanently block).
  await act(async () => {
    await result.current.start()
  })
  expect(result.current.state).toBe('recording')

  vi.unstubAllGlobals()
})

test('MediaRecorder.start() throwing also releases the mic and degrades to unavailable', async () => {
  // The guard covers rec.start() too, not just the constructor: same mic-hot
  // failure mode. This test fails if start() is ever moved outside the try.
  const trackStop = vi.fn()
  const stream = { getTracks: () => [{ stop: trackStop }] } as unknown as MediaStream
  class StartThrows {
    state: 'inactive' | 'recording' = 'inactive'
    ondataavailable: ((e: { data: Blob }) => void) | null = null
    onstop: (() => void) | null = null
    mimeType = 'audio/webm'
    constructor(public s: MediaStream) {}
    start() {
      throw new Error('start() failed')
    }
    stop() {
      this.state = 'inactive'
    }
  }
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } })
  vi.stubGlobal('MediaRecorder', StartThrows as unknown as typeof MediaRecorder)
  const { result } = renderHook(() => useRecorder({ onText: vi.fn() }), {
    wrapper: wrapper(makeVoiceClient({ transcript: 'x' })),
  })
  await act(async () => {
    await result.current.start()
  })
  expect(result.current.state).toBe('unavailable')
  expect(trackStop).toHaveBeenCalled() // mic released even though start() threw
  vi.unstubAllGlobals()
})

test('unmount while the permission prompt is pending releases the mic and does not start', async () => {
  const trackStop = vi.fn()
  const stream = { getTracks: () => [{ stop: trackStop }] } as unknown as MediaStream
  let resolveGum!: (s: MediaStream) => void
  vi.stubGlobal('navigator', {
    mediaDevices: { getUserMedia: vi.fn().mockReturnValue(new Promise<MediaStream>((r) => { resolveGum = r })) },
  })
  vi.stubGlobal('MediaRecorder', MockMediaRecorder as unknown as typeof MediaRecorder)
  const { result, unmount } = renderHook(() => useRecorder({ onText: vi.fn() }), {
    wrapper: wrapper(makeVoiceClient({ transcript: 'x' })),
  })
  let startPromise!: Promise<void>
  act(() => {
    startPromise = result.current.start()
  })
  unmount()
  await act(async () => {
    resolveGum(stream)
    await startPromise
  })
  expect(trackStop).toHaveBeenCalled()
  expect(MockMediaRecorder.instances).toHaveLength(0)
  vi.unstubAllGlobals()
})
