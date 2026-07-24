import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { LanguagePicker } from './LanguagePicker'

test('shows all five endonyms and reports the chosen code', async () => {
  const onSelect = vi.fn()
  renderWithProviders(<LanguagePicker onSelect={onSelect} />)
  for (const name of ['Italiano', 'English', 'Français', 'Español', 'العربية']) {
    expect(screen.getByRole('button', { name })).toBeInTheDocument()
  }
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  expect(onSelect).toHaveBeenCalledWith('ar')
})
