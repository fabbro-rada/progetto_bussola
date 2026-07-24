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
  const s = reducer({ ...initialState, language: 'it' }, {
    type: 'started',
    result: { status: 'ok', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } },
  })
  expect(s).toMatchObject({ screen: 'question', sessionToken: 'tok', step: { kind: 'question', text: 'Q1' } })
})

test('started unauthorized/unavailable route to their screens', () => {
  expect(reducer(initialState, { type: 'started', result: { status: 'unauthorized' } }).screen).toBe('unauthorized')
  expect(reducer(initialState, { type: 'started', result: { status: 'unavailable' } }).screen).toBe('unavailable')
})

test('submitting records lastAnswer for retry', () => {
  const s = reducer({ ...initialState, sessionToken: 'tok' }, { type: 'submitting', answer: 'so cucinare' })
  expect(s.lastAnswer).toBe('so cucinare')
})

test('submitted ok maps each step kind to its screen', () => {
  const base = { ...initialState, sessionToken: 'tok' }
  for (const kind of ['question', 'summary', 'clarification', 'refusal', 'unavailable', 'completed'] as const) {
    const s = reducer(base, { type: 'submitted', result: { status: 'ok', step: { kind, text: 't' } } })
    expect(s.screen).toBe(kind)
    expect(s.sessionToken).toBe('tok')
  }
})

test('submitted session-expired resets to the start; unauthorized routes to unauthorized', () => {
  const base = { ...initialState, sessionToken: 'tok', screen: 'question' as const }
  expect(reducer(base, { type: 'submitted', result: { status: 'session-expired' } })).toEqual(initialState)
  expect(reducer(base, { type: 'submitted', result: { status: 'unauthorized' } }).screen).toBe('unauthorized')
})

test('submitted unavailable keeps the session token so retry is possible', () => {
  const s = reducer({ ...initialState, sessionToken: 'tok' }, { type: 'submitted', result: { status: 'unavailable' } })
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
