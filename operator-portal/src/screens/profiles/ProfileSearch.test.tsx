import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, PROFILE } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { ProfileSearch } from './ProfileSearch'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/profiles" element={<ProfileSearch />} />
      <Route path="/profiles/:pseudonym" element={<div>DETAIL</div>} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

test('loads all profiles on mount and links each row to its detail', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profiles: { status: 'ok', profiles: [PROFILE] } })
  renderWithProviders(harness(), { client, route: '/profiles' })
  expect(await screen.findByRole('link', { name: 'P-4F2A' })).toHaveAttribute('href', '/profiles/P-4F2A')
  expect(client.searched[0]).toEqual({}) // mount search: no filters
})

test('«Cerca» sends the set filters', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profiles: { status: 'ok', profiles: [PROFILE] } })
  renderWithProviders(harness(), { client, route: '/profiles' })
  await screen.findByRole('link', { name: 'P-4F2A' })
  await userEvent.type(screen.getByLabelText('Competenza'), 'cucina')
  await userEvent.click(screen.getByRole('button', { name: 'Cerca' }))
  await waitFor(() => expect(client.searched.at(-1)).toEqual({ skill_query: 'cucina' }))
})

test('empty state when no profiles match', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profiles: { status: 'ok', profiles: [] } })
  renderWithProviders(harness(), { client, route: '/profiles' })
  expect(await screen.findByText('Nessun profilo trovato.')).toBeInTheDocument()
})

test('401 redirects to login', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() }, profiles: { status: 'unauthorized' } })
  renderWithProviders(harness(), { client, route: '/profiles' })
  expect(await screen.findByText('LOGIN')).toBeInTheDocument()
})
