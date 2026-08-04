import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Clarification } from './Clarification'
import i18n from '../i18n'

test('is an OPEN question: a free-text answer box (no Sì/No), submitting what the person writes', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(
    <Clarification text="Che cosa facevi di preciso come custode nella scuola?" onSubmit={onSubmit} />,
  )
  // A clarification is NOT a confirmation: no "Sì, è corretto" / "No, correggi qualcosa".
  expect(screen.queryByRole('button', { name: 'Sì, è corretto' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'No, correggi qualcosa' })).not.toBeInTheDocument()
  // The person answers in an open box and sends it.
  await userEvent.type(screen.getByRole('textbox'), 'controllavo gli ingressi e chiudevo la scuola')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))
  expect(onSubmit).toHaveBeenCalledWith('controllavo gli ingressi e chiudevo la scuola')
})
