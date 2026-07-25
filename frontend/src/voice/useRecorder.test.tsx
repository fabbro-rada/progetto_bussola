import { renderHook, act, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { type ReactNode } from 'react'
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
