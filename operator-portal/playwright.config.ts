import { defineConfig } from '@playwright/test'

// End-to-end accessibility audit of the operator portal in a REAL browser
// (Chromium). This complements the jsdom component audit (src/a11y.audit.test.tsx):
// here axe can check what jsdom cannot — color contrast (real layout + CSS).
// The API is mocked per-test (no backend needed); we only need the built
// frontend served. The portal is authenticated (unlike the kiosk), so each
// test seeds a session token + mocks `/auth/me` before navigating — see
// e2e/a11y.spec.ts. Run with `npm run test:e2e` (NOT part of the standard
// `npm test` gate — it needs the Playwright browser).
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  reporter: [['line']],
  use: {
    baseURL: 'http://127.0.0.1:4174',
    viewport: { width: 1280, height: 800 },
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: {
    // Build once and serve the production bundle (closest to what ships).
    command: 'npm run build && npm run preview -- --port 4174 --strictPort',
    url: 'http://127.0.0.1:4174',
    // Reuse a running preview locally for fast iteration, but never in CI —
    // there a stale server would silently audit an old build.
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    // Build-time env: API base empty means same-origin requests, so
    // Playwright's page.route can intercept every call the client makes.
    env: { VITE_API_BASE: '' },
  },
})
