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
  expect(screen.getByText(/Vincoli ok/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Dettagli/ }))
  expect(screen.getByText('Esperienza in cucina')).toBeInTheDocument()
  expect(screen.getByText(/ho lavorato in un ristorante/)).toBeInTheDocument()
  expect(screen.getByText('Attestato HACCP')).toBeInTheDocument()
  expect(screen.getByText('non risulta')).toBeInTheDocument()
  expect(screen.getByText(/Corso HACCP base/)).toBeInTheDocument()
})

test('empty results shows the no-candidates message', () => {
  renderWithProviders(<MatchResults results={[]} />)
  expect(screen.getByText('Nessun candidato compatibile.')).toBeInTheDocument()
})

test('an incompatible candidate shows the fail badge and its reasons, not "Vincoli ok"', async () => {
  const incompatible = {
    pseudonym_id: 'P-9C1B',
    score: 0,
    requirements: [],
    constraint: { compatible: false, reasons: ['Richiede turni notturni; non disponibile la notte'] },
    gaps: [],
  }
  renderWithProviders(<MatchResults results={[incompatible]} />)
  expect(screen.getByText(/Vincoli non compatibili/)).toBeInTheDocument()
  expect(screen.queryByText(/Vincoli ok/)).not.toBeInTheDocument()
  // reasons show once expanded
  await userEvent.click(screen.getByRole('button', { name: /Dettagli/ }))
  expect(screen.getByText(/Richiede turni notturni/)).toBeInTheDocument()
})
