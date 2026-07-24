import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { ConfirmCorrect } from './ConfirmCorrect'
import i18n from '../i18n'
import { makeVoiceClient } from '../test/fakeClient'
import { stubMedia } from '../test/media'

test('confirm submits the localized affirmative', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<ConfirmCorrect text="Ho capito: sai cucinare" onSubmit={onSubmit} />)
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è corretto' }))
  expect(onSubmit).toHaveBeenCalledWith('Sì, è corretto')
})

test('correct reveals a field and submits the typed correction', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<ConfirmCorrect text="Ho capito: sai cucinare" onSubmit={onSubmit} />)
  await userEvent.click(screen.getByRole('button', { name: 'No, correggi qualcosa' }))
  await userEvent.type(screen.getByRole('textbox'), 'so anche guidare il muletto')
  await userEvent.click(screen.getByRole('button', { name: 'Invia' }))
  expect(onSubmit).toHaveBeenCalledWith('so anche guidare il muletto')
})

test('confirm branch shows read-aloud but no Parla; correcting branch enables Parla', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  renderWithProviders(<ConfirmCorrect text="Ho capito: sai cucinare" onSubmit={vi.fn()} />, {
    voiceClient: makeVoiceClient({ audio: null }),
  })
  expect(screen.getByRole('button', { name: 'Ascolta' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Parla/ })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'No, correggi qualcosa' }))
  expect(await screen.findByRole('button', { name: /Parla/ })).toBeInTheDocument()
  vi.unstubAllGlobals()
})
