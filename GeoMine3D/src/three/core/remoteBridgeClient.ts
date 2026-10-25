/**
 * 远程调试桥客户端：把 window.__geomine 桥接到后端 WebSocket 中继
 * （/api/v1/remote/ws），使 MCP 服务（backend/mcp_server.py）能远程
 * 调用场景引擎命令。
 *
 * 协议：
 *   → { type: 'invoke', id, command, args: unknown[] }   后端下发命令
 *   ← { type: 'result', id, ok, result? / error? }       本端执行后回包
 *   → { type: 'ping' } / ← { type: 'pong' }              保活
 *
 * 命令按白名单分发：仅 remoteControl api 对象上的函数（含 settlement.*），
 * `handles`（引擎原始句柄，不可序列化）永不暴露；`eval` 逃生舱仅在
 * URL 显式带 ?remote=1 时放行。
 */

import type { BridgeTelemetry } from './bridgeTelemetry'

export interface RemoteBridgeClientOptions {
    api: Record<string, unknown>
    telemetry: BridgeTelemetry
    getProjectId: () => string
    getAllowEval: () => boolean
}

const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 10000
const PING_INTERVAL_MS = 25000
const STATUS_EVENT = 'geomine:remote-bridge'

type BridgeCommand = (...args: never[]) => unknown

export function startRemoteBridgeClient(options: RemoteBridgeClientOptions): () => void {
    const { api, telemetry } = options

    const allowed = new Map<string, BridgeCommand>()
    collectCommands(api, '', allowed)

    let socket: WebSocket | null = null
    let disposed = false
    let attempts = 0
    let pingTimer = 0

    function emitStatus(status: 'connected' | 'reconnecting' | 'closed', detail: Record<string, unknown> = {}) {
        window.dispatchEvent(new CustomEvent(STATUS_EVENT, { detail: { status, ...detail } }))
    }

    function send(payload: Record<string, unknown>) {
        if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(payload))
    }

    async function dispatch(command: string, args: unknown[]): Promise<unknown> {
        if (command === 'eval') {
            if (!options.getAllowEval()) throw new Error('eval 未启用：仅页面 URL 显式带 ?remote=1 时可用')
            // 调试逃生舱：结果必须可 JSON 序列化，由 sanitize 兜底
            return window.eval(String(args[0] ?? ''))
        }
        const command_ = allowed.get(command)
        if (!command_) {
            throw new Error(`未知命令: ${command}（可用: ${[...allowed.keys()].sort().join(', ')}）`)
        }
        return await (command_ as (...args: unknown[]) => unknown)(...args)
    }

    async function handleInvoke(message: { id?: string; command?: string; args?: unknown[] }) {
        const id = String(message.id ?? '')
        if (!id) return
        try {
            const result = await dispatch(String(message.command ?? ''), message.args ?? [])
            send({ type: 'result', id, ok: true, result: sanitize(result) })
        } catch (error) {
            send({
                type: 'result',
                id,
                ok: false,
                error: { message: error instanceof Error ? error.message : String(error) },
            })
        }
    }

    function connect() {
        if (disposed) return
        const projectId = options.getProjectId()
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const url = `${proto}//${window.location.host}/api/v1/remote/ws?projectId=${encodeURIComponent(projectId)}`
        const ws = new WebSocket(url)
        socket = ws

        ws.onopen = () => {
            const firstTry = attempts === 0
            attempts = 0
            if (firstTry) {
                console.info(`[GeoMine3D] 远程调试桥已连接后端中继 (project=${projectId})`)
            }
            pingTimer = window.setInterval(() => send({ type: 'ping' }), PING_INTERVAL_MS)
        }
        ws.onmessage = (event) => {
            let message: { type?: string; sessionId?: string } | null = null
            try {
                message = JSON.parse(String(event.data))
            } catch {
                return
            }
            if (message?.type === 'invoke') void handleInvoke(message as never)
        }
        ws.onclose = () => {
            window.clearInterval(pingTimer)
            if (socket === ws) socket = null
            if (disposed) {
                emitStatus('closed')
                return
            }
            // 后端未启动时只提示一次，之后静默退避重连，避免刷屏
            if (attempts === 0) {
                console.info('[GeoMine3D] 远程调试桥无法连接后端中继，将自动重试')
            }
            emitStatus('reconnecting', { attempts })
            const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempts, RECONNECT_MAX_MS)
            attempts += 1
            window.setTimeout(connect, delay)
        }
        ws.onerror = () => ws.close()
    }

    connect()

    return () => {
        disposed = true
        window.clearInterval(pingTimer)
        socket?.close()
        socket = null
        telemetry.dispose()
    }
}

/** 递归收集 api 上的函数（含 settlement.* 子对象）；handles 明确排除。 */
function collectCommands(source: Record<string, unknown>, prefix: string, out: Map<string, BridgeCommand>) {
    for (const [key, value] of Object.entries(source)) {
        if (key === 'handles') continue
        const name = prefix ? `${prefix}.${key}` : key
        if (typeof value === 'function') {
            out.set(name, value as BridgeCommand)
        } else if (value && typeof value === 'object' && !prefix) {
            collectCommands(value as Record<string, unknown>, name, out)
        }
    }
}

/** 结果必须可 JSON 序列化；失败降级为字符串，保证中继不因坏返回而挂。 */
function sanitize(value: unknown): unknown {
    if (value === undefined) return null
    try {
        JSON.stringify(value)
        return value
    } catch {
        return String(value)
    }
}
