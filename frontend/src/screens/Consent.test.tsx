import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Consent } from './Consent'
import i18n from '../i18n'

test('shows the consent points and wires accept/decline', async () => {
  await i18n.changeLanguage('it')
  const onAccept = vi.fn()
  const onDecline = vi.fn()
  renderWithProviders(<Consent onAccept={onAccept} onDecline={onDecline} />)
  expect(screen.getByText('Prima di iniziare 👋')).toBeInTheDocument()
  expect(screen.getByText(/Niente reati, niente salute, niente famiglia/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Ho capito, iniziamo' }))
  expect(onAccept).toHaveBeenCalledOnce()
  await userEvent.click(screen.getByRole('button', { name: 'Non ora' }))
  expect(onDecline).toHaveBeenCalledOnce()
})
