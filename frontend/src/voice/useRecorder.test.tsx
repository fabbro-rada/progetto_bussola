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
