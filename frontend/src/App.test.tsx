import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { renderWithProviders } from './test/utils'
import { makeFakeClient, makeVoiceClient, noopVoiceClient, step } from './test/fakeClient'
import { App } from './App'
import type { KioskClient, SubmitResult } from './types'

async function chooseItalianAndConsent() {
  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Ho capito, iniziamo' }))
}

// Follow-up path helper (Sottosistema 29, Task 6): opens the discreet link
// from the language picker, picks a language + types a code on the new
// follow-up entry screen, and submits — landing on the follow-up
// consent/recap. Mirrors `chooseItalianAndConsent` above but stops one screen
// earlier so callers can assert on accept/decline separately (the whole
// point of that screen being a first-class, consequence-free choice, §4).
// The submit button is looked up positionally (last button in the DOM):
// its label is in whatever language was just chosen, which after an Arabic
// tile tap is Arabic script, not a fixed string.
async function openFollowupWithCode(languageName: string, code: string) {
  await userEvent.click(await screen.findByRole('button', { name: /follow-up/i }))
  await userEvent.click(await screen.findByRole('button', { name: languageName }))
  const input = document.querySelector('#followup-token') as HTMLInputElement
  await userEvent.type(input, code)
  const buttons = screen.getAllByRole('button')
  await userEvent.click(buttons[buttons.length - 1])
}

test('happy path: language -> consent -> question -> summary -> completed', async () => {
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Che lavoro sai fare?') },
    submits: [
      { status: 'ok', step: step('summary', 'Ho capito: sai cucinare') },
      { status: 'ok', step: step('completed', 'Grazie!') },
    ],
  })
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)

  await chooseItalianAndConsent()
  expect(await screen.findByText('Che lavoro sai fare?')).toBeInTheDocument()

  await userEvent.type(screen.getByRole('textbox'), 'so cucinare')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))

  expect(await screen.findByText('Ho capito: sai cucinare')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Sì, è corretto' }))

  expect(await screen.findByText(/Grazie! Ho raccolto tutto/)).toBeInTheDocument()
  expect(client.calls.answers).toEqual(['so cucinare', 'Sì, è corretto'])
})

test('after a correction, the updated summary shows the Sì/No choice again (not the text box)', async () => {
  // Live-test bug: correcting a summary re-summarized but left the free-text box
  // up instead of the Sì/No choice, because summary→summary reused the same
  // ConfirmCorrect. Keying screens by stepSeq remounts it fresh.
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Che lavoro sai fare?') },
    submits: [
      { status: 'ok', step: step('summary', 'Ho capito: falegname e muratore') },
      { status: 'ok', step: step('summary', 'Ho capito: falegname, muratore e cameriere') },
    ],
  })
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
  await chooseItalianAndConsent()

  await userEvent.type(await screen.findByRole('textbox'), 'falegname e muratore')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))

  expect(await screen.findByText('Ho capito: falegname e muratore')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'No, correggi qualcosa' }))
  await userEvent.type(screen.getByRole('textbox'), 'so fare anche il cameriere')
  await userEvent.click(screen.getByRole('button', { name: 'Invia' }))

  expect(await screen.findByText('Ho capito: falegname, muratore e cameriere')).toBeInTheDocument()
  // the Sì/No choice is back, and there is no free-text box
  expect(screen.getByRole('button', { name: 'Sì, è corretto' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'No, correggi qualcosa' })).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(client.calls.answers).toEqual(['falegname e muratore', 'so fare anche il cameriere'])
})

test('a refusal re-shows the question that was asked, with the scope banner', async () => {
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Che lavoro sai fare?') },
    submits: [{ status: 'ok', step: step('refusal', 'Restiamo sul lavoro.') }],
  })
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
  await chooseItalianAndConsent()

  await userEvent.type(await screen.findByRole('textbox'), 'che tempo fa domani?')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))

  expect(await screen.findByText('Posso aiutarti solo con lavoro e formazione.')).toBeInTheDocument()
  expect(screen.getByText('Che lavoro sai fare?')).toBeInTheDocument() // original question re-shown
})

