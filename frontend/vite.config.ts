import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Browser calls /api/... ; Vite strips /api and forwards to FastAPI on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
