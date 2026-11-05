/**
 * 建模进度订阅（SSE）。
 *
 * 后端 `GET /api/v1/modeling-jobs/{id}/events` 每推一帧形如：
 *   id: <stream-entry-id>
 *   event: progress | done
 *   data: {"stage": "界面插值", "percent": 21.3, "message": "界面插值 5/15 ..."}
 *
 * 为什么用 EventSource 而不是 WebSocket：
 * - 进度是单向推送，不需要双向通道；
 * - 浏览器原生自动重连，并且会**自动带上 `Last-Event-ID`**，后端据此只补发漏掉的帧
 *   （这也是后端用 Redis Stream 而不是 Pub/Sub 的原因）；
 * - 走普通 HTTP，Vite 代理/Nginx/浏览器缓存策略都按常规处理，无需额外握手协议。
 *
 * 降级：浏览器不支持 EventSource、或连续重连失败（后端没启用 Redis 队列 / 中间层把
 * 长连接掐掉）时，回调 `onFallback`，由调用方退回原来的轮询。
 */

export interface ModelingProgressFrame {
  stage: string
  percent: number
  message: string
}

export interface ModelingProgressHandlers {
  /** 每收到一帧进度回调一次 */
  onProgress?: (frame: ModelingProgressFrame) => void
  /** 任务收尾（后端发 event: done 后关闭连接） */
  onDone?: (frame: ModelingProgressFrame) => void
  /** SSE 不可用，调用方应退回轮询 */
  onFallback?: (reason: string) => void
}

export interface ModelingProgressSubscription {
  close: () => void
}

const BASE = '/api/v1'

export function modelingProgressUrl(jobId: string): string {
  return `${BASE}/modeling-jobs/${encodeURIComponent(jobId)}/events`
}

/** 连续失败多少次后放弃 SSE（EventSource 自己会按浏览器策略重连，这里只兜底）。 */
const MAX_ERRORS = 3

export function subscribeModelingProgress(
  jobId: string,
  handlers: ModelingProgressHandlers = {},
): ModelingProgressSubscription {
  if (typeof window === 'undefined' || typeof window.EventSource !== 'function') {
    handlers.onFallback?.('浏览器不支持 EventSource')
    return { close: () => {} }
  }

  let source: EventSource | null = null
  let errors = 0
  let closed = false

  const parse = (raw: string): ModelingProgressFrame | null => {
    try {
      const payload = JSON.parse(raw)
      const percent = Number(payload?.percent)
      return {
        stage: String(payload?.stage ?? ''),
        percent: Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0,
        message: String(payload?.message ?? ''),
      }
    } catch {
      return null
    }
  }

  const close = () => {
    closed = true
    source?.close()
    source = null
  }

  const open = () => {
    if (closed) return
    source = new EventSource(modelingProgressUrl(jobId))

    source.addEventListener('progress', event => {
      errors = 0
      const frame = parse((event as MessageEvent<string>).data)
      if (frame) handlers.onProgress?.(frame)
    })

    source.addEventListener('done', event => {
      const frame = parse((event as MessageEvent<string>).data)
      // 后端发完 done 会主动断开；这里先关掉，避免浏览器把它当成异常并重连。
      close()
      if (frame) handlers.onDone?.(frame)
      else handlers.onDone?.({ stage: '完成', percent: 100, message: '' })
    })

    source.addEventListener('error', () => {
      if (closed) return
      errors += 1
      if (errors >= MAX_ERRORS) {
        // 反复连不上：可能是后端未启用队列，或中间层直接吞掉长连接 → 退回轮询。
        close()
        handlers.onFallback?.(`SSE 连续 ${errors} 次不可用`)
      }
      // 否则交给浏览器自动重连（自动带 Last-Event-ID，服务端续传）
    })
  }

  open()

  return { close }
}
