import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const usePolling = process.env.VITE_USE_POLLING === 'true'
const watchInterval = Number(process.env.VITE_POLL_INTERVAL || 300)

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: Number(process.env.VITE_PORT || 3000),
    watch: {
      usePolling,
      interval: watchInterval
    },
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
