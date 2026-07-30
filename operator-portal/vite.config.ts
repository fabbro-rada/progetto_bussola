/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// The operator portal runs on its own Vite dev server (port 5174, alongside the
// kiosk on 5173); the S5/S6 API is served by the backend on 127.0.0.1:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/operators': 'http://127.0.0.1:8000',
      '/job-requests': 'http://127.0.0.1:8000',
      '/profiles': 'http://127.0.0.1:8000',
    },
  },
  preview: {
    // Vite reuses `server.proxy` for `vite preview` unless overridden here.
    // That's fine for `npm run dev`, but `vite preview` serves the production
    // static build (used by the Playwright a11y e2e's webServer — see
    // playwright.config.ts) and has no business proxying to a dev backend:
    // with server.proxy inherited, navigating to /job-requests, /profiles or
    // /operators would be proxied to :8000 instead of serving the SPA shell,
    // 404-ing (no backend running) before React Router ever gets a chance.
    proxy: {},
  },
  test: {
    // Vitest (jsdom) owns the component/unit tests under src/. The Playwright
    // a11y e2e lives in e2e/ and runs via `npm run test:e2e`, NOT here — keep
    // vitest from collecting its .spec.ts (different runner/globals).
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
