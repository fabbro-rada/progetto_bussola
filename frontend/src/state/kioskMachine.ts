import type { Screen, StartResult, Step, StepKind, SubmitResult } from '../types'

export interface MachineState {
  screen: Screen
  language: string | null
  sessionToken: string | null
  step: Step | null
  lastAnswer: string | null
}

export const initialState: MachineState = {
  screen: 'language',
  language: null,
  sessionToken: null,
  step: null,
  lastAnswer: null,
}

export type Action =
  | { type: 'selectLanguage'; language: string }
  | { type: 'declineConsent' }
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
    case 'started': {
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized' }
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable' }
      return { ...state, sessionToken: r.sessionToken, step: r.step, screen: screenFor(r.step.kind) }
    }
    case 'submitting':
      return { ...state, lastAnswer: action.answer }
    case 'submitted': {
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized' }
      if (r.status === 'session-expired') return initialState
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable' }
      return { ...state, step: r.step, screen: screenFor(r.step.kind) }
    }
    case 'stop':
      return initialState
    default:
      return state
  }
}
