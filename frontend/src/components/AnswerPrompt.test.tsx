import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { AnswerPrompt } from './AnswerPrompt'
import i18n from '../i18n'
import { makeVoiceClient } from '../test/fakeClient'
import { stubMedia } from '../test/media'

test('submits the trimmed answer and clears the field; empty is ignored', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<AnswerPrompt text="Che lavoro sai fare?" onSubmit={onSubmit} />)
  expect(screen.getByText('Che lavoro sai fare?')).toBeInTheDocument()

  const next = screen.getByRole('button', { name: 'Avanti' })
  await userEvent.click(next)
  expect(onSubmit).not.toHaveBeenCalled() // empty ignored (button disabled)

  await userEvent.type(screen.getByRole('textbox'), '  so cucinare  ')
  await userEvent.click(next)
  expect(onSubmit).toHaveBeenCalledWith('so cucinare')
})

test('renders an optional banner (used by the refusal screen)', () => {
  renderWithProviders(<AnswerPrompt text="Torniamo a te" onSubmit={vi.fn()} banner="Solo lavoro" />)
  expect(screen.getByText('Solo lavoro')).toBeInTheDocument()
})

test('dictated text lands in the field for review (does not auto-submit)', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  const client = makeVoiceClient({ transcript: 'ho lavorato in cucina', audio: null })
  const onSubmit = vi.fn()
  renderWithProviders(<AnswerPrompt text="Che lavoro sai fare?" onSubmit={onSubmit} />, { voiceClient: client })
  await userEvent.click(await screen.findByRole('button', { name: /Parla/ }))
  await userEvent.click(await screen.findByRole('button', { name: /Stop/ }))
  await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('ho lavorato in cucina'))
  expect(onSubmit).not.toHaveBeenCalled() // review, not auto-submit
  vi.unstubAllGlobals()
})

test('while the form is busy (answer processing) the field and voice buttons are disabled', async () => {
  await i18n.changeLanguage('it')
  renderWithProviders(<AnswerPrompt text="Che lavoro sai fare?" onSubmit={vi.fn()} busy />)
  expect(screen.getByRole('textbox')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Avanti' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Ascolta' })).toBeDisabled()
  expect(screen.getByRole('button', { name: /audio/i })).toBeDisabled()
})

test('the textarea and «Avanti» are disabled while a dictation is in progress', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  const client = makeVoiceClient({ transcript: 'ho lavorato in cucina', audio: null })
  renderWithProviders(<AnswerPrompt text="Che lavoro sai fare?" onSubmit={vi.fn()} />, { voiceClient: client })
  const textarea = screen.getByRole('textbox')
  expect(textarea).not.toBeDisabled()
  await userEvent.click(await screen.findByRole('button', { name: /Parla/ }))
  await screen.findByRole('button', { name: /Stop/ }) // recording in progress
  expect(textarea).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Avanti' })).toBeDisabled()
  // when the dictation finishes, the field re-enables with the transcript
  await userEvent.click(screen.getByRole('button', { name: /Stop/ }))
  await waitFor(() => expect(textarea).not.toBeDisabled())
  expect(textarea).toHaveValue('ho lavorato in cucina')
  vi.unstubAllGlobals()
})
