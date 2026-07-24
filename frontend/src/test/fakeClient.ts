import type { KioskClient, StartResult, Step, SubmitResult } from '../types'
import type { VoiceClient } from '../voice/voiceClient'

// Deterministic fake: `start` returns startResult; each `submit` returns the
// next scripted SubmitResult. Synthetic data only (§9).
export function makeFakeClient(opts: {
  start?: StartResult
  submits?: SubmitResult[]
}): KioskClient & { calls: { answers: string[] } } {
  const calls = { answers: [] as string[] }
  let i = 0
  const start: StartResult = opts.start ?? { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } }
  const submits = opts.submits ?? []
  return {
    calls,
    async startInterview() {
      return start
    },
    async submitAnswer(_token: string, answer: string) {
      calls.answers.push(answer)
      return submits[i++] ?? { status: 'ok', step: { kind: 'completed', text: 'fine' } }
    },
  }
}

export const step = (kind: Step['kind'], text: string): Step => ({ kind, text })

// Silent default for component tests: no audio, dictation unavailable.
export const noopVoiceClient: VoiceClient = {
  async transcribe() {
    return { status: 'unavailable' }
  },
  async synthesize() {
    return null
  },
}

// Configurable fake for voice tests. `transcript` → transcribe result text;
// `audio` → a Blob for synthesize (null = 204/no audio).
export function makeVoiceClient(opts: { transcript?: string; audio?: Blob | null } = {}): VoiceClient & {
  calls: { transcribe: number; synthesize: Array<{ text: string; language: string }> }
} {
  const calls = { transcribe: 0, synthesize: [] as Array<{ text: string; language: string }> }
  return {
    calls,
    async transcribe() {
      calls.transcribe++
      return opts.transcript !== undefined
        ? { status: 'ok', text: opts.transcript }
        : { status: 'unavailable' }
    },
    async synthesize(text: string, language: string) {
      calls.synthesize.push({ text, language })
      return opts.audio ?? null
    },
  }
}
