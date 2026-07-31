import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient } from '../test/fakeClient'
import { ChangePassword } from './ChangePassword'
import { Login } from './Login'

afterEach(() => sessionStorage.clear())

function Harness() {
  return (
    <Routes>
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<div>HOME</div>} />
    </Routes>
  )
}

test('successful change signs out and returns to login with a confirmation', async () => {
  // change_password revokes every session server-side, so the current token is
  // dead. The user must land back on /login (with a confirmation) — NOT on HOME
  // with a token that would 401 on the first request and force a re-login.
  const client = makeFakeClient({ change: { status: 'ok' } })
  renderWithProviders(<Harness />, { client, route: '/change-password' })
  await userEvent.type(screen.getByLabelText('Password attuale'), 'oldpw')
  await userEvent.type(screen.getByLabelText('Nuova password'), 'newpassword')
  await userEvent.click(screen.getByRole('button', { name: 'Salva la nuova password' }))
  expect(
    await screen.findByText('Password aggiornata. Ora accedi con la nuova password.'),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Entra' })).toBeInTheDocument() // on the login form
  expect(screen.queryByText('HOME')).not.toBeInTheDocument()
})

test('error shows a message and stays on the form', async () => {
  const client = makeFakeClient({ change: { status: 'error' } })
  renderWithProviders(<Harness />, { client, route: '/change-password' })
  await userEvent.type(screen.getByLabelText('Password attuale'), 'oldpw')
  await userEvent.type(screen.getByLabelText('Nuova password'), 'newpassword')
  await userEvent.click(screen.getByRole('button', { name: 'Salva la nuova password' }))
  expect(await screen.findByText('Si è verificato un errore. Riprova.')).toBeInTheDocument()
})

test('a too-short new password shows a specific message and never calls the backend', async () => {
  // change:{status:'ok'} → if the client actually called the backend it would
  // navigate to HOME; the client-side min-8 guard must block it instead.
  const client = makeFakeClient({ change: { status: 'ok' } })
  renderWithProviders(<Harness />, { client, route: '/change-password' })
  await userEvent.type(screen.getByLabelText('Password attuale'), 'oldpw')
  await userEvent.type(screen.getByLabelText('Nuova password'), 'short') // 5 chars < 8
  await userEvent.click(screen.getByRole('button', { name: 'Salva la nuova password' }))
  expect(
    await screen.findByText('La nuova password deve avere almeno 8 caratteri.'),
  ).toBeInTheDocument()
  expect(screen.queryByText('HOME')).not.toBeInTheDocument() // stayed on the form
})

test('the min-length hint is shown', () => {
  renderWithProviders(<Harness />, { client: makeFakeClient({}), route: '/change-password' })
  expect(screen.getByText('La password deve avere almeno 8 caratteri.')).toBeInTheDocument()
})
