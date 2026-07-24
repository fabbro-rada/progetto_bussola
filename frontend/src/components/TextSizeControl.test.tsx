import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { TextSizeControl } from './TextSizeControl'
import i18n from '../i18n'

test('marks the chosen size as pressed and scales the root variable', async () => {
  await i18n.changeLanguage('it')
  renderWithProviders(<TextSizeControl />)
  await userEvent.click(screen.getByRole('button', { name: 'Molto grande' }))
  expect(screen.getByRole('button', { name: 'Molto grande' })).toHaveAttribute('aria-pressed', 'true')
  expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1.5')
})
