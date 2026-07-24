import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Summary } from './Summary'
import i18n from '../i18n'

test('shows the recap and confirms with one tap', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Summary text="Ecco cosa ho capito: sai cucinare" onSubmit={onSubmit} />)
  expect(screen.getByText('Ecco cosa ho capito: sai cucinare')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è corretto' }))
  expect(onSubmit).toHaveBeenCalledWith('Sì, è corretto')
})
