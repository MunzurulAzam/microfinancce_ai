import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    proxy: {
      // In LOCAL dev, forward /api/* → Flask on :5001
      // In PRODUCTION (Vercel build), this proxy is NOT used —
      // VITE_API_BASE_URL in .env points to Render directly.
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
