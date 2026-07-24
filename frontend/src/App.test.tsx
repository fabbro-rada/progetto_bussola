import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { renderWithProviders } from './test/utils'
import { makeFakeClient, step } from './test/fakeClient'
import { App } from './App'
import type { KioskClient, SubmitResult } from './types'

async function chooseItalianAndConsent() {
  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Ho capito, iniziamo' }))
}

test('happy path: language -> consent -> question -> summary -> completed', async () => {
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Che lavoro sai fare?') },
    submits: [
      { status: 'ok', step: step('summary', 'Ho capito: sai cucinare') },
      { status: 'ok', step: step('completed', 'Grazie!') },
    ],
  })
  renderWithProviders(<App client={client} />)

  await chooseItalianAndConsent()
  expect(await screen.findByText('Che lavoro sai fare?')).toBeInTheDocument()

  await userEvent.type(screen.getByRole('textbox'), 'so cucinare')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))

  expect(await screen.findByText('Ho capito: sai cucinare')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è corretto' }))

  expect(await screen.findByText(/Grazie! Ho raccolto tutto/)).toBeInTheDocument()
  expect(client.calls.answers).toEqual(['so cucinare', 'Sì, è corretto'])
})

test('«Ferma» resets to the language picker from mid-interview', async () => {
  const client = makeFakeClient({ start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Domanda') } })
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText('Domanda')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: /Ferma/ }))
  expect(screen.getByRole('button', { name: 'Italiano' })).toBeInTheDocument()
})

test('«Ferma» is not shown on the language picker (no session yet)', () => {
  renderWithProviders(<App client={makeFakeClient({})} />)
  expect(screen.queryByRole('button', { name: /Ferma/ })).not.toBeInTheDocument()
})

test('backend down on start -> unavailable screen, retry recovers', async () => {
  let firstCall = true
  const base = makeFakeClient({ start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Ripartiti') } })
  const client = {
    ...base,
    async startInterview() {
      if (firstCall) {
        firstCall = false
        return { status: 'unavailable' as const }
      }
      return { status: 'ok' as const, sessionToken: 'tok', step: step('question', 'Ripartiti') }
    },
  }
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText(/Un momento, ci riprovo/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Riprova' }))
  expect(await screen.findByText('Ripartiti')).toBeInTheDocument()
})

test('session expired mid-interview -> back to the language picker', async () => {
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Domanda') },
    submits: [{ status: 'session-expired' }],
  })
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()
  await userEvent.type(await screen.findByRole('textbox'), 'x')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))
  expect(await screen.findByRole('button', { name: 'Italiano' })).toBeInTheDocument()
})

test('unauthorized token -> station-not-authorized screen', async () => {
  const client = makeFakeClient({ start: { status: 'unauthorized' } })
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText(/Questa postazione non è autorizzata/)).toBeInTheDocument()
})

test('choosing Arabic sets the document direction to rtl', async () => {
  renderWithProviders(<App client={makeFakeClient({})} />)
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  expect(document.documentElement.dir).toBe('rtl')
})

test('does not double-submit while a request is in flight; shows pending, disables the button', async () => {
  let releaseSubmit!: (r: SubmitResult) => void
  const inFlight = new Promise<SubmitResult>((res) => { releaseSubmit = res })
  let submitCalls = 0
  const client: KioskClient = {
    async startInterview() {
      return { status: 'ok', sessionToken: 'tok', step: step('summary', 'Ho capito: sai cucinare') }
    },
    async submitAnswer() {
      submitCalls++
      return inFlight
    },
  }
  renderWithProviders(<App client={client} />)
  await chooseItalianAndConsent()

  const yes = await screen.findByRole('button', { name: 'Sì, è corretto' })
  await userEvent.click(yes)

  // pending feedback shown, button disabled
  expect(screen.getByText('Sto elaborando…')).toBeInTheDocument()
  expect(yes).toBeDisabled()

  // a second tap while in flight must NOT fire a second request
  await userEvent.click(yes)
  expect(submitCalls).toBe(1)

  // releasing the request advances normally
  releaseSubmit({ status: 'ok', step: step('completed', 'Grazie!') })
  expect(await screen.findByText(/Grazie/)).toBeInTheDocument()
})
