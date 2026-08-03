import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { makeVoiceClient, noopVoiceClient } from '../test/fakeClient'
import { StartCodeEntry } from './StartCodeEntry'
import i18n from '../i18n'

test('requires both a language and a non-empty code before it can continue', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<StartCodeEntry onSubmit={onSubmit} onLanguageChange={vi.fn()} />)

  const submit = screen.getByRole('button', { name: 'Continua' })
  expect(submit).toBeDisabled()

  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  expect(submit).toBeDisabled() // language chosen, code still empty

  await userEvent.type(screen.getByLabelText(/codice/i), 'S-ABC123')
  expect(submit).toBeEnabled()

  await userEvent.click(submit)
  expect(onSubmit).toHaveBeenCalledWith('S-ABC123', 'it')
})

test('trims the entered code and reports the chosen language code, not its label', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  const { container } = renderWithProviders(
    <StartCodeEntry onSubmit={onSubmit} onLanguageChange={vi.fn()} />,
  )

  // Tapping a tile applies the language immediately, so every label on this
  // screen — including the submit button — re-renders in Arabic right away.
  // Look the elements up by stable id/role rather than (now-stale) Italian
  // text.
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  const input = container.querySelector('#start-code') as HTMLInputElement
  await userEvent.type(input, '  S-1  ')
  const buttons = screen.getAllByRole('button')
  await userEvent.click(buttons[buttons.length - 1])

  expect(onSubmit).toHaveBeenCalledWith('S-1', 'ar')
})

test('choosing a language tile applies it immediately (RTL for Arabic)', async () => {
  renderWithProviders(<StartCodeEntry onSubmit={vi.fn()} onLanguageChange={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  await waitFor(() => expect(document.documentElement.dir).toBe('rtl'))
})

test('no voice affordance before a language is chosen', async () => {
  await i18n.changeLanguage('it')
  renderWithProviders(<StartCodeEntry onSubmit={vi.fn()} onLanguageChange={vi.fn()} />, {
    voiceClient: noopVoiceClient,
  })
  expect(screen.queryByRole('button', { name: 'Ascolta' })).not.toBeInTheDocument()
})

test('picking a language reveals the listen affordance and narrates the title + code prompt', async () => {
  await i18n.changeLanguage('it')
  const voice = makeVoiceClient({ audio: null })
  renderWithProviders(<StartCodeEntry onSubmit={vi.fn()} onLanguageChange={vi.fn()} />, { voiceClient: voice })

  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))

  expect(await screen.findByRole('button', { name: 'Ascolta' })).toBeInTheDocument()
  await waitFor(() =>
    expect(voice.calls.synthesize).toEqual([
      { text: "Inserisci il tuo codice. Inserisci il codice che ti ha dato l'operatore", language: 'it' },
    ]),
  )
})

test('reports the chosen language to the app immediately (voice narration retargeting)', async () => {
  const onLanguageChange = vi.fn()
  renderWithProviders(<StartCodeEntry onSubmit={vi.fn()} onLanguageChange={onLanguageChange} />)
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  expect(onLanguageChange).toHaveBeenCalledWith('ar')
})
