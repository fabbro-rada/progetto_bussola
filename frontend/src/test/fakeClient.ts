import type { KioskClient, StartResult, Step, SubmitResult } from '../types'
import type { VoiceClient } from '../voice/voiceClient'

// Deterministic fake: `start` returns startResult; each `submit` returns the
// next scripted SubmitResult. Synthetic data only (§9).
// `startFollowup` defaults to the same `start` result unless overridden, so
// existing callers that only care about the first-interview path don't need
// to know about the follow-up option. `calls.followup` records exactly what
// was sent, so tests can assert BOTH the token and the language reached the
// client (the language must never be silently dropped — see Task 6 brief).
// `calls.start` mirrors that for the first-interview path (Task 8 review
// fix): records the start code + language `startInterview` was actually
// called with, so tests can catch a swapped-argument regression or a
// stale/empty code slipping through `App.tsx`'s `start()`.
export function makeFakeClient(opts: {
  start?: StartResult
  submits?: SubmitResult[]
  startFollowup?: StartResult
}): KioskClient & {
  calls: {
    answers: string[]
    start: { code: string; language: string } | null
    followup: { token: string; language: string } | null
  }
} {
  const calls = {
    answers: [] as string[],
    start: null as { code: string; language: string } | null,
    followup: null as { token: string; language: string } | null,
  }
  let i = 0
  const start: StartResult = opts.start ?? { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } }
  const submits = opts.submits ?? []
  return {
    calls,
    async startInterview(code: string, language: string) {
      calls.start = { code, language }
      return start
    },
    async submitAnswer(_token: string, answer: string) {
      calls.answers.push(answer)
      return submits[i++] ?? { status: 'ok', step: { kind: 'completed', text: 'fine' } }
    },
    async startFollowup(token: string, language: string) {
      calls.followup = { token, language }
      return opts.startFollowup ?? start
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
