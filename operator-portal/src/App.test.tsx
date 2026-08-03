import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import i18n from './i18n'
import { AuthProvider } from './auth/AuthContext'
import { App } from './App'
import { makeFakeClient, operatorWith } from './test/fakeClient'
import { setToken } from './auth/session'
import type { OperatorClient } from './types'

afterEach(() => sessionStorage.clear())

function renderApp(client: OperatorClient, route = '/') {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider client={client}>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </I18nextProvider>,
  )
}

test('unauthenticated visit to / lands on login', async () => {
  renderApp(makeFakeClient({ me: { status: 'unauthorized' } }), '/')
  expect(await screen.findByRole('button', { name: 'Entra' })).toBeInTheDocument()
  expect(screen.queryByText('Sessione scaduta. Accedi di nuovo.')).not.toBeInTheDocument()
})

test('stale token invalidated during bootstrap → login shows the session-expired notice', async () => {
  setToken('stale')
  renderApp(makeFakeClient({ me: { status: 'unauthorized' } }), '/')
  expect(await screen.findByRole('button', { name: 'Entra' })).toBeInTheDocument()
  expect(screen.getByText('Sessione scaduta. Accedi di nuovo.')).toBeInTheDocument()
})

test('happy path: login → shell home with the operator name', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'tok', operator: operatorWith({ display_name: 'M. Rossi' }), mustChangePassword: false },
  })
  renderApp(client, '/login')
  await userEvent.type(screen.getByLabelText('Nome utente'), 'mrossi')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  expect(await screen.findByText('Benvenuto/a, M. Rossi')).toBeInTheDocument()
})

test('must_change_password gate: login forces the change screen, home not reachable', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'tok', operator: operatorWith({ must_change_password: true }), mustChangePassword: true },
  })
  renderApp(client, '/login')
  await userEvent.type(screen.getByLabelText('Nome utente'), 'mrossi')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  expect(await screen.findByRole('button', { name: 'Salva la nuova password' })).toBeInTheDocument()
  expect(screen.queryByText(/Benvenuto/)).not.toBeInTheDocument()
})

test('logout returns to login', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  renderApp(client, '/')
  await userEvent.click(await screen.findByRole('button', { name: 'Esci' }))
  expect(await screen.findByRole('button', { name: 'Entra' })).toBeInTheDocument()
})

test('deep link to a protected route while unauthenticated → login', async () => {
  renderApp(makeFakeClient({ me: { status: 'unauthorized' } }), '/profiles')
  expect(await screen.findByRole('button', { name: 'Entra' })).toBeInTheDocument()
})

test('an authenticated operator can reach the new-interview section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } })
  renderApp(client, '/new-interview')
  // «Genera codice» is rendered only by NewInterview → proves the route mounted
  expect(await screen.findByRole('button', { name: 'Genera codice' })).toBeInTheDocument()
})

test('an authenticated operator can navigate to the job-requests section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } })
  renderApp(client, '/job-requests')
  // «Nuova richiesta» is rendered only by JobRequestList → proves the route mounted
  expect(await screen.findByRole('link', { name: 'Nuova richiesta' })).toBeInTheDocument()
})

test('an authenticated operator can reach the profiles section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } })
  renderApp(client, '/profiles')
  // «Cerca» is rendered only by ProfileSearch → proves the route mounted (not just the Nav link)
  expect(await screen.findByRole('button', { name: 'Cerca' })).toBeInTheDocument()
})

test('an authenticated admin can reach the operators section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } })
  renderApp(client, '/operators')
  // «+ Nuovo operatore» is rendered only by OperatorList → proves the route mounted
  expect(await screen.findByRole('button', { name: /Nuovo operatore/ })).toBeInTheDocument()
})

test('an authenticated supervisor can reach the metrics section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  renderApp(client, '/metrics')
  // «Profili totali» is rendered only by MetricsPanel → proves the route mounted
  expect(await screen.findByText('Profili totali')).toBeInTheDocument()
})

test('an authenticated supervisor can reach the report section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  renderApp(client, '/report')
  // «Esporta report» is rendered only by ReportPanel → proves the route mounted
  expect(await screen.findByRole('button', { name: 'Esporta report' })).toBeInTheDocument()
})

test('an operator can reach the export section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'operator' }) } })
  renderApp(client, '/export')
  expect(await screen.findByRole('button', { name: /Nuova richiesta/ })).toBeInTheDocument()
})

test('a supervisor can reach the export-approvals section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  renderApp(client, '/export-approvals')
  // The Nav link and the page <h1> share the same i18n string («Approvazioni export»);
  // scope to the heading role so this proves the route mounted, not just the Nav link.
  expect(await screen.findByRole('heading', { name: 'Approvazioni export' })).toBeInTheDocument()
})

test('an authenticated auditor can reach the audit log section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'auditor' }) } })
  renderApp(client, '/audit')
  // «Verifica integrità» is rendered only by AuditLog → proves the route mounted
  expect(await screen.findByRole('button', { name: 'Verifica integrità' })).toBeInTheDocument()
})

test('an authenticated supervisor can reach the operator-activity section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  renderApp(client, '/activity')
  // «Profili consultati» is a column rendered only by OperatorActivityPanel → proves the route mounted
  expect(await screen.findByText('Profili consultati')).toBeInTheDocument()
})

test('an authenticated admin can reach the system-config section', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } })
  renderApp(client, '/config')
  // «Modello linguistico» is a section heading rendered only by SystemConfigPanel → proves the route mounted
  expect(await screen.findByText('Modello linguistico')).toBeInTheDocument()
})
