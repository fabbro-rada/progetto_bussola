import { useCallback, useReducer } from 'react'
import { kioskClient } from './api/kioskClient'
import type { KioskClient } from './types'
import { applyLanguage } from './i18n'
import { initialState, reducer } from './state/kioskMachine'
import { StopButton } from './components/StopButton'
import { TextSizeControl } from './components/TextSizeControl'
import { VoicePlaceholder } from './components/VoicePlaceholder'
import { LanguagePicker } from './screens/LanguagePicker'
import { Consent } from './screens/Consent'
import { Question } from './screens/Question'
import { Summary } from './screens/Summary'
import { Clarification } from './screens/Clarification'
import { Refusal } from './screens/Refusal'
import { Unavailable } from './screens/Unavailable'
import { Completed } from './screens/Completed'
import { Unauthorized } from './screens/Unauthorized'

export function App({ client = kioskClient }: { client?: KioskClient } = {}) {
  const [state, dispatch] = useReducer(reducer, initialState)

  const selectLanguage = useCallback((code: string) => {
    applyLanguage(code)
    dispatch({ type: 'selectLanguage', language: code })
  }, [])

  const start = useCallback(async () => {
    if (!state.language) return
    const result = await client.startInterview(state.language)
    dispatch({ type: 'started', result })
  }, [client, state.language])

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
      const result = await client.submitAnswer(state.sessionToken, state.lastAnswer)
      dispatch({ type: 'submitted', result })
    } else {
      await start()
    }
  }, [client, state.sessionToken, state.lastAnswer, start])

  const stop = useCallback(() => {
    applyLanguage('it')
    dispatch({ type: 'stop' })
  }, [])

  function renderScreen() {
    switch (state.screen) {
      case 'language':
        return <LanguagePicker onSelect={selectLanguage} />
      case 'consent':
        return <Consent onAccept={start} onDecline={() => dispatch({ type: 'declineConsent' })} />
      case 'question':
        return <Question text={state.step!.text} onSubmit={submit} />
      case 'summary':
        return <Summary text={state.step!.text} onSubmit={submit} />
      case 'clarification':
        return <Clarification text={state.step!.text} onSubmit={submit} />
      case 'refusal':
        return <Refusal text={state.step!.text} onSubmit={submit} />
      case 'unavailable':
        return <Unavailable onRetry={retry} />
      case 'completed':
        return <Completed onFinish={stop} />
      case 'unauthorized':
        return <Unauthorized />
    }
  }

  const inSession = state.screen !== 'language'
  return (
    <div className="app">
      <header className="chrome">
        {inSession ? <StopButton onStop={stop} /> : <span />}
        <TextSizeControl />
        <VoicePlaceholder />
      </header>
      <main>{renderScreen()}</main>
    </div>
  )
}
