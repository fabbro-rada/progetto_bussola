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
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
