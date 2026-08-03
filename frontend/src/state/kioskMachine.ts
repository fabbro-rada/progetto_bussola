import type { Screen, StartResult, Step, StepKind, SubmitResult } from '../types'

export interface MachineState {
  screen: Screen
  language: string | null
  sessionToken: string | null
  step: Step | null
  // Monotonic counter bumped every time a NEW step is set. Used as a React key
  // for the step screens so each new step remounts a fresh input component —
  // otherwise a summary→summary transition (a correction) reuses the same
  // ConfirmCorrect and keeps showing its "correcting" text box instead of the
  // Sì/No choice.
  stepSeq: number
  // Text of the last prompt the person was answering (question/summary/
  // clarification). Kept across a refusal — whose own step carries only the
  // refusal notice — so the refusal screen can re-show the actual question.
  lastPrompt: string | null
  lastAnswer: string | null
  pending: boolean
  // Set once the person enters a follow-up code (before start-followup is
  // called) and kept around so a transient `retry()` after a failed
  // start-followup calls startFollowup again instead of starting a fresh
  // first interview (§4 — the person should not have to re-key their code).
  followupToken: string | null
  // Re-identification (Task 8): the kiosk no longer self-starts anonymously.
  // Set once the person enters the one-time start code an operator gave
  // them (before `start` is called) and kept around for the same retry
  // reason as `followupToken` above.
  startCode: string | null
}

export const initialState: MachineState = {
  screen: 'language',
  language: null,
  sessionToken: null,
  step: null,
  stepSeq: 0,
  lastPrompt: null,
  lastAnswer: null,
  pending: false,
  followupToken: null,
  startCode: null,
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
  // Fix round 1 (§4 accessibility): a tile tap on the follow-up entry screen
  // already calls `applyLanguage()` (updates i18n text + document dir), but
  // that alone does NOT retarget voice narration — `VoiceProvider`'s
  // `language` comes from THIS state's `language` field, which otherwise
  // stays whatever it was until `submitFollowupCredentials` fires on final
  // submit. Without this, a person who taps "Arabic" and then "Ascolta" on
  // this very screen would hear Italian narration. Screen is left untouched
  // (still `followupEntry`) — only the field the voice/dir side effects key
  // off changes, mirroring what `selectLanguage` does for `language` minus
  // the screen transition.
  | { type: 'previewFollowupLanguage'; language: string }
  // Start-code path (re-identification, Task 8): the FIRST-interview entry
  // point, right after LanguagePicker (so the language is already chosen —
  // the start-code screen only captures the code, no second language pick).
  | { type: 'submitStartCode'; code: string }

// Step kinds map 1:1 to screens of the same name.
function screenFor(kind: StepKind): Screen {
  return kind
}

// The prompts the person actively answers; a refusal keeps the previous one so
// the refusal screen can re-show the question that was asked.
const PROMPT_KINDS: readonly StepKind[] = ['question', 'summary', 'clarification']
function nextPrompt(step: Step, prev: string | null): string | null {
  return PROMPT_KINDS.includes(step.kind) ? step.text : prev
}

export function reducer(state: MachineState, action: Action): MachineState {
  switch (action.type) {
    case 'selectLanguage':
      // Re-identification (Task 8): the kiosk no longer self-starts
      // anonymously -- a language pick now leads to the start-code entry
      // screen, not straight to consent (that only happens once a start
      // code has been captured, see `submitStartCode` below).
      return { ...state, language: action.language, screen: 'startCodeEntry' }
    case 'declineConsent':
      return initialState
    case 'starting':
      return { ...state, pending: true }
    case 'started': {
      if (!state.pending) return state
      const r = action.result
      // Fail-closed (Task 8, mirrors `startedFollowup` below): `start` now
      // consumes a person-entered start code, and the backend returns the
      // SAME 401 for an invalid/used/expired code as for a genuinely
      // unauthorized device (deliberately indistinguishable, to leak
      // nothing about which one it was). Routing to 'unauthorized' ("this
      // station is not authorized") would misdirect the person -- and any
      // operator helping them -- toward a device problem that may not
      // exist, so both statuses route to the same gentle 'unavailable'
      // screen instead.
      if (r.status !== 'ok') return { ...state, screen: 'unavailable', pending: false }
      return {
        ...state,
        sessionToken: r.sessionToken,
        step: r.step,
        stepSeq: state.stepSeq + 1,
        lastPrompt: nextPrompt(r.step, state.lastPrompt),
        screen: screenFor(r.step.kind),
        pending: false,
      }
    }
    case 'submitting':
      return { ...state, lastAnswer: action.answer, pending: true }
    case 'submitted': {
      if (!state.pending) return state
      const r = action.result
      if (r.status === 'unauthorized') return { ...state, screen: 'unauthorized', pending: false }
      if (r.status === 'session-expired') return initialState
      if (r.status === 'unavailable') return { ...state, screen: 'unavailable', pending: false }
      return {
        ...state,
        step: r.step,
        stepSeq: state.stepSeq + 1,
        lastPrompt: nextPrompt(r.step, state.lastPrompt),
        screen: screenFor(r.step.kind),
        pending: false,
      }
    }
    case 'stop':
      return initialState
    case 'openFollowupEntry':
      return { ...state, screen: 'followupEntry' }
    case 'previewFollowupLanguage':
      return { ...state, language: action.language }
    case 'submitFollowupCredentials':
      return { ...state, followupToken: action.token, language: action.language, screen: 'followupConsent' }
    case 'submitStartCode':
      // The language was already set by selectLanguage (LanguagePicker); keep it.
      return { ...state, startCode: action.code, screen: 'consent' }
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
      return {
        ...state,
        sessionToken: r.sessionToken,
        step: r.step,
        stepSeq: state.stepSeq + 1,
        lastPrompt: nextPrompt(r.step, state.lastPrompt),
        screen: screenFor(r.step.kind),
        pending: false,
      }
    }
    default:
      return state
  }
}
