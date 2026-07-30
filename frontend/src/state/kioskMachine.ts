import type { Screen, StartResult, Step, StepKind, SubmitResult } from '../types'

export interface MachineState {
  screen: Screen
  language: string | null
  sessionToken: string | null
  step: Step | null
  lastAnswer: string | null
  pending: boolean
  // Set once the person enters a follow-up code (before start-followup is
  // called) and kept around so a transient `retry()` after a failed
  // start-followup calls startFollowup again instead of starting a fresh
  // first interview (§4 — the person should not have to re-key their code).
  followupToken: string | null
}

export const initialState: MachineState = {
  screen: 'language',
  language: null,
  sessionToken: null,
  step: null,
  lastAnswer: null,
  pending: false,
  followupToken: null,
}

export type Action =
  | { type: 'selectLanguage'; language: string }
  | { type: 'declineConsent' }
  | { type: 'starting' }
  | { type: 'started'; result: StartResult }
  | { type: 'submitting'; answer: string }
  | { type: 'submitted'; result: SubmitResult }
  | { type: 'stop' }
  // Additive follow-up path (Sottosistema 29, Task 6). A discreet link on the
  // language picker opens a token+language entry screen; submitting it moves
  // to a follow-up-specific consent/recap (voluntariness, §4) BEFORE any
  // network call is made. Declining reuses `declineConsent` (same reset).
  | { type: 'openFollowupEntry' }
  | { type: 'submitFollowupCredentials'; token: string; language: string }
  | { type: 'startedFollowup'; result: StartResult }

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
      if (!state.pending) return state
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized', pending: false }
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable', pending: false }
      return { ...state, sessionToken: r.sessionToken, step: r.step, screen: screenFor(r.step.kind), pending: false }
    }
    case 'submitting':
      return { ...state, lastAnswer: action.answer, pending: true }
    case 'submitted': {
      if (!state.pending) return state
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized', pending: false }
      if (r.status === 'session-expired') return initialState
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable', pending: false }
      return { ...state, step: r.step, screen: screenFor(r.step.kind), pending: false }
    }
    case 'stop':
      return initialState
    case 'openFollowupEntry':
      return { ...state, screen: 'followupEntry' }
    case 'submitFollowupCredentials':
      return { ...state, followupToken: action.token, language: action.language, screen: 'followupConsent' }
    case 'startedFollowup': {
      if (!state.pending) return state
      const r = action.result
      // Fail-closed: an invalid/used/expired token and a genuinely down
      // backend are indistinguishable to the person and MUST NOT be — the
      // 'unauthorized' screen ("this station is not authorized") would leak
      // that something about the person's code specifically was rejected and
      // would misdirect them (and operators) toward a device-auth problem
      // that doesn't exist. Both statuses route to the same gentle,
      // no-detail "unavailable" screen instead (brief's Step 3).
      if (r.status !== 'ok') return { ...state, screen: 'unavailable', pending: false }
      return { ...state, sessionToken: r.sessionToken, step: r.step, screen: screenFor(r.step.kind), pending: false }
    }
    default:
      return state
  }
}
