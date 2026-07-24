import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Unavailable } from './Unavailable'
import i18n from '../i18n'

test('shows a gentle degrade message and a retry action', async () => {
  await i18n.changeLanguage('it')
  const onRetry = vi.fn()
  renderWithProviders(<Unavailable onRetry={onRetry} />)
  expect(screen.getByText(/Un momento, ci riprovo/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Riprova' }))
  expect(onRetry).toHaveBeenCalledOnce()
})
