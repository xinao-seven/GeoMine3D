import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const backendTarget = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'

export default defineConfig({
    plugins: [vue()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        host: true,
        port: 5173,
        proxy: {
            '/api': {
                target: backendTarget,
                changeOrigin: true,
            },
            '/static': {
                target: backendTarget,
                changeOrigin: true,
            },
            '/data': {
                target: backendTarget,
                changeOrigin: true,
            },
        },
    },
})
