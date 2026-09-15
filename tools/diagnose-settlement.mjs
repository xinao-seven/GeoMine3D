/**
 * 沉陷绑定失败诊断:打开工作区 → 加载地层 → 启用沉陷 → 抓 console.warn 与场景状态。
 * 运行: node tools/diagnose-settlement.mjs
 */
import { spawn } from 'node:child_process'
import { setTimeout as sleep } from 'node:timers/promises'

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = 9335
const BASE = 'http://localhost:5173'
const PROJECT = '97464713-9996-47eb-86d6-5e2729176588'

const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--enable-unsafe-swiftshader',
  '--no-sandbox', `--remote-debugging-port=${PORT}`, '--window-size=1400,900', 'about:blank'],
  { stdio: 'ignore' })

let ws, id = 0
const pend = new Map()
const logs = []
const send = (m, p = {}) => { const i = ++id; ws.send(JSON.stringify({ id: i, method: m, params: p })); return new Promise((r, j) => pend.set(i, { r, j })) }
const ev = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })
  if (r.exceptionDetails) return 'EXC: ' + r.exceptionDetails.text
  return r.result?.value
}

try {
  await sleep(1500)
  const t = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(x => x.type === 'page')
  ws = new WebSocket(t.webSocketDebuggerUrl)
  await new Promise(r => { ws.onopen = r })
  ws.onmessage = e => {
    const m = JSON.parse(e.data)
    if (m.method === 'Runtime.consoleAPICalled') {
      const txt = (m.params.args || []).map(a => a.value ?? a.description ?? '').join(' ')
      if (/Settlement|沉陷/.test(txt)) logs.push(`[${m.params.type}] ${txt}`)
    }
    if (m.id && pend.has(m.id)) { const { r, j } = pend.get(m.id); pend.delete(m.id); m.error ? j(new Error(JSON.stringify(m.error))) : r(m.result) }
  }
  await send('Page.enable'); await send('Runtime.enable')
  await send('Page.navigate', { url: `${BASE}/workspace/${PROJECT}?toolbox=settlement` })
  await sleep(8000)

  console.log('== 加载地层模型 ==')
  for (let i = 0; i < 8; i++) {
    const n = await ev(`(() => {
      const rows = [...document.querySelectorAll('.resource-row')]
      const b = rows.map(r => r.querySelector('.resource-main'))
        .filter(x => x && !x.disabled && /\\.glb/.test(x.textContent))
      if (!b.length) return 0
      b.slice(0, 4).forEach(x => x.click())
      return b.length
    })()`)
    if (!n) break
    await sleep(2500)
  }
  await sleep(4000)

  console.log('== 已加载模型 ==')
  console.log(JSON.stringify(await ev(`(() => {
    const g = window.__geomine; if (!g) return '__geomine 不存在'
    return g.modelManager.getAllModels().map(m => {
      const meshes = []; m.object.traverse(c => { if (c.isMesh) meshes.push({
        name: c.name, verts: c.geometry.getAttribute('position')?.count ?? 0,
        hasNodeIndex: !!c.geometry.getAttribute('_node_index') }) })
      return { type: m.type, name: m.name,
        catalogCode: m.object.userData?.modelData?.metadata?.catalog_code ?? null,
        verticalScale: m.object.userData?.modelData?.metadata?.vertical_scale ?? null,
        localCoords: m.object.userData?.modelData?.metadata?.local_coordinates ?? null,
        groupScaleZ: m.object.scale.z, meshes }
    })
  })()`), null, 1))

  console.log('== 位移场 ==')
  console.log(JSON.stringify(await ev(`(() => {
    const sm = window.__geomine?.settlementManager
    if (!sm) return 'settlementManager 尚未创建(未启用过)'
    const idx = sm.meta
    return { loaded: sm.loaded, maxSub: idx?.maxSubsidenceM, layers: idx?.layers?.map(l => ({ code: l.code, count: l.count })) }
  })()`), null, 1))

  console.log('== 启用沉陷对比 ==')
  await ev(`window.__geomine.settlement.enabled = true`)
  await sleep(6000)
  console.log('boundLayers =', await ev(`window.__geomine.settlement.boundLayers`))
  console.log('loadError   =', await ev(`window.__geomine.settlement.loadError`))

  console.log('\n== 控制台里的 Settlement 日志 ==')
  console.log(logs.length ? logs.join('\n') : '(无)')
} finally { try { ws?.close() } catch { } chrome.kill() }
