import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { FollowupConsent } from './FollowupConsent'
import i18n from '../i18n'

test('shows the follow-up recap and wires accept/decline', async () => {
  await i18n.changeLanguage('it')
  const onAccept = vi.fn()
  const onDecline = vi.fn()
  renderWithProviders(<FollowupConsent onAccept={onAccept} onDecline={onDecline} />)

  expect(screen.getByText(/Aggiorniamo il tuo profilo/)).toBeInTheDocument()
  expect(screen.getByText(/Niente reati, niente salute, niente famiglia/)).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Sì, aggiorniamo' }))
  expect(onAccept).toHaveBeenCalledOnce()

  await userEvent.click(screen.getByRole('button', { name: 'Non ora' }))
  expect(onDecline).toHaveBeenCalledOnce()
})

test('decline is available even while a request is pending, so the person is never stuck', async () => {
  await i18n.changeLanguage('it')
  const onDecline = vi.fn()
  renderWithProviders(<FollowupConsent onAccept={vi.fn()} onDecline={onDecline} busy />)
  await userEvent.click(screen.getByRole('button', { name: 'Non ora' }))
  expect(onDecline).toHaveBeenCalledOnce()
})
