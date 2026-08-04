import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { Recap } from './Recap'
import i18n from '../i18n'

const PROFILE = {
  pseudonym_id: 'P-1', languages: [{ language: 'it', level: 'fluent' }], digital_literacy: 'basic',
  skills: [{ name: 'cucina', kind: 'technical', evidence: 'stated' }],
  experiences: [{ role: 'consulente', sector: 'IT', duration_months: 24 }],
  aspiration: { fields_of_interest: ['ristorazione'], availability: 'full_time', constraints: [] },
  desired_training: [{ topic: 'HACCP' }], operational_notes: [],
}

test('shows the profile fields (role + person words) and confirms', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Recap profile={PROFILE} onSubmit={onSubmit} />, { language: 'it' })
  expect(screen.getByText('consulente', { exact: false })).toBeInTheDocument()
  expect(screen.getByText('cucina', { exact: false })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è tutto giusto' }))
  expect(onSubmit).toHaveBeenCalled()
})

test('correcting sends the free text', async () => {
  await i18n.changeLanguage('it')
  const onSubmit = vi.fn()
  renderWithProviders(<Recap profile={PROFILE} onSubmit={onSubmit} />, { language: 'it' })
  await userEvent.click(screen.getByRole('button', { name: 'Correggi qualcosa' }))
  await userEvent.type(screen.getByRole('textbox'), 'il consulente era 2 anni')
  await userEvent.click(screen.getByRole('button', { name: 'Invia la correzione' }))
  expect(onSubmit).toHaveBeenCalledWith('il consulente era 2 anni')
})
