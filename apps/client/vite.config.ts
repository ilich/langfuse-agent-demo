import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI server (apps/server, `make run`) listens on port 8000. Proxying its routes keeps the
// browser on one origin, so the server needs no CORS setup.
const SERVER_URL = process.env.SERVER_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/orders': SERVER_URL,
      '/health': SERVER_URL,
    },
  },
})
