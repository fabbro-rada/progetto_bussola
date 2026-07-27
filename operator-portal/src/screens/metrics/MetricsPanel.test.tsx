import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { MetricsPanel } from './MetricsPanel'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/metrics" element={<MetricsPanel />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function supervisor(metrics: unknown) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, metrics: metrics as never })
}

test('renders the five metrics, completeness as a percentage', async () => {
  setToken('tok')
  const client = supervisor({ status: 'ok', metrics: { total_profiles: 5, completed_profiles: 3, average_completeness: 0.6, total_job_requests: 2, matching_runs: 4 } })
  renderWithProviders(harness(), { client, route: '/metrics' })
  expect(await screen.findByText('60%')).toBeInTheDocument()
  expect(screen.getByText('Profili totali')).toBeInTheDocument()
  expect(screen.getByText('5')).toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
})

test('403 shows the forbidden error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'forbidden' }), route: '/metrics' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'unauthorized' }), route: '/metrics' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})

test('network error shows the retryable message', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'error' }), route: '/metrics' })
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})
