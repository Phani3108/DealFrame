import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: parseInt(process.env.PORT || '3000', 10),
    proxy: {
      '/api': 'http://localhost:8002',
      '/health': 'http://localhost:8002',
      '/docs': 'http://localhost:8002',
      '/redoc': 'http://localhost:8002',
      '/openapi.json': 'http://localhost:8002',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
