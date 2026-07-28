import { axe } from 'vitest-axe'

// Component-level a11y audit helper (mirrors the kiosk's). jsdom does not
// compute layout or CSS, so color-contrast cannot run here — contrast is a
// manual / e2e (real-browser) check. We also disable page-structure rules that
// only make sense for a whole document, not a screen rendered on its own; those
// belong to a future Playwright e2e audit against the running portal.
const DISABLED_RULES = [
  'region',
  'landmark-one-main',
  'landmark-unique',
  'landmark-complementary-is-top-level',
  'page-has-heading-one',
  'document-title',
  'html-has-lang',
  'html-lang-valid',
  'bypass',
  'color-contrast', // needs layout + canvas text metrics; jsdom has neither
] as const

const OPTIONS = {
  rules: Object.fromEntries(DISABLED_RULES.map((id) => [id, { enabled: false }])),
}

// Runs axe on a rendered container and throws a readable error listing each
// violation (rule, help, offending selectors) if any component-level issue is
// found. Using the runner directly (not the matcher) keeps typing simple.
export async function expectNoA11yViolations(container: Element): Promise<void> {
  const results = await axe(container, OPTIONS)
  if (results.violations.length === 0) return
  const report = results.violations
    .map((v) => {
      const where = v.nodes.map((n) => `      ${n.target.join(', ')}`).join('\n')
      return `  • [${v.impact ?? 'n/a'}] ${v.id}: ${v.help}\n${where}\n      ${v.helpUrl}`
    })
    .join('\n')
  throw new Error(`${results.violations.length} a11y violation(s):\n${report}`)
}
