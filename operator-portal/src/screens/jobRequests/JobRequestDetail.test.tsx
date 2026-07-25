import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith, JOB, MATCH } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { JobRequestDetail } from './JobRequestDetail'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/job-requests/:id" element={<JobRequestDetail />} />
      <Route path="/login" element={<div>LOGIN</div>} />
    </Routes>
  )
}

test('shows the request then runs matching on click, rendering explainable results', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    job: { status: 'ok', job: JOB },
    match: { status: 'ok', results: [MATCH] },
  })
  renderWithProviders(harness(), { client, route: '/job-requests/7' })
  expect(await screen.findByText('Aiuto cuoco')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Esegui matching' }))
  expect(await screen.findByText('P-4F2A')).toBeInTheDocument()
  expect(client.calls.match).toBe(1)
})

test('no compatible candidates message when match returns empty', async () => {
  setToken('tok')
  const client = makeFakeClient({
    me: { status: 'ok', operator: operatorWith() },
    job: { status: 'ok', job: JOB },
    match: { status: 'ok', results: [] },
  })
  renderWithProviders(harness(), { client, route: '/job-requests/7' })
  await userEvent.click(await screen.findByRole('button', { name: 'Esegui matching' }))
  expect(await screen.findByText('Nessun candidato compatibile.')).toBeInTheDocument()
})
