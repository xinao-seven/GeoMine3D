/**
 * 用 Chrome DevTools Protocol 真实驱动页面,验证「竖向比例」滑块确实改变了场景几何高度。
 *
 * 做法(不靠像素猜测,直接从场景图量测):
 *   1. 打开工作区(真实项目) → 加载若干地层模型
 *   2. 依次点 1× / 默认 / 50× 预设
 *   3. 读 geoRoot.scale.z 与所有模型的**世界包围盒高度**,断言单调放大
 *
 * 依赖 SceneCanvas 在 DEV 下挂的 __geomine 调试句柄。
 *
 * 运行: node tools/verify-zscale.mjs
 */
import { spawn } from 'node:child_process'
import { writeFileSync, mkdirSync } from 'node:fs'
import { setTimeout as sleep } from 'node:timers/promises'

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = 9333
const BASE = process.env.BASE_URL || 'http://localhost:5173'
const PROJECT = process.env.PROJECT_ID || '97464713-9996-47eb-86d6-5e2729176588'
const OUT = 'C:/code/GeoMine3D/.verify'

mkdirSync(OUT, { recursive: true })

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--enable-unsafe-swiftshader', '--no-sandbox',
  `--remote-debugging-port=${PORT}`, '--window-size=1400,900', 'about:blank',
], { stdio: 'ignore' })

let ws, msgId = 0
const pending = new Map()

function send(method, params = {}) {
  const id = ++msgId
  ws.send(JSON.stringify({ id, method, params }))
  return new Promise((res, rej) => pending.set(id, { res, rej }))
}

async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' :: ' + expression.slice(0, 100))
  return r.result?.value
}

async function screenshot(name) {
  const r = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, 'base64'))
}

/** 直接从场景图量测:geoRoot 缩放 + 所有模型的世界包围盒高度 */
async function probe() {
  return evaluate(`(() => {
    const g = window.__geomine
    if (!g) return { error: '__geomine 未注入(可能不是 DEV 构建)' }
    const geoRoot = g.sceneManager.geoRoot
    const models = g.modelManager.getAllModels()
    const box = new (Object.getPrototypeOf(geoRoot).constructor.prototype.constructor === Function ? Object : Object)()
    // 用 three 的 Box3:从任一对象取构造器太重,直接在页面里 new 一个
    let minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity
    const v = { x:0, y:0, z:0 }
    for (const m of models) {
      m.object.updateWorldMatrix(true, true)
      const b = new (g.sceneManager.scene.constructor === Object ? Object : Object)()
      // 遍历顶点求世界坐标包围盒(不依赖 Box3 是否在 window 上)
      m.object.traverse(o => {
        const pos = o.geometry && o.geometry.getAttribute && o.geometry.getAttribute('position')
        if (!pos) return
        const e = o.matrixWorld.elements
        for (let i = 0; i < pos.count; i += 7) {
          const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i)
          const wx = e[0]*x + e[4]*y + e[8]*z  + e[12]
          const wy = e[1]*x + e[5]*y + e[9]*z  + e[13]
          const wz = e[2]*x + e[6]*y + e[10]*z + e[14]
          if (wy < minY) minY = wy; if (wy > maxY) maxY = wy
          if (wz < minZ) minZ = wz; if (wz > maxZ) maxZ = wz
        }
      })
    }
    return {
      multiplier: geoRoot.scale.z,
      modelCount: models.length,
      worldHeightY: Number.isFinite(minY) ? +(maxY - minY).toFixed(2) : null,
      worldSpanZ: Number.isFinite(minZ) ? +(maxZ - minZ).toFixed(2) : null,
    }
  })()`)
}

async function clickPreset(text) {
  return evaluate(`(() => {
    const els = [...document.querySelectorAll('.tb-seg-buttons button')]
    const el = els.find(e => e.textContent.trim() === ${JSON.stringify(text)})
    if (!el) return { ok:false, seen: els.map(e=>e.textContent.trim()) }
    el.click()
    return { ok:true }
  })()`)
}

