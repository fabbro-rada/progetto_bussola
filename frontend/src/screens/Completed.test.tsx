import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Completed } from './Completed'
import i18n from '../i18n'

test('thanks the person and finishes', async () => {
  await i18n.changeLanguage('it')
  const onFinish = vi.fn()
  renderWithProviders(<Completed onFinish={onFinish} />)
  expect(screen.getByText(/Grazie! Ho raccolto tutto/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Ho finito' }))
  expect(onFinish).toHaveBeenCalledOnce()
})
