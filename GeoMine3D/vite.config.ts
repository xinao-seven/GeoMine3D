import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://10.4.61.70:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://10.4.61.70:8000',
        changeOrigin: true,
      },
      '/data': {
        target: 'http://10.4.61.70:8000',
        changeOrigin: true,
      },
    },
  },
})
