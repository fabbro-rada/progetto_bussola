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
