import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { makeVoiceClient } from '../test/fakeClient'
import { VoiceBar } from './VoiceBar'
import i18n from '../i18n'

test('auto-reads the text on mount (calls synthesize with text + language)', async () => {
  await i18n.changeLanguage('it')
  const client = makeVoiceClient({ audio: null }) // null → no Audio, silent
  renderWithProviders(<VoiceBar text="Che lavoro sai fare?" />, { voiceClient: client, language: 'it' })
  await waitFor(() => expect(client.calls.synthesize).toEqual([{ text: 'Che lavoro sai fare?', language: 'it' }]))
})

test('mute toggle suppresses auto-read and is reflected in aria-pressed', async () => {
  await i18n.changeLanguage('it')
  const client = makeVoiceClient({ audio: null })
  renderWithProviders(<VoiceBar text="Domanda" />, { voiceClient: client, language: 'it' })
  await waitFor(() => expect(client.calls.synthesize.length).toBe(1))
  const mute = screen.getByRole('button', { name: /audio/i })
  await userEvent.click(mute)
  expect(mute).toHaveAttribute('aria-pressed', 'true')
})

test('«Ascolta» replays on demand', async () => {
  await i18n.changeLanguage('it')
  const client = makeVoiceClient({ audio: null })
  renderWithProviders(<VoiceBar text="Domanda" />, { voiceClient: client, language: 'it' })
  await waitFor(() => expect(client.calls.synthesize.length).toBe(1))
  await userEvent.click(screen.getByRole('button', { name: 'Ascolta' }))
  await waitFor(() => expect(client.calls.synthesize.length).toBe(2))
})