test('«Ferma» resets to the language picker from mid-interview', async () => {
  const client = makeFakeClient({ start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Domanda') } })
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText('Domanda')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: /Ferma/ }))
  expect(screen.getByRole('button', { name: 'Italiano' })).toBeInTheDocument()
})

test('«Ferma» is not shown on the language picker (no session yet)', () => {
  renderWithProviders(<App client={makeFakeClient({})} voiceClient={noopVoiceClient} />)
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
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
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
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
  await chooseItalianAndConsent()
  await userEvent.type(await screen.findByRole('textbox'), 'x')
  await userEvent.click(screen.getByRole('button', { name: 'Avanti' }))
  expect(await screen.findByRole('button', { name: 'Italiano' })).toBeInTheDocument()
})

test('unauthorized token -> station-not-authorized screen', async () => {
  const client = makeFakeClient({ start: { status: 'unauthorized' } })
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText(/Questa postazione non è autorizzata/)).toBeInTheDocument()
})

test('choosing Arabic sets the document direction to rtl', async () => {
  renderWithProviders(<App client={makeFakeClient({})} voiceClient={noopVoiceClient} />)
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  expect(document.documentElement.dir).toBe('rtl')
})

test('declining consent in Arabic returns to an ltr language picker', async () => {
  renderWithProviders(<App client={makeFakeClient({})} voiceClient={noopVoiceClient} />)
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  await userEvent.click(await screen.findByRole('button', { name: /ليس الآن|Non ora/ }))
  expect(document.documentElement.dir).toBe('ltr')
})

test('«Ferma» during an in-flight submit is not undone by the late response', async () => {
  let releaseSubmit!: (r: SubmitResult) => void
  const inFlight = new Promise<SubmitResult>((res) => { releaseSubmit = res })
  const client: KioskClient = {
    async startInterview() {
      return { status: 'ok', sessionToken: 'tok', step: step('summary', 'RECAP PRIVATO') }
    },
    async submitAnswer() { return inFlight },
    async startFollowup() { return { status: 'unavailable' } },
  }
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
  await chooseItalianAndConsent()
  await userEvent.click(await screen.findByRole('button', { name: 'Sì, è corretto' }))
  // stop while the submit is pending
  await userEvent.click(screen.getByRole('button', { name: /Ferma/ }))
  expect(screen.getByRole('button', { name: 'Italiano' })).toBeInTheDocument()
  // late response must NOT resurrect the interview
  releaseSubmit({ status: 'ok', step: step('completed', 'Grazie!') })
  // allow the microtask to flush; still on the picker
  expect(await screen.findByRole('button', { name: 'Italiano' })).toBeInTheDocument()
  expect(screen.queryByText('RECAP PRIVATO')).not.toBeInTheDocument()
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
    async startFollowup() { return { status: 'unavailable' } },
  }
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
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

test('auto-reads the interview question via synthesize when a step appears', async () => {
  const fakeVoice = makeVoiceClient({ audio: null })
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Che lavoro sai fare?') },
  })
  renderWithProviders(<App client={client} voiceClient={fakeVoice} />)
  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Ho capito, iniziamo' }))
  await screen.findByText('Che lavoro sai fare?')
  await waitFor(() =>
    expect(fakeVoice.calls.synthesize.some((c) => c.text === 'Che lavoro sai fare?' && c.language === 'it')).toBe(true),
  )
})

// --- Follow-up path (Sottosistema 29, Task 6) -------------------------------
// Additive: a discreet link on the language picker, a token+language entry
// screen, and a follow-up-specific consent/recap — none of it touches the
// first-interview flow exercised by the tests above.

