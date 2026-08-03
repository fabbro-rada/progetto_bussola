import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Refusal } from './Refusal'
import i18n from '../i18n'

test('shows the refusal banner AND re-shows the original question, still accepts a new answer', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Refusal question="Che lavoro ti piacerebbe fare?" onSubmit={onSubmit} />)
  expect(screen.getByText('Posso aiutarti solo con lavoro e formazione.')).toBeInTheDocument()
  expect(screen.getByText('Che lavoro ti piacerebbe fare?')).toBeInTheDocument() // the question is re-shown
  await userEvent.type(screen.getByRole('textbox'), 'cuoco')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))
  expect(onSubmit).toHaveBeenCalledWith('cuoco')
})
