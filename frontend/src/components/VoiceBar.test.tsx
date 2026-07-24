import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { makeVoiceClient } from '../test/fakeClient'
import { stubMedia } from '../test/media' // shared mock created in Task 4
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

test('dictation: Parla → Stop → onDictated fires with the transcript (field, not auto-submit)', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  const client = makeVoiceClient({ transcript: 'so cucinare', audio: null })
  const onDictated = vi.fn()
  renderWithProviders(<VoiceBar text="Domanda" canDictate onDictated={onDictated} />, {
    voiceClient: client,
    language: 'it',
  })
  await userEvent.click(await screen.findByRole('button', { name: /Parla/ }))
  await userEvent.click(await screen.findByRole('button', { name: /Stop/ }))
  await waitFor(() => expect(onDictated).toHaveBeenCalledWith('so cucinare'))
  vi.unstubAllGlobals()
})

test('no Parla when canDictate is false', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  renderWithProviders(<VoiceBar text="Domanda" />, { voiceClient: makeVoiceClient({ audio: null }), language: 'it' })
  expect(screen.queryByRole('button', { name: /Parla/ })).not.toBeInTheDocument()
  vi.unstubAllGlobals()
})
