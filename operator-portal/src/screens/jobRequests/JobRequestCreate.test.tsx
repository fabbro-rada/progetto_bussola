import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test/utils'
import { makeFakeClient, operatorWith } from '../../test/fakeClient'
import { setToken } from '../../auth/session'
import { JobRequestCreate } from './JobRequestCreate'

afterEach(() => sessionStorage.clear())

function harness() {
  return (
    <Routes>
      <Route path="/job-requests/new" element={<JobRequestCreate />} />
      <Route path="/job-requests/:id" element={<div>DETAIL</div>} />
    </Routes>
  )
}

test('submits the work-only body and navigates to the created detail', async () => {
  setToken('tok')
  // create defaults to { status: 'ok', job: JOB } (id 7) → navigates to /job-requests/7
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  renderWithProviders(harness(), { client, route: '/job-requests/new' })
  await userEvent.type(screen.getByLabelText('Titolo'), 'Aiuto cuoco')
  await userEvent.type(screen.getByLabelText('Settore'), 'Ristorazione')
  await userEvent.type(screen.getByLabelText(/Competenze richieste/), 'cucina, igiene')
  await userEvent.click(screen.getByRole('button', { name: 'Crea richiesta' }))
  await waitFor(() => expect(screen.getByText('DETAIL')).toBeInTheDocument())
  expect(client.created[0]).toMatchObject({
    title: 'Aiuto cuoco',
    sector: 'Ristorazione',
    required_skills: ['cucina', 'igiene'],
    required_availability: null,
    involves_night_shifts: false,
    required_languages: [],
    training_prerequisites: [],
  })
})
