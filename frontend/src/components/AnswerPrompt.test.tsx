import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { AnswerPrompt } from './AnswerPrompt'
import i18n from '../i18n'

test('submits the trimmed answer and clears the field; empty is ignored', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<AnswerPrompt text="Che lavoro sai fare?" onSubmit={onSubmit} />)
  expect(screen.getByText('Che lavoro sai fare?')).toBeInTheDocument()

  const next = screen.getByRole('button', { name: 'Avanti' })
  await userEvent.click(next)
  expect(onSubmit).not.toHaveBeenCalled() // empty ignored (button disabled)

  await userEvent.type(screen.getByRole('textbox'), '  so cucinare  ')
  await userEvent.click(next)
  expect(onSubmit).toHaveBeenCalledWith('so cucinare')
})

test('renders an optional banner (used by the refusal screen)', () => {
  renderWithProviders(<AnswerPrompt text="Torniamo a te" onSubmit={vi.fn()} banner="Solo lavoro" />)
  expect(screen.getByText('Solo lavoro')).toBeInTheDocument()
})
