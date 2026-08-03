import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { makeVoiceClient } from '../test/fakeClient'
import { StartCodeEntry } from './StartCodeEntry'
import i18n from '../i18n'

test('Continua is disabled until a non-empty code is entered, then submits the code', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<StartCodeEntry onSubmit={onSubmit} />, { language: 'it' })

  const submit = screen.getByRole('button', { name: 'Continua' })
  expect(submit).toBeDisabled() // empty code

  await userEvent.type(screen.getByLabelText(/codice/i), 'S-ABC123')
  expect(submit).toBeEnabled() // language was already chosen on LanguagePicker

  await userEvent.click(submit)
  expect(onSubmit).toHaveBeenCalledWith('S-ABC123')
})

test('trims the entered code before submitting', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<StartCodeEntry onSubmit={onSubmit} />, { language: 'it' })
  await userEvent.type(screen.getByLabelText(/codice/i), '  S-1  ')
  await userEvent.click(screen.getByRole('button', { name: 'Continua' }))
  expect(onSubmit).toHaveBeenCalledWith('S-1')
})

test('does NOT show a language grid (the language was chosen on the previous screen)', async () => {
  await i18n.changeLanguage('it')
  renderWithProviders(<StartCodeEntry onSubmit={vi.fn()} />, { language: 'it' })
  expect(screen.queryByRole('button', { name: 'Italiano' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'العربية' })).not.toBeInTheDocument()
})

test('narrates the title + code prompt in the already-chosen language', async () => {
  await i18n.changeLanguage('it')
  const voice = makeVoiceClient({ audio: null })
  renderWithProviders(<StartCodeEntry onSubmit={vi.fn()} />, { voiceClient: voice, language: 'it' })

  expect(screen.getByRole('button', { name: 'Ascolta' })).toBeInTheDocument()
  await waitFor(() =>
    expect(voice.calls.synthesize).toEqual([
      { text: "Inserisci il tuo codice. Inserisci il codice che ti ha dato l'operatore", language: 'it' },
    ]),
  )
})
