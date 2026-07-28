import { screen } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, SYSTEM_CONFIG } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { SystemConfigPanel } from './SystemConfigPanel'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/config" element={<SystemConfigPanel />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function admin(config: unknown) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) }, systemConfig: config as never })
}

test('renders the config with a reachable badge and per-language voice', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: admin({ status: 'ok', config: SYSTEM_CONFIG }), route: '/config' })
  expect(await screen.findByText('qwen2.5-7b-instruct')).toBeInTheDocument()
  expect(screen.getByText('Raggiungibile')).toBeInTheDocument()
  expect(screen.getByText('solo testo')).toBeInTheDocument()  // ar → text-only
})

test('shows the unreachable badge when the LLM is down', async () => {
  setToken('tok')
  const down = { ...SYSTEM_CONFIG, llm_reachable: false }
  renderWithProviders(harness(), { client: admin({ status: 'ok', config: down }), route: '/config' })
  expect(await screen.findByText('Non raggiungibile')).toBeInTheDocument()
})

test('403 shows the forbidden error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: admin({ status: 'forbidden' }), route: '/config' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: admin({ status: 'unauthorized' }), route: '/config' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})

test('network error shows the retryable message', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: admin({ status: 'error' }), route: '/config' })
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})
