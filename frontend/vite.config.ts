/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Dev proxy: the SPA runs on the Vite dev server; the S8 API is served by the
// backend on 127.0.0.1:8000 (single-box, localhost — STATO_TECNICO §6).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/kiosk': 'http://127.0.0.1:8000' } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
