import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { test } from 'vitest'
import { renderWithProviders } from './test/utils'
import { expectNoA11yViolations } from './test/axe'
import { LanguagePicker } from './screens/LanguagePicker'
import { StartCodeEntry } from './screens/StartCodeEntry'
import { Consent } from './screens/Consent'
import { FollowupEntry } from './screens/FollowupEntry'
import { FollowupConsent } from './screens/FollowupConsent'
import { Question } from './screens/Question'
import { Clarification } from './screens/Clarification'
import { Summary } from './screens/Summary'
import { Refusal } from './screens/Refusal'
import { Completed } from './screens/Completed'
import { Unauthorized } from './screens/Unauthorized'
import { Unavailable } from './screens/Unavailable'
import { Notice } from './components/Notice'
import { StopButton } from './components/StopButton'
import { TextSizeControl } from './components/TextSizeControl'
import { VoiceBar } from './components/VoiceBar'
import { AnswerPrompt } from './components/AnswerPrompt'
import { ConfirmCorrect } from './components/ConfirmCorrect'

const noop = () => {}

// Every person-facing kiosk screen and shared component is rendered with
// representative props and checked for component-level a11y violations (§4).
test('LanguagePicker has no a11y violations', async () => {
  const { container } = renderWithProviders(<LanguagePicker onSelect={noop} />)
  await expectNoA11yViolations(container)
})

test('StartCodeEntry has no a11y violations', async () => {
  const { container } = renderWithProviders(<StartCodeEntry onSubmit={noop} onLanguageChange={noop} />)
  await expectNoA11yViolations(container)
})

// Also audit the post-language-selection state, since that's when the
// VoiceBar mounts and is the more representative state (mirrors
// FollowupEntry below).
test('StartCodeEntry (after picking a language) has no a11y violations', async () => {
  const { container } = renderWithProviders(<StartCodeEntry onSubmit={noop} onLanguageChange={noop} />)
  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  await expectNoA11yViolations(container)
})

test('Consent has no a11y violations', async () => {
  const { container } = renderWithProviders(<Consent onAccept={noop} onDecline={noop} />)
  await expectNoA11yViolations(container)
})

test('FollowupEntry has no a11y violations', async () => {
  const { container } = renderWithProviders(<FollowupEntry onSubmit={noop} onLanguageChange={noop} />)
  await expectNoA11yViolations(container)
})

// Also audit the post-language-selection state, since that's when the
// VoiceBar (fix round 1, §4) mounts and is the more representative state.
test('FollowupEntry (after picking a language) has no a11y violations', async () => {
  const { container } = renderWithProviders(<FollowupEntry onSubmit={noop} onLanguageChange={noop} />)
  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  await expectNoA11yViolations(container)
})

test('FollowupConsent has no a11y violations', async () => {
  const { container } = renderWithProviders(<FollowupConsent onAccept={noop} onDecline={noop} />)
  await expectNoA11yViolations(container)
})

test('Question has no a11y violations', async () => {
  const { container } = renderWithProviders(<Question text="Che lavoro sai fare?" onSubmit={noop} />)
  await expectNoA11yViolations(container)
})

test('Clarification has no a11y violations', async () => {
  const { container } = renderWithProviders(<Clarification text="Ho capito bene?" onSubmit={noop} />)
  await expectNoA11yViolations(container)
})

test('Summary has no a11y violations', async () => {
  const { container } = renderWithProviders(<Summary text="Ecco cosa ho capito." onSubmit={noop} />)
  await expectNoA11yViolations(container)
})

test('Refusal has no a11y violations', async () => {
  const { container } = renderWithProviders(<Refusal question="Che lavoro sai fare?" onSubmit={noop} />)
  await expectNoA11yViolations(container)
})

test('Completed has no a11y violations', async () => {
  const { container } = renderWithProviders(<Completed onFinish={noop} />)
  await expectNoA11yViolations(container)
})

test('Unauthorized has no a11y violations', async () => {
  const { container } = renderWithProviders(<Unauthorized />)
  await expectNoA11yViolations(container)
})

test('Unavailable has no a11y violations', async () => {
  const { container } = renderWithProviders(<Unavailable onRetry={noop} />)
  await expectNoA11yViolations(container)
})

test('Notice has no a11y violations', async () => {
  const { container } = renderWithProviders(<Notice tone="warn" text="Attenzione." />)
  await expectNoA11yViolations(container)
})

test('StopButton has no a11y violations', async () => {
  const { container } = renderWithProviders(<StopButton onStop={noop} />)
  await expectNoA11yViolations(container)
})

test('TextSizeControl has no a11y violations', async () => {
  const { container } = renderWithProviders(<TextSizeControl />)
  await expectNoA11yViolations(container)
})

test('VoiceBar has no a11y violations', async () => {
  const { container } = renderWithProviders(<VoiceBar text="Leggo questo." canDictate onDictated={noop} />)
  await expectNoA11yViolations(container)
})

test('AnswerPrompt has no a11y violations', async () => {
  const { container } = renderWithProviders(<AnswerPrompt text="Scrivi la risposta." onSubmit={noop} />)
  await expectNoA11yViolations(container)
})

test('ConfirmCorrect has no a11y violations', async () => {
  const { container } = renderWithProviders(<ConfirmCorrect text="Confermi?" onSubmit={noop} />)
  await expectNoA11yViolations(container)
})