test('follow-up: valid code -> consent recap -> accept sends BOTH the token and the chosen language, reaches the first question', async () => {
  const client = makeFakeClient({
    startFollowup: { status: 'ok', sessionToken: 'tok', step: step('question', 'Come è andata di recente?') },
  })
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)

  await openFollowupWithCode('Italiano', 'F-ABC123')

  // Voluntariness (§4): a recap/consent screen, with an accept action, shows
  // BEFORE anything is sent.
  expect(client.calls.followup).toBeNull()
  await userEvent.click(await screen.findByRole('button', { name: 'Sì, aggiorniamo' }))

  expect(await screen.findByText('Come è andata di recente?')).toBeInTheDocument()
  expect(client.calls.followup).toEqual({ token: 'F-ABC123', language: 'it' })
})

test('follow-up: declining the recap returns to the neutral entry — no session started, no submit ever sent', async () => {
  const client = makeFakeClient({})
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)

  await openFollowupWithCode('Italiano', 'F-ABC123')

  await userEvent.click(await screen.findByRole('button', { name: 'Non ora' }))
  expect(await screen.findByRole('button', { name: 'Italiano' })).toBeInTheDocument()
  expect(client.calls.followup).toBeNull() // start-followup was never called
  expect(client.calls.answers).toEqual([]) // and nothing was ever submitted
})

test('follow-up: an invalid/expired/used token fails closed to the gentle unavailable screen (no crash, no leak of why)', async () => {
  const client = makeFakeClient({ startFollowup: { status: 'unauthorized' } })
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)

  await openFollowupWithCode('Italiano', 'F-BAD')
  await userEvent.click(await screen.findByRole('button', { name: 'Sì, aggiorniamo' }))

  expect(await screen.findByText(/Un momento, ci riprovo/)).toBeInTheDocument()
  // Specifically NOT the station-not-authorized screen — that would
  // misdirect the person (and any operator helping them) toward a device
  // problem that doesn't exist.
  expect(screen.queryByText(/Questa postazione non è autorizzata/)).not.toBeInTheDocument()
})

test('«Ferma» resets from mid-follow-up-entry back to the language picker', async () => {
  renderWithProviders(<App client={makeFakeClient({})} voiceClient={noopVoiceClient} />)
  await openFollowupWithCode('Italiano', 'F-ABC123')
  await userEvent.click(screen.getByRole('button', { name: /Ferma/ }))
  expect(screen.getByRole('button', { name: 'Italiano' })).toBeInTheDocument()
})

test('follow-up: choosing Arabic on the entry screen sets rtl; declining the recap resets to ltr', async () => {
  renderWithProviders(<App client={makeFakeClient({})} voiceClient={noopVoiceClient} />)
  await openFollowupWithCode('العربية', 'F-1')
  expect(document.documentElement.dir).toBe('rtl')

  await userEvent.click(await screen.findByRole('button', { name: /ليس الآن|Non ora/ }))
  expect(document.documentElement.dir).toBe('ltr')
})

test('the default language-picker tap still starts a brand new first interview, unaffected by the follow-up entry point', async () => {
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Che lavoro sai fare?') },
  })
  renderWithProviders(<App client={client} voiceClient={noopVoiceClient} />)
  await chooseItalianAndConsent()
  expect(await screen.findByText('Che lavoro sai fare?')).toBeInTheDocument()
  expect(client.calls.followup).toBeNull()
})

// Fix round 1 (§4 accessibility): FollowupEntry now narrates via VoiceBar.
// This proves the deeper wiring behind it — picking a tile there retargets
// the app's actual voice-narration language immediately (not only once the
// whole form is submitted), the same way `auto-reads the interview question
// via synthesize` above proves it for the first-interview LanguagePicker.
test('follow-up: picking Arabic on the entry screen narrates in Arabic right away, before the code is even submitted', async () => {
  const fakeVoice = makeVoiceClient({ audio: null })
  renderWithProviders(<App client={makeFakeClient({})} voiceClient={fakeVoice} />)
  await userEvent.click(await screen.findByRole('button', { name: /follow-up/i }))
  await userEvent.click(await screen.findByRole('button', { name: 'العربية' }))
  await waitFor(() => expect(fakeVoice.calls.synthesize.some((c) => c.language === 'ar')).toBe(true))
})
