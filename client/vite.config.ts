import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  define: {
    'process.env.VITE_API_BASE_URL': JSON.stringify(process.env.VITE_API_BASE_URL || 'http://localhost:8000'),
  },
  optimizeDeps: {
    include: ['@pipecat-ai/client-js', '@pipecat-ai/websocket-transport']
  },
  resolve: {
    alias: {
      'events': 'events'
    }
  }
})
