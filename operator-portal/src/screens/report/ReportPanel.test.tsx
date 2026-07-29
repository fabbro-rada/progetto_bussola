import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, REPORT } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ReportPanel } from './ReportPanel'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/report" element={<ReportPanel />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function supervisor(overrides: Parameters<typeof makeFakeClient>[0] = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, ...overrides })
}

test('renders a coverage value and a suppressed cell rendered verbatim as «<5»', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ report: { status: 'ok', report: REPORT } }), route: '/report' })
  // coverage
  expect(await screen.findByText('60%')).toBeInTheDocument()
  expect(screen.getByText('Profili totali').previousSibling).toHaveTextContent('5')
  expect(screen.getByText('Colloqui completati').previousSibling).toHaveTextContent('3')
  // suppressed small cells must render verbatim, never expanded/computed
  expect(screen.getAllByText('<5').length).toBeGreaterThan(0)
})

test('403 shows the forbidden error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ report: { status: 'forbidden' } }), route: '/report' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ report: { status: 'unauthorized' } }), route: '/report' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})

test('network error shows the retryable message', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ report: { status: 'error' } }), route: '/report' })
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})

test('«Esporta report» calls createReportExport and shows the pending message (no download UI)', async () => {
  setToken('tok')
  const client = supervisor({ report: { status: 'ok', report: REPORT } })
  renderWithProviders(harness(), { client, route: '/report' })
  await screen.findByText('60%')
  await userEvent.click(screen.getByRole('button', { name: 'Esporta report' }))
  await waitFor(() => expect(client.calls.reportExport).toBe(1))
  expect(await screen.findByText('Richiesta inviata, in attesa di approvazione')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Scarica' })).not.toBeInTheDocument()
})
