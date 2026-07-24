import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { StopButton } from './StopButton'
import i18n from '../i18n'

test('calls onStop when clicked', async () => {
  await i18n.changeLanguage('it')
  const onStop = vi.fn()
  renderWithProviders(<StopButton onStop={onStop} />)
  await userEvent.click(screen.getByRole('button', { name: /Ferma/ }))
  expect(onStop).toHaveBeenCalledOnce()
})
