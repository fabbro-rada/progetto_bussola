import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { Login } from './Login'

afterEach(() => sessionStorage.clear())

function LoginHarness() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<div>HOME</div>} />
      <Route path="/change-password" element={<div>CHANGE</div>} />
    </Routes>
  )
}

test('successful login navigates to home', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'tok', operator: operatorWith(), mustChangePassword: false },
  })
  renderWithProviders(<LoginHarness />, { client, route: '/login' })
  await userEvent.type(screen.getByLabelText('Nome utente'), 'mrossi')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  await waitFor(() => expect(screen.getByText('HOME')).toBeInTheDocument())
})

test('login with must_change_password navigates to change-password', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'tok', operator: operatorWith({ must_change_password: true }), mustChangePassword: true },
  })
  renderWithProviders(<LoginHarness />, { client, route: '/login' })
  await userEvent.type(screen.getByLabelText('Nome utente'), 'mrossi')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  await waitFor(() => expect(screen.getByText('CHANGE')).toBeInTheDocument())
})

test('invalid credentials show a generic message and do not navigate', async () => {
  const client = makeFakeClient({ login: { status: 'invalid' } })
  renderWithProviders(<LoginHarness />, { client, route: '/login' })
  await userEvent.type(screen.getByLabelText('Nome utente'), 'x')
  await userEvent.type(screen.getByLabelText('Password'), 'y')
  await userEvent.click(screen.getByRole('button', { name: 'Entra' }))
  expect(await screen.findByText('Credenziali non valide.')).toBeInTheDocument()
  expect(screen.queryByText('HOME')).not.toBeInTheDocument()
})
