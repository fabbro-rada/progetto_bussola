import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, AUDIT_ENTRY } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { AuditLog, LIMIT } from './AuditLog'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/audit" element={<AuditLog />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

function auditor(overrides = {}) {
  return makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'auditor' }) }, ...overrides })
}

test('lists entries on mount', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: auditor(), route: '/audit' })
  expect(await screen.findByText('profile_viewed')).toBeInTheDocument()
  expect(screen.getByText('P-4F2A')).toBeInTheDocument()
})

test('«Cerca» sends the set filters', async () => {
  setToken('tok')
  const client = auditor()
  renderWithProviders(harness(), { client, route: '/audit' })
  await screen.findByText('profile_viewed')
  await userEvent.type(screen.getByLabelText('Attore'), 'm.rossi')
  await userEvent.type(screen.getByLabelText('Azione'), 'profile_viewed')
  await userEvent.click(screen.getByRole('button', { name: 'Cerca' }))
  await waitFor(() => expect(client.auditQueries.at(-1)).toMatchObject({ actor: 'm.rossi', action: 'profile_viewed', limit: LIMIT }))
})

test('«Carica altri» pages with before=<last id> and appends; hides at end', async () => {
  setToken('tok')
  const full = Array.from({ length: LIMIT }, (_, i) => ({ ...AUDIT_ENTRY, id: 100 - i, action: 'a' + (100 - i) }))
  const client = auditor({ auditPages: [
    { status: 'ok', entries: full },                                   // mount: full page → hasMore
    { status: 'ok', entries: [{ ...AUDIT_ENTRY, id: 40, action: 'older' }] },  // load-more: short page → end
  ] })
  renderWithProviders(harness(), { client, route: '/audit' })
  await screen.findByText('a100')
  await userEvent.click(screen.getByRole('button', { name: 'Carica altri' }))
  await waitFor(() => expect(screen.getByText('older')).toBeInTheDocument())
  expect(client.auditQueries.at(-1)).toMatchObject({ before: 51 }) // full[49].id = 100-49 = 51
  expect(screen.queryByRole('button', { name: 'Carica altri' })).not.toBeInTheDocument()
})

test('«Verifica integrità»: green badge on an intact chain', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: auditor(), route: '/audit' })
  await screen.findByText('profile_viewed')
  await userEvent.click(screen.getByRole('button', { name: 'Verifica integrità' }))
  expect(await screen.findByText('Catena integra')).toBeInTheDocument()
})

test('«Verifica integrità»: red badge with the broken row on a tampered chain', async () => {
  setToken('tok')
  const client = auditor({ verify: { status: 'ok', verification: { ok: false, broken_at: 7, reason: 'prev_hash mismatch' } } })
  renderWithProviders(harness(), { client, route: '/audit' })
  await screen.findByText('profile_viewed')
  await userEvent.click(screen.getByRole('button', { name: 'Verifica integrità' }))
  expect(await screen.findByText('Manomissione rilevata alla riga 7')).toBeInTheDocument()
})

test('empty state when the log has no entries', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: auditor({ audit: { status: 'ok', entries: [] } }), route: '/audit' })
  expect(await screen.findByText('Nessuna voce.')).toBeInTheDocument()
})

test('403 on mount shows the error, not a stuck spinner', async () => {
  setToken('tok')
  renderWithProviders(harness(), { client: auditor({ audit: { status: 'forbidden' } }), route: '/audit' })
  expect(await screen.findByText('Non hai i permessi per questa azione.')).toBeInTheDocument()
  expect(screen.queryByText('Caricamento…')).not.toBeInTheDocument()
})
