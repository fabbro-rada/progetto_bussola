import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, REPORT, EXPORT_REQUEST } from '../../test/fakeClient'
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

test('«Esporta report» exports (auto-approved) and offers immediate JSON/CSV download', async () => {
  setToken('tok')
  const saved: { name: string }[] = []
  const client = supervisor({
    report: { status: 'ok', report: REPORT },
    createReportExp: { status: 'ok', request: { ...EXPORT_REQUEST, id: 42, kind: 'report', status: 'approved' } },
  })
  function harnessWithSave() {
    return (
      <Routes>
        <Route path="/report" element={<ReportPanel saveBlob={(_b, name) => saved.push({ name })} />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    )
  }
  renderWithProviders(harnessWithSave(), { client, route: '/report' })
  await screen.findByText('60%')
  await userEvent.click(screen.getByRole('button', { name: 'Esporta report' }))
  await waitFor(() => expect(client.calls.reportExport).toBe(1))
  // No "awaiting approval" dead-end: download buttons appear right away.
  const jsonBtn = await screen.findByRole('button', { name: 'Scarica JSON' })
  const csvBtn = screen.getByRole('button', { name: 'Scarica CSV' })

  await userEvent.click(jsonBtn)
  await waitFor(() => expect(client.downloadedIds).toContain(42))
  await userEvent.click(csvBtn)
  await waitFor(() => expect(client.downloadFormats).toContain('csv'))
  expect(saved.map((s) => s.name)).toEqual(['report.json', 'report.csv'])
})