try {
  await sleep(1500)
  const targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
  const page = targets.find(t => t.type === 'page')
  ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise(r => { ws.onopen = r })
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data)
    if (m.id && pending.has(m.id)) {
      const { res, rej } = pending.get(m.id)
      pending.delete(m.id)
      m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result)
    }
  }
  await send('Page.enable'); await send('Runtime.enable')

  console.log('1) 打开工作区 ...')
  await send('Page.navigate', { url: `${BASE}/workspace/${PROJECT}?toolbox=scale` })
  await sleep(7000)

  console.log('2) 加载地层模型 ...')
  for (let i = 0; i < 10; i++) {
    const n = await evaluate(`(() => {
      const btns = [...document.querySelectorAll('.resource-main')]
        .filter(b => !b.disabled && !/钻孔/.test(b.textContent))
      if (!btns.length) return 0
      btns.slice(0, 3).forEach(b => b.click())
      return btns.length
    })()`)
    if (!n) break
    console.log(`   第 ${i+1} 轮:可点资源 ${n} 条`)
    await sleep(2500)
  }
  await sleep(5000)

  // 注意:?toolbox=scale 已经打开了该组,再点一次导轨按钮会把它关掉。
  const opened = await evaluate(`document.querySelector('.tb-page-head span')?.textContent ?? ''`)
  if (opened !== '竖向比例') {
    await evaluate(`(() => {
      const b = [...document.querySelectorAll('.tb-rail-btn')]
        .find(e => (e.getAttribute('title')||'') === '竖向比例')
      if (b) b.click()
    })()`)
    await sleep(800)
  }
  console.log('   当前功能页:',
    await evaluate(`document.querySelector('.tb-page-head span')?.textContent ?? '(未展开)'`),
    '| 预设按钮:',
    await evaluate(`[...document.querySelectorAll('.tb-seg-buttons button')].map(b=>b.textContent.trim())`))

  const rows = []
  for (const preset of ['1×', '默认', '50×', '100×']) {
    const c = await clickPreset(preset)
    if (!c.ok) { console.log(`   ⚠️ 找不到预设按钮,现有:${JSON.stringify(c.seen)}`); break }
    await sleep(1500)
    const p = await probe()
    const shown = await evaluate(`(() => {
      const el = [...document.querySelectorAll('.tb-row')].find(e => e.textContent.includes('竖向夸张倍数'))
      return el ? el.textContent.replace(/\\s+/g,' ').trim() : '?'
    })()`)
    rows.push({ preset, ...p, shown })
    await screenshot(`zscale-${preset.replace('×', 'x').replace('默认', 'default')}`)
    console.log(`   ${preset.padEnd(4)} scale.z=${String(p.multiplier).padEnd(6)} ` +
                `模型数=${String(p.modelCount).padEnd(3)} 世界高度=${p.worldHeightY} ` +
                `| 面板「${shown}」`)
  }

  console.log('\n===== 结论 =====')
  const hs = rows.map(r => r.worldHeightY).filter(v => v != null)
  const ms = rows.map(r => r.multiplier)
  if (rows.some(r => r.error)) console.log('❌', rows.find(r => r.error).error)
  else if (!hs.length || rows[0].modelCount === 0) console.log('⚠️ 未加载到模型,无法判定')
  else {
    const mono = ms.every((v, i) => i === 0 || v >= ms[i - 1]) && hs.every((v, i) => i === 0 || v >= hs[i - 1])
    const grew = hs[hs.length - 1] > hs[0] * 1.2
    console.log('scale.z 序列:', ms.join(' → '))
    console.log('世界高度序列:', hs.join(' → '))
    console.log(mono && grew
      ? '✅ 竖向比例确实改变了场景几何高度(与世界高度单调对应)'
      : '❌ 未观察到预期变化')
  }
} finally {
  try { ws?.close() } catch {}
  chrome.kill()
}
