import type { Screen, StartResult, Step, StepKind, SubmitResult } from '../types'

export interface MachineState {
  screen: Screen
  language: string | null
  sessionToken: string | null
  step: Step | null
  lastAnswer: string | null
  pending: boolean
}

export const initialState: MachineState = {
  screen: 'language',
  language: null,
  sessionToken: null,
  step: null,
  lastAnswer: null,
  pending: false,
}

export type Action =
  | { type: 'selectLanguage'; language: string }
  | { type: 'declineConsent' }
  | { type: 'starting' }
  | { type: 'started'; result: StartResult }
  | { type: 'submitting'; answer: string }
  | { type: 'submitted'; result: SubmitResult }
  | { type: 'stop' }

// Step kinds map 1:1 to screens of the same name.
function screenFor(kind: StepKind): Screen {
  return kind
}

export function reducer(state: MachineState, action: Action): MachineState {
  switch (action.type) {
    case 'selectLanguage':
      return { ...state, language: action.language, screen: 'consent' }
    case 'declineConsent':
      return initialState
    case 'starting':
      return { ...state, pending: true }
    case 'started': {
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized', pending: false }
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable', pending: false }
      return { ...state, sessionToken: r.sessionToken, step: r.step, screen: screenFor(r.step.kind), pending: false }
    }
    case 'submitting':
      return { ...state, lastAnswer: action.answer, pending: true }
    case 'submitted': {
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized', pending: false }
      if (r.status === 'session-expired') return initialState
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable', pending: false }
      return { ...state, step: r.step, screen: screenFor(r.step.kind), pending: false }
    }
    case 'stop':
      return initialState
    default:
      return state
  }
}
