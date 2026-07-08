import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    sourcemap: process.env.VITE_SENTRY_DSN ? true : false,
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://yorkteam.cn',
        changeOrigin: true,
        secure: false,
      },
      '/webhook': {
        target: 'https://yorkteam.cn',
        changeOrigin: true,
        secure: false,
      },
      '/health': {
        target: 'https://yorkteam.cn',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
