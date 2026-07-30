import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { makeVoiceClient, noopVoiceClient } from '../test/fakeClient'
import { FollowupEntry } from './FollowupEntry'
import i18n from '../i18n'

test('requires both a language and a non-empty code before it can continue', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<FollowupEntry onSubmit={onSubmit} onLanguageChange={vi.fn()} />)

  const submit = screen.getByRole('button', { name: 'Continua' })
  expect(submit).toBeDisabled()

  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  expect(submit).toBeDisabled() // language chosen, code still empty

  await userEvent.type(screen.getByLabelText(/codice/i), 'F-ABC123')
  expect(submit).toBeEnabled()

  await userEvent.click(submit)
  expect(onSubmit).toHaveBeenCalledWith('F-ABC123', 'it')
})

test('trims the entered code and reports the chosen language code, not its label', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  const { container } = renderWithProviders(
    <FollowupEntry onSubmit={onSubmit} onLanguageChange={vi.fn()} />,
  )

  // Tapping a tile applies the language immediately, so every label on this
  // screen — including the submit button — re-renders in Arabic right away.
  // Look the elements up by stable id/role rather than (now-stale) Italian
  // text.
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  const input = container.querySelector('#followup-token') as HTMLInputElement
  await userEvent.type(input, '  F-1  ')
  const buttons = screen.getAllByRole('button')
  await userEvent.click(buttons[buttons.length - 1])

  expect(onSubmit).toHaveBeenCalledWith('F-1', 'ar')
})

test('choosing a language tile applies it immediately (RTL for Arabic)', async () => {
  renderWithProviders(<FollowupEntry onSubmit={vi.fn()} onLanguageChange={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  await waitFor(() => expect(document.documentElement.dir).toBe('rtl'))
})

// --- Fix round 1 (§4 accessibility): VoiceBar on the follow-up entry screen.
// A returning person handed a paper code by an operator gets no audio at all
// on this screen otherwise — the only person-facing, language-committed
// screen in the kiosk without one.

test('no voice affordance before a language is chosen', async () => {
  await i18n.changeLanguage('it')
  renderWithProviders(<FollowupEntry onSubmit={vi.fn()} onLanguageChange={vi.fn()} />, {
    voiceClient: noopVoiceClient,
  })
  expect(screen.queryByRole('button', { name: 'Ascolta' })).not.toBeInTheDocument()
})

test('picking a language reveals the listen affordance and narrates the title + token prompt', async () => {
  await i18n.changeLanguage('it')
  const voice = makeVoiceClient({ audio: null })
  renderWithProviders(<FollowupEntry onSubmit={vi.fn()} onLanguageChange={vi.fn()} />, { voiceClient: voice })

  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))

  expect(await screen.findByRole('button', { name: 'Ascolta' })).toBeInTheDocument()
  await waitFor(() =>
    expect(voice.calls.synthesize).toEqual([
      { text: "Hai un codice di follow-up?. Inserisci il codice che ti ha dato l'operatore", language: 'it' },
    ]),
  )
})

test('reports the chosen language to the app immediately (voice narration retargeting)', async () => {
  const onLanguageChange = vi.fn()
  renderWithProviders(<FollowupEntry onSubmit={vi.fn()} onLanguageChange={onLanguageChange} />)
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  expect(onLanguageChange).toHaveBeenCalledWith('ar')
})
