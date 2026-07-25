import { vi } from 'vitest'

// Browser media APIs are absent in jsdom; this stubs getUserMedia + MediaRecorder.
export class MockMediaRecorder {
  static instances: MockMediaRecorder[] = []
  state: 'inactive' | 'recording' = 'inactive'
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  mimeType = 'audio/webm'
  constructor(public stream: MediaStream) {
    MockMediaRecorder.instances.push(this)
  }
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['chunk'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

export function stubMedia(granted = true): void {
  const stream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream
  vi.stubGlobal('navigator', {
    mediaDevices: {
      getUserMedia: granted
        ? vi.fn().mockResolvedValue(stream)
        : vi.fn().mockRejectedValue(new Error('denied')),
    },
  })
  vi.stubGlobal('MediaRecorder', MockMediaRecorder as unknown as typeof MediaRecorder)
}
