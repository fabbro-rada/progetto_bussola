import { expect, test } from 'vitest'
import { initialState, reducer } from './kioskMachine'

test('selectLanguage moves to consent and records the language', () => {
  const s = reducer(initialState, { type: 'selectLanguage', language: 'ar' })
  expect(s.screen).toBe('consent')
  expect(s.language).toBe('ar')
})

test('declineConsent resets to the initial state', () => {
  const s = reducer({ ...initialState, screen: 'consent', language: 'it' }, { type: 'declineConsent' })
  expect(s).toEqual(initialState)
})

test('started ok derives the screen from the step kind and stores the session token', () => {
  const s = reducer({ ...initialState, language: 'it', pending: true }, {
    type: 'started',
    result: { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } },
  })
  expect(s).toMatchObject({ screen: 'question', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } })
})

test('started unauthorized/unavailable route to their screens', () => {
  expect(reducer({ ...initialState, pending: true }, { type: 'started', result: { status: 'unauthorized' } }).screen).toBe('unauthorized')
  expect(reducer({ ...initialState, pending: true }, { type: 'started', result: { status: 'unavailable' } }).screen).toBe('unavailable')
})

test('submitting records lastAnswer for retry', () => {
  const s = reducer({ ...initialState, sessionToken: 'tok' }, { type: 'submitting', answer: 'so cucinare' })
  expect(s.lastAnswer).toBe('so cucinare')
})

test('submitted ok maps each step kind to its screen', () => {
  const base = { ...initialState, sessionToken: 'tok', pending: true }
  for (const kind of ['question', 'summary', 'clarification', 'refusal', 'unavailable', 'completed'] as const) {
    const s = reducer(base, { type: 'submitted', result: { status: 'ok', step: { kind, text: 't' } } })
    expect(s.screen).toBe(kind)
    expect(s.sessionToken).toBe('tok')
  }
})

test('submitted session-expired resets to the start; unauthorized routes to unauthorized', () => {
  const base = { ...initialState, sessionToken: 'tok', screen: 'question' as const, pending: true }
  expect(reducer(base, { type: 'submitted', result: { status: 'session-expired' } })).toEqual(initialState)
  expect(reducer(base, { type: 'submitted', result: { status: 'unauthorized' } }).screen).toBe('unauthorized')
})

test('submitted unavailable keeps the session token so retry is possible', () => {
  const s = reducer({ ...initialState, sessionToken: 'tok', pending: true }, { type: 'submitted', result: { status: 'unavailable' } })
  expect(s.screen).toBe('unavailable')
  expect(s.sessionToken).toBe('tok')
})

test('stop resets to the initial state from anywhere', () => {
  const s = reducer({ ...initialState, screen: 'summary', sessionToken: 'tok', language: 'fr' }, { type: 'stop' })
  expect(s).toEqual(initialState)
})

test('starting sets pending true', () => {
  const s = reducer(initialState, { type: 'starting' })
  expect(s.pending).toBe(true)
})

test('submitting sets pending true along with lastAnswer', () => {
  const s = reducer({ ...initialState, sessionToken: 'tok' }, { type: 'submitting', answer: 'so cucinare' })
  expect(s.lastAnswer).toBe('so cucinare')
  expect(s.pending).toBe(true)
})

test('started ok clears pending even when the prior state was pending', () => {
  const s = reducer({ ...initialState, language: 'it', pending: true }, {
    type: 'started',
    result: { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } },
  })
  expect(s.pending).toBe(false)
})

test('started unauthorized/unavailable clear pending too', () => {
  expect(reducer({ ...initialState, pending: true }, { type: 'started', result: { status: 'unauthorized' } }).pending).toBe(false)
  expect(reducer({ ...initialState, pending: true }, { type: 'started', result: { status: 'unavailable' } }).pending).toBe(false)
})

test('submitted ok clears pending even when the prior state was pending', () => {
  const base = { ...initialState, sessionToken: 'tok', pending: true }
  const s = reducer(base, { type: 'submitted', result: { status: 'ok', step: { kind: 'summary', text: 't' } } })
  expect(s.pending).toBe(false)
})

test('submitted unauthorized/unavailable clear pending too', () => {
  const base = { ...initialState, sessionToken: 'tok', pending: true }
  expect(reducer(base, { type: 'submitted', result: { status: 'unauthorized' } }).pending).toBe(false)
  expect(reducer(base, { type: 'submitted', result: { status: 'unavailable' } }).pending).toBe(false)
})

// --- Follow-up path (Sottosistema 29, Task 6): additive on top of the above,
// none of which changed.

test('openFollowupEntry moves to the follow-up entry screen from anywhere', () => {
  const s = reducer(initialState, { type: 'openFollowupEntry' })
  expect(s.screen).toBe('followupEntry')
})

test('submitFollowupCredentials stores the token and language and moves to follow-up consent', () => {
  const s = reducer({ ...initialState, screen: 'followupEntry' }, {
    type: 'submitFollowupCredentials',
    token: 'F-123',
    language: 'ar',
  })
  expect(s.screen).toBe('followupConsent')
  expect(s.followupToken).toBe('F-123')
  expect(s.language).toBe('ar')
})

test('declining follow-up consent resets to the initial state (reuses declineConsent)', () => {
  const mid = { ...initialState, screen: 'followupConsent' as const, followupToken: 'F-123', language: 'ar' }
  expect(reducer(mid, { type: 'declineConsent' })).toEqual(initialState)
})

test('startedFollowup ok derives the screen from the step kind and stores the session token', () => {
  const s = reducer({ ...initialState, followupToken: 'F-123', language: 'ar', pending: true }, {
    type: 'startedFollowup',
    result: { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Bentornato' } },
  })
  expect(s).toMatchObject({ screen: 'question', sessionToken: 'tok', step: { kind: 'question', text: 'Bentornato' } })
})

test('startedFollowup unauthorized (bad/expired/used token) routes to the gentle unavailable screen, not "unauthorized"', () => {
  const base = { ...initialState, followupToken: 'F-123', pending: true }
  const s = reducer(base, { type: 'startedFollowup', result: { status: 'unauthorized' } })
  expect(s.screen).toBe('unavailable')
  expect(s.pending).toBe(false)
})

test('startedFollowup unavailable (backend down) also routes to the unavailable screen', () => {
  const base = { ...initialState, followupToken: 'F-123', pending: true }
  const s = reducer(base, { type: 'startedFollowup', result: { status: 'unavailable' } })
  expect(s.screen).toBe('unavailable')
  expect(s.pending).toBe(false)
})

test('a late startedFollowup after a reset is ignored (pending=false → no-op)', () => {
  const late = reducer(initialState, {
    type: 'startedFollowup',
    result: { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q' } },
  })
  expect(late).toEqual(initialState)
})

test('stop resets the follow-up path too (Ferma from followupEntry/followupConsent)', () => {
  const mid = { ...initialState, screen: 'followupEntry' as const, followupToken: 'F-123', language: 'ar' }
  expect(reducer(mid, { type: 'stop' })).toEqual(initialState)
})

test('a late started/submitted after a reset is ignored (pending=false → no-op)', () => {
  // initialState has pending:false, screen:'language'
  const lateStarted = reducer(initialState, {
    type: 'started',
    result: { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q' } },
  })
  expect(lateStarted).toEqual(initialState) // screen stays 'language', not 'question'

  const lateSubmitted = reducer(initialState, {
    type: 'submitted',
    result: { status: 'ok', step: { kind: 'summary', text: 'RECAP' } },
  })
  expect(lateSubmitted).toEqual(initialState)
})
