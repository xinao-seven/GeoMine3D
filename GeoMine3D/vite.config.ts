import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import os from 'node:os'

function getRealtimeIPv4() {
    const interfaces = os.networkInterfaces()

    for (const items of Object.values(interfaces)) {
        if (!items) continue

        for (const item of items) {
            if (item.family !== 'IPv4') continue
            if (item.internal) continue
            if (item.address.startsWith('169.254.')) continue
            return item.address
        }
    }

    return '127.0.0.1'
}

const realtimeIP = getRealtimeIPv4()
const backendTarget = process.env.VITE_BACKEND_URL || `http://${realtimeIP}:8000`

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
