import { screen, waitFor } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../test/utils'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { ProtectedRoute } from './ProtectedRoute'
import { setToken } from './session'

afterEach(() => sessionStorage.clear())

function Harness() {
  return (
    <Routes>
      <Route path="/login" element={<div>LOGIN</div>} />
      <Route path="/change-password" element={<div>CHANGE</div>} />
      <Route path="/" element={<ProtectedRoute><div>PROTECTED</div></ProtectedRoute>} />
    </Routes>
  )
}

test('no operator → redirected to login', async () => {
  renderWithProviders(<Harness />, { client: makeFakeClient({ me: { status: 'unauthorized' } }), route: '/' })
  await waitFor(() => expect(screen.getByText('LOGIN')).toBeInTheDocument())
})

test('authenticated, no gate → renders the protected content', async () => {
  setToken('tok')
  renderWithProviders(<Harness />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ must_change_password: false }) } }),
    route: '/',
  })
  await waitFor(() => expect(screen.getByText('PROTECTED')).toBeInTheDocument())
})

test('must_change_password → redirected to change-password (gate not bypassable)', async () => {
  setToken('tok')
  renderWithProviders(<Harness />, {
    client: makeFakeClient({ me: { status: 'ok', operator: operatorWith({ must_change_password: true }) } }),
    route: '/',
  })
  await waitFor(() => expect(screen.getByText('CHANGE')).toBeInTheDocument())
  expect(screen.queryByText('PROTECTED')).not.toBeInTheDocument()
})
