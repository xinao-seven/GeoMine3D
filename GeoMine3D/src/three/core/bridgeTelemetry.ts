/**
 * 远程调试遥测：控制台环形缓冲与 FPS 采样。
 *
 * 只在远程控制桥启用时由 remoteControl.ts 安装；采集到的控制台日志
 * （含未捕获异常 / Promise 拒绝）与帧率供 MCP 服务端通过桥命令读取。
 */

export type ConsoleLogLevel = 'log' | 'info' | 'warn' | 'error'

export interface ConsoleLogEntry {
    level: ConsoleLogLevel
    message: string
    time: number
}

export interface BridgeTelemetry {
    getLogs(level?: string, limit?: number): ConsoleLogEntry[]
    clearLogs(): void
    fps(): { fps: number; frameMs: number }
    dispose(): void
}

const MAX_LOGS = 500
const SINGLE_VALUE_LIMIT = 800

export function installBridgeTelemetry(): BridgeTelemetry {
    const logs: ConsoleLogEntry[] = []
    const originals = new Map<ConsoleLogLevel, (...args: unknown[]) => void>()

    function formatValue(value: unknown): string {
        if (typeof value === 'string') return value
        if (value instanceof Error) return value.stack || `${value.name}: ${value.message}`
        if (value !== null && typeof value === 'object') {
            try {
                const text = JSON.stringify(value)
                if (text === undefined) return String(value)
                return text.length > SINGLE_VALUE_LIMIT ? `${text.slice(0, SINGLE_VALUE_LIMIT)}…` : text
            } catch {
                return String(value)
            }
        }
        return String(value)
    }

    function record(level: ConsoleLogLevel, args: unknown[]) {
        logs.push({ level, message: args.map(formatValue).join(' '), time: Date.now() })
        if (logs.length > MAX_LOGS) logs.splice(0, logs.length - MAX_LOGS)
    }

    for (const level of ['log', 'info', 'warn', 'error'] as const) {
        const original = console[level].bind(console)
        originals.set(level, original)
        console[level] = (...args: unknown[]) => {
            record(level, args)
            original(...args)
        }
    }

    const onError = (event: ErrorEvent) => {
        record('error', event.error ? [event.message, event.error] : [event.message])
    }
    const onRejection = (event: PromiseRejectionEvent) => {
        record('error', ['Unhandled rejection:', event.reason])
    }
    window.addEventListener('error', onError)
    window.addEventListener('unhandledrejection', onRejection)

    // FPS 采样：rAF 自转只记时间差，不触发渲染；页面切后台时 rAF 暂停属预期
    let fps = 0
    let frameMs = 0
    let rafId = 0
    let last = performance.now()
    const tick = (now: number) => {
        const dt = now - last
        last = now
        if (dt > 0 && dt < 1000) {
            frameMs = frameMs ? frameMs * 0.9 + dt * 0.1 : dt
            fps = 1000 / frameMs
        }
        rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)

    return {
        getLogs(level = 'all', limit = 200) {
            const filtered = level === 'all' ? logs : logs.filter((entry) => entry.level === level)
            return filtered.slice(-Math.min(limit, MAX_LOGS))
        },
        clearLogs() {
            logs.length = 0
        },
        fps() {
            return { fps: Math.round(fps * 10) / 10, frameMs: Math.round(frameMs * 10) / 10 }
        },
        dispose() {
            for (const [level, original] of originals) console[level] = original
            window.removeEventListener('error', onError)
            window.removeEventListener('unhandledrejection', onRejection)
            cancelAnimationFrame(rafId)
        },
    }
}
