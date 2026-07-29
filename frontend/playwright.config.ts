import { defineConfig } from '@playwright/test'

// End-to-end accessibility audit of the kiosk in a REAL browser (Chromium).
// This complements the jsdom component audit (src/a11y.audit.test.tsx): here
// axe can check what jsdom cannot — color contrast (real layout + CSS) and RTL
// rendering. The API is mocked per-test (no backend/LLM/DB needed); we only
// need the built frontend served. Run with `npm run test:e2e` (NOT part of the
// standard `npm test` gate — it needs the Playwright browser).
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  reporter: [['line']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    viewport: { width: 1280, height: 800 },
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: {
    // Build once and serve the production bundle (closest to what ships).
    command: 'npm run build && npm run preview -- --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 120_000,
    // Build-time env: the token is irrelevant (routes are mocked), API base is
    // same-origin so requests hit paths Playwright intercepts.
    env: { VITE_KIOSK_TOKEN: 'e2e', VITE_API_BASE: '' },
  },
})
