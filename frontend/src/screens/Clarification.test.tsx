import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Clarification } from './Clarification'
import i18n from '../i18n'

test('lets the person correct an incongruence', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Clarification text="Hai detto 5 anni, ma le date dicono 2. È corretto?" onSubmit={onSubmit} />)
  await userEvent.click(screen.getByRole('button', { name: 'No, correggi qualcosa' }))
  await userEvent.type(screen.getByRole('textbox'), 'erano 2 anni')
  await userEvent.click(screen.getByRole('button', { name: 'Invia' }))
  expect(onSubmit).toHaveBeenCalledWith('erano 2 anni')
})
