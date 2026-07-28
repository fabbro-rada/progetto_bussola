import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { OperatorActivityPanel } from './OperatorActivityPanel'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/activity" element={<OperatorActivityPanel />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function supervisor(activity: unknown) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) }, activity: activity as never })
}

test('renders a row per operator with the work-action counts', async () => {
  setToken('tok')
  const client = supervisor({ status: 'ok', activity: [
    { actor: 'm.rossi', profiles_viewed: 4, profiles_searched: 2, matchings_run: 1, exports_requested: 1, exports_downloaded: 0, last_active: '2026-07-27T10:00:00Z' },
  ] })
  renderWithProviders(harness(), { client, route: '/activity' })
  expect(await screen.findByText('m.rossi')).toBeInTheDocument()
  expect(screen.getByText('4')).toBeInTheDocument()   // profiles_viewed
  expect(screen.getByText('Profili consultati')).toBeInTheDocument()
})

test('empty state when there is no activity', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'ok', activity: [] }), route: '/activity' })
  expect(await screen.findByText('Nessuna attività registrata.')).toBeInTheDocument()
})

test('403 shows the forbidden error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'forbidden' }), route: '/activity' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'unauthorized' }), route: '/activity' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})

test('network error shows the retryable message', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: supervisor({ status: 'error' }), route: '/activity' })
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})
