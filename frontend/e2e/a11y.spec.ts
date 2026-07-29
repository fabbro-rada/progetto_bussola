import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

// End-to-end a11y audit of the kiosk in real Chromium. Complements the jsdom
// component audit: here axe checks color-contrast (real layout+CSS) and RTL —
// the things jsdom cannot. The API is mocked per-test; no backend needed.

// Response shapes mirror kioskClient.ts: start -> {session_token, step};
// submit -> {step}; step.kind drives the screen. Voice endpoints degrade to text.
type Step = { kind: string; text: string }

async function mockKiosk(
  page: Page,
  opts: { startStatus?: number; firstStep?: Step; nextStep?: Step } = {},
): Promise<void> {
  const first = opts.firstStep ?? { kind: 'question', text: 'Che lavoro sai fare?' }
  const next = opts.nextStep ?? { kind: 'summary', text: 'Ecco cosa ho capito di te.' }
  await page.route('**/kiosk/interview/start', (route) => {
    if (opts.startStatus && opts.startStatus !== 200) {
      return route.fulfill({ status: opts.startStatus, contentType: 'application/json', body: '{}' })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ session_token: 'e2e-token', step: first }),
    })
  })
  await page.route('**/kiosk/interview/submit', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ step: next }) }),
  )
  // Voice off: transcribe/synthesize -> no audio, degrade to text (§3), never hang.
  await page.route('**/kiosk/voice/**', (route) => route.fulfill({ status: 204, body: '' }))
}

async function audit(page: Page, label: string): Promise<void> {
  // WCAG 2 A/AA, INCLUDING color-contrast (the whole reason for a real browser).
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  const summary = violations.map((v) => ({ id: v.id, help: v.help, nodes: v.nodes.map((n) => n.target) }))
  expect(violations, `${label} a11y violations:\n${JSON.stringify(summary, null, 2)}`).toEqual([])
}

// Drive language -> consent -> question -> submit, landing on `nextStep`'s screen.
async function reachAfterSubmit(page: Page, nextStep: Step): Promise<void> {
  await mockKiosk(page, { nextStep })
  await page.goto('/')
  await page.getByRole('button', { name: 'Italiano' }).click()
  await page.locator('.big-confirm').click() // accept consent -> question
  await expect(page.locator('.prompt-text')).toBeVisible()
  await page.getByPlaceholder('Scrivi qui la tua risposta…').fill('faccio il cuoco')
  await page.getByRole('button', { name: 'Avanti' }).click()
}

test('language picker (entry screen)', async ({ page }) => {
  await mockKiosk(page)
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Italiano' })).toBeVisible()
  await audit(page, 'language-picker')
})

test('consent screen — Italian', async ({ page }) => {
  await mockKiosk(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Italiano' }).click()
  await expect(page.getByRole('button', { name: 'Ho capito, iniziamo' })).toBeVisible()
  await audit(page, 'consent-it')
})

test('consent screen — Arabic (RTL)', async ({ page }) => {
  await mockKiosk(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'العربية' }).click()
  await expect(page.locator('.big-confirm')).toBeVisible() // on the Consent screen (not a fallback)
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await audit(page, 'consent-ar-rtl')
})

test('question screen — Arabic (RTL)', async ({ page }) => {
  await mockKiosk(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'العربية' }).click()
  await page.locator('.big-confirm').click() // consent accept (language-neutral selector)
  await expect(page.locator('.prompt-text')).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await audit(page, 'question-ar-rtl')
})

test('question screen — Italian', async ({ page }) => {
  await mockKiosk(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Italiano' }).click()
  await page.locator('.big-confirm').click()
  await expect(page.locator('.prompt-text')).toBeVisible()
  await audit(page, 'question-it')
})

test('summary screen', async ({ page }) => {
  await reachAfterSubmit(page, { kind: 'summary', text: 'Ecco cosa ho capito di te.' })
  await expect(page.getByText('Ecco cosa ho capito di te.')).toBeVisible()
  await audit(page, 'summary')
})

test('clarification screen', async ({ page }) => {
  await reachAfterSubmit(page, { kind: 'clarification', text: 'Una cosa non mi torna: puoi chiarire?' })
  await expect(page.getByText('Una cosa non mi torna: puoi chiarire?')).toBeVisible()
  await audit(page, 'clarification')
})

test('refusal screen', async ({ page }) => {
  await reachAfterSubmit(page, { kind: 'refusal', text: 'Restiamo sul lavoro.' })
  await expect(page.getByText('Posso aiutarti solo con lavoro e formazione.')).toBeVisible()
  await audit(page, 'refusal')
})

test('unavailable screen', async ({ page }) => {
  await reachAfterSubmit(page, { kind: 'unavailable', text: '' })
  await expect(page.getByRole('button', { name: 'Riprova' })).toBeVisible()
  await audit(page, 'unavailable')
})

test('completed screen', async ({ page }) => {
  await reachAfterSubmit(page, { kind: 'completed', text: '' })
  await expect(page.getByRole('button', { name: 'Ho finito' })).toBeVisible()
  await audit(page, 'completed')
})

test('unauthorized screen', async ({ page }) => {
  await mockKiosk(page, { startStatus: 401 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Italiano' }).click()
  await page.locator('.big-confirm').click() // accept -> start returns 401
  await expect(page.getByText('Questa postazione non è autorizzata. Chiedi aiuto a un operatore.')).toBeVisible()
  await audit(page, 'unauthorized')
})
