import type { KioskClient, StartResult, Step, SubmitResult } from '../types'

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
