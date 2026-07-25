import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { MATCH } from '../../test/fakeClient'
import { MatchResults } from './MatchResults'

afterEach(() => sessionStorage.clear())

test('shows pseudonym, transparent fraction, and (expanded) verdicts with evidence + gaps', async () => {
  renderWithProviders(<MatchResults results={[MATCH]} />)
  expect(screen.getByText('P-4F2A')).toBeInTheDocument()
  expect(screen.getByText('1/2 requisiti')).toBeInTheDocument() // 1 satisfied of 2
  await userEvent.click(screen.getByRole('button', { name: /Dettagli/ }))
  expect(screen.getByText('Esperienza in cucina')).toBeInTheDocument()
  expect(screen.getByText(/ho lavorato in un ristorante/)).toBeInTheDocument()
  expect(screen.getByText(/Corso HACCP base/)).toBeInTheDocument()
})

test('empty results shows the no-candidates message', () => {
  renderWithProviders(<MatchResults results={[]} />)
  expect(screen.getByText('Nessun candidato compatibile.')).toBeInTheDocument()
})
