import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Question } from './Question'
import i18n from '../i18n'

test('shows the backend question text and submits the typed answer', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Question text="In quali lingue te la cavi?" onSubmit={onSubmit} />)
  expect(screen.getByText('In quali lingue te la cavi?')).toBeInTheDocument()
  await userEvent.type(screen.getByRole('textbox'), 'italiano e arabo')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))
  expect(onSubmit).toHaveBeenCalledWith('italiano e arabo')
})
