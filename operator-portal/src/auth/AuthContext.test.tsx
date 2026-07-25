import { render, screen, waitFor, act } from '@testing-library/react'
import { expect, test, afterEach } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { makeFakeClient, operatorWith } from '../test/fakeClient'
import { setToken, getToken } from './session'

afterEach(() => sessionStorage.clear())

function Probe() {
  const { operator, loading, mustChangePassword, sessionExpired, login, logout, onUnauthorized } = useAuth()
  return (
    <div>
      <span>loading:{String(loading)}</span>
      <span>op:{operator ? operator.username : 'none'}</span>
      <span>mcp:{String(mustChangePassword)}</span>
      <span>expired:{String(sessionExpired)}</span>
      <button onClick={() => void login('mrossi', 'pw')}>login</button>
      <button onClick={() => void logout()}>logout</button>
      <button onClick={() => onUnauthorized()}>unauthorized</button>
    </div>
  )
}

test('no token on mount → not loading, no operator (no me() call needed)', async () => {
  const client = makeFakeClient({})
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('loading:false')).toBeInTheDocument())
  expect(screen.getByText('op:none')).toBeInTheDocument()
  expect(client.calls.me).toBe(0)
})

test('existing token on mount → me() populates the operator', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ username: 'gverdi' }) } })
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('op:gverdi')).toBeInTheDocument())
  expect(client.calls.me).toBe(1)
})

test('me() 401 on mount → token cleared, no operator, sessionExpired set', async () => {
  setToken('stale')
  const client = makeFakeClient({ me: { status: 'unauthorized' } })
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('op:none')).toBeInTheDocument())
  expect(getToken()).toBeNull()
  await waitFor(() => expect(screen.getByText('expired:true')).toBeInTheDocument())
})

test("me() 'error' on mount (transient) → token kept, no operator, sessionExpired NOT set", async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'error' } })
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('loading:false')).toBeInTheDocument())
  expect(screen.getByText('op:none')).toBeInTheDocument()
  expect(getToken()).toBe('tok')
  expect(screen.getByText('expired:false')).toBeInTheDocument()
})

test('onUnauthorized() sets sessionExpired', async () => {
  const client = makeFakeClient({})
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('loading:false')).toBeInTheDocument())
  expect(screen.getByText('expired:false')).toBeInTheDocument()
  await act(async () => {
    screen.getByText('unauthorized').click()
  })
  expect(screen.getByText('expired:true')).toBeInTheDocument()
})

test('login ok resets sessionExpired to false', async () => {
  setToken('stale')
  const client = makeFakeClient({
    me: { status: 'unauthorized' },
    login: { status: 'ok', token: 'newtok', operator: operatorWith({ username: 'mrossi' }), mustChangePassword: false },
  })
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('expired:true')).toBeInTheDocument())
  await act(async () => {
    screen.getByText('login').click()
  })
  await waitFor(() => expect(screen.getByText('op:mrossi')).toBeInTheDocument())
  expect(screen.getByText('expired:false')).toBeInTheDocument()
})

test('login ok saves token + operator; logout clears them', async () => {
  const client = makeFakeClient({
    login: { status: 'ok', token: 'newtok', operator: operatorWith({ username: 'mrossi' }), mustChangePassword: false },
  })
  render(
    <AuthProvider client={client}>
      <Probe />
    </AuthProvider>,
  )
  await waitFor(() => expect(screen.getByText('loading:false')).toBeInTheDocument())
  await act(async () => {
    screen.getByText('login').click()
  })
  await waitFor(() => expect(screen.getByText('op:mrossi')).toBeInTheDocument())
  expect(getToken()).toBe('newtok')
  await act(async () => {
    screen.getByText('logout').click()
  })
  await waitFor(() => expect(screen.getByText('op:none')).toBeInTheDocument())
  expect(getToken()).toBeNull()
})
