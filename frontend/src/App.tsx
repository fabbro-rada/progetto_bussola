import { useCallback, useReducer } from 'react'
import { useTranslation } from 'react-i18next'
import mark from './assets/logo-bussola-mark.png'
import { kioskClient } from './api/kioskClient'
import type { KioskClient } from './types'
import { applyLanguage } from './i18n'
import { initialState, reducer } from './state/kioskMachine'
import { StopButton } from './components/StopButton'
import { TextSizeControl } from './components/TextSizeControl'
import { voiceClient as realVoiceClient } from './voice/voiceClient'
import { VoiceProvider } from './voice/VoiceContext'
import type { VoiceClient } from './voice/voiceClient'
import { LanguagePicker } from './screens/LanguagePicker'
import { StartCodeEntry } from './screens/StartCodeEntry'
import { Consent } from './screens/Consent'
import { FollowupEntry } from './screens/FollowupEntry'
import { FollowupConsent } from './screens/FollowupConsent'
import { Question } from './screens/Question'
import { Summary } from './screens/Summary'
import { Clarification } from './screens/Clarification'
import { Refusal } from './screens/Refusal'
import { Unavailable } from './screens/Unavailable'
import { Completed } from './screens/Completed'
import { Recap } from './screens/Recap'
import { Unauthorized } from './screens/Unauthorized'

export function App({
  client = kioskClient,
  voiceClient = realVoiceClient,
}: { client?: KioskClient; voiceClient?: VoiceClient } = {}) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const { t } = useTranslation()

  const selectLanguage = useCallback((code: string) => {
    applyLanguage(code)
    dispatch({ type: 'selectLanguage', language: code })
  }, [])

  const start = useCallback(async () => {
    if (!state.language || !state.startCode) return
    dispatch({ type: 'starting' })
    const result = await client.startInterview(state.startCode, state.language)
    dispatch({ type: 'started', result })
  }, [client, state.language, state.startCode])

  // Re-identification (Task 8): captures the start code (the language was
  // already chosen on LanguagePicker) and moves on to the (unchanged) consent
  // screen — no network call yet.
  const submitStartCode = useCallback((code: string) => {
    dispatch({ type: 'submitStartCode', code })
  }, [])

  const openFollowupEntry = useCallback(() => {
    dispatch({ type: 'openFollowupEntry' })
  }, [])

  // Fix round 1 (§4): keeps voice narration on the follow-up entry screen
  // targeting the language just tapped, not whatever `state.language` was
  // before. `FollowupEntry` already applies the language to i18n/dir itself;
  // this only updates the field `VoiceProvider`'s `language` prop reads below.
  const previewFollowupLanguage = useCallback((code: string) => {
    dispatch({ type: 'previewFollowupLanguage', language: code })
  }, [])

  const submitFollowupCredentials = useCallback((token: string, language: string) => {
    dispatch({ type: 'submitFollowupCredentials', token, language })
  }, [])

  const startFollowup = useCallback(async () => {
    if (!state.followupToken || !state.language) return
    dispatch({ type: 'starting' })
    const result = await client.startFollowup(state.followupToken, state.language)
    dispatch({ type: 'startedFollowup', result })
  }, [client, state.followupToken, state.language])

  const submit = useCallback(
    async (answer: string) => {
      if (!state.sessionToken) return
      dispatch({ type: 'submitting', answer })
      const result = await client.submitAnswer(state.sessionToken, answer)
      dispatch({ type: 'submitted', result })
    },
    [client, state.sessionToken],
  )

  const retry = useCallback(async () => {
    if (state.sessionToken && state.lastAnswer !== null) {
      await submit(state.lastAnswer)
    } else if (state.followupToken) {
      await startFollowup()
    } else {
      await start()
    }
  }, [state.sessionToken, state.lastAnswer, state.followupToken, submit, start, startFollowup])

  const stop = useCallback(() => {
    applyLanguage('it')
    dispatch({ type: 'stop' })
  }, [])

  const decline = useCallback(() => {
    applyLanguage('it')
    dispatch({ type: 'declineConsent' })
  }, [])

  function renderScreen() {
    switch (state.screen) {
      case 'language':
        return <LanguagePicker onSelect={selectLanguage} onFollowupEntry={openFollowupEntry} />
      case 'startCodeEntry':
        return <StartCodeEntry onSubmit={submitStartCode} />
      case 'consent':
        return <Consent onAccept={start} onDecline={decline} busy={state.pending} />
      case 'followupEntry':
        return <FollowupEntry onSubmit={submitFollowupCredentials} onLanguageChange={previewFollowupLanguage} notice={state.followupNotice} />
      case 'followupConsent':
        return <FollowupConsent onAccept={startFollowup} onDecline={decline} busy={state.pending} />
      // Key by stepSeq so every new step remounts a fresh input component
      // (a summary→summary correction must reset ConfirmCorrect to Sì/No).
      case 'question':
        return <Question key={state.stepSeq} text={state.step!.text} onSubmit={submit} busy={state.pending} />
      case 'summary':
        return <Summary key={state.stepSeq} text={state.step!.text} onSubmit={submit} busy={state.pending} />
      case 'clarification':
        return <Clarification key={state.stepSeq} text={state.step!.text} onSubmit={submit} busy={state.pending} />
      case 'refusal':
        // Re-show the question the person was answering (the refusal step itself
        // only carries the notice, surfaced as the banner inside Refusal).
        return <Refusal key={state.stepSeq} question={state.lastPrompt ?? ''} onSubmit={submit} busy={state.pending} />
      case 'unavailable':
        return <Unavailable onRetry={retry} busy={state.pending} />
      case 'completed':
        return <Completed onFinish={stop} />
      case 'recap':
        return <Recap key={state.stepSeq} profile={state.step!.recap!} onSubmit={submit} busy={state.pending} />
      case 'unauthorized':
        return <Unauthorized />
    }
  }

  const inSession = state.screen !== 'language'
  return (
    <div className="app">
      <header className="chrome">
        <div className="chrome-start">
          <img src={mark} alt="Progetto Bussola" className="chrome-mark" />
          {inSession && <StopButton onStop={stop} />}
        </div>
        {state.pending && (
          <div className="pending" role="status" aria-live="polite">
            {t('pending.text')}
          </div>
        )}
        <TextSizeControl />
      </header>
      <VoiceProvider language={state.language ?? 'it'} client={voiceClient}>
        <main>{renderScreen()}</main>
      </VoiceProvider>
    </div>
  )
}
