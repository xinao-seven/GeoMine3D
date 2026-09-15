import * as THREE from 'three'

/**
 * 沉陷位移场加载与"沉陷前后"几何变形。
 *
 * 数据来源:`/static/models/settlement/`
 *   - vertex_offsets.index.json  每层位移段的元信息
 *   - vertex_offsets.bin         各层位移数组(连续 float32 三元组)
 *
 * 设计要点(为什么不用双模型叠加、也不放 shader 里)
 * -------------------------------------------------
 * 1. 本工程 67~70% 的顶点在沉陷前后严格共面,双模型同屏叠加必然大面积 z-fighting,
 *    且 14 层 DoubleSide 半透明还有排序伪影。改为**单模型 + 位移**从根上避免。
 * 2. 位移直接作用在 `geometry.attributes.position` 上,原因是本工程的
 *    `HighlightManager._applyColor` / `applyStratumLayerControl` 会**整块替换材质**;
 *    若把位移做在 shader(onBeforeCompile)里,材质一被替换位移就丢失。
 *    改几何则与所有既有工具(剖切/炸开/拾取/高亮/透明度)天然兼容。
 * 3. 基线顶点备份一次,之后每帧只是 `pos = base + k·offset` 的线性组合。
 *
 * 位移语义:`position_settled = position_base + exaggeration · t · offset`
 *   t = 0 沉陷前,t = 1 沉陷后;exaggeration 是**纯显示端**夸大倍数
 *   (真实沉降仅数米,×20 后仍不显眼,故需要额外夸大,图例上必须标注)。
 */

export type SettlementColorMode = 'original' | 'dz' | 'magnitude'

export interface SettlementLayerMeta {
    code: string
    count: number
    byteOffset: number
    byteLength: number
    baseGlbSha256: string
}

export interface SettlementIndex {
    schemaVersion: string
    generatedUtc: string
    layout: string
    dtype: string
    components: number
    unit: string
    dzSign: string
    originRestore: { x: number; y: number; z: number }
    displayZScale: number
    maxSubsidenceM: number
    maxHorizontalM: number
    workingsFollowSettlement: boolean
    layers: SettlementLayerMeta[]
    statistics?: Record<string, any>
}

/** 单个 mesh 的变形状态 */
interface MeshState {
    mesh: THREE.Mesh
    base: Float32Array          // 基线顶点(拷贝,不可变)
    offset: Float32Array        // 该顶点对应的位移
    dz: Float32Array            // 竖向位移(着色用,避免每次重算)
    baseColors: Float32Array | null
}

/**
 * 单个 mesh 未能绑定位移场的原因。
 *
 * 存在的理由:以前这里只有一句 console.warn,用户侧只能看到“未绑定到地层”,
 * 却不知道究竟是没数据、层号没认出来、还是顶点数不匹配。现在把它结构化,
 * 由工具箱原样展示出来。
 */
export interface SettlementBindIssue {
    mesh: string
    layerCode: string
    reason: string
    /** 位移场里的顶点个数(展示用) */
    expected?: number
    /** GLB 里的顶点个数(展示用) */
    actual?: number
}

const DEFAULT_BASE_URL = '/static/models/settlement'

export class SettlementManager {
    private baseUrl: string
    private index: SettlementIndex | null = null
    private offsetBlob: ArrayBuffer | null = null
    private offsetByLayer = new Map<string, Float32Array>()
    private states: MeshState[] = []
    private _t = 0
    private _exaggeration = 1
    private _colorMode: SettlementColorMode = 'original'
    /** 已应用的最大竖向位移(显示单位),供图例与相机取景使用 */
    private _appliedMaxDz = 0
    /** 着色归一化的参考量(真实尺度,夸大倍数在分子分母上抵消) */
    private _maxDzReal = 1
    private _maxMagReal = 1
    private issues: SettlementBindIssue[] = []

    constructor(baseUrl: string = DEFAULT_BASE_URL) {
        this.baseUrl = baseUrl
    }

    /** 只拉了索引(几 KB),尚未拉位移数据 */
    get indexLoaded() { return this.index !== null }
    /**
     * 位移数据是否就绪。
     *
     * 注意:这里**不能**用 `index !== null` 判断。页面挂载时会预取索引
     * (为了在启用前就显示最大沉降等读数),若把“有索引”当成“已就绪”,
     * 启用时就会跳过 4.4 MB 数据的加载,最终表现为“已加载地层却提示未绑定”。
     */
    get loaded() { return this.offsetBlob !== null }
    get meta(): SettlementIndex | null { return this.index }
    /** 上一次 attach 的逐条结果,供 UI 展示“为什么没绑上” */
    get lastIssues(): SettlementBindIssue[] { return this.issues }
    get time() { return this._t }
    get exaggeration() { return this._exaggeration }
    get colorMode() { return this._colorMode }
    get attachedCount() { return this.states.length }
    get appliedMaxDz() { return this._appliedMaxDz }
    get maxDzReal() { return this._maxDzReal }
    get maxMagReal() { return this._maxMagReal }

    /** 拉取索引(仅几 KB)。用于在尚未启用时就能显示最大沉降等元信息 */
    async loadIndex(): Promise<SettlementIndex> {
        if (this.index) return this.index
        const idxResp = await fetch(`${this.baseUrl}/vertex_offsets.index.json`,
            { cache: 'no-store' })
        if (!idxResp.ok) {
            throw new Error(
                `位移场索引 HTTP ${idxResp.status}：${this.baseUrl}/vertex_offsets.index.json`)
        }
        // 常见坑：后端未挂载 /static 时会被 SPA 兜底路由接管，返回 index.html。
        // 这类响应 res.ok 为 true，必须靠 content-type 识别，否则会报难以理解的 JSON 解析错误。
        const idxType = idxResp.headers.get('content-type') || ''
        if (!idxType.includes('json')) {
            const len = idxResp.headers.get('content-length') || '(无)'
            const age = idxResp.headers.get('age') || '(无)'
            throw new Error(
                `位移场路径未指向静态文件（返回 ${idxType || '未知类型'}，content-length ${len}，age ${age}）。` +
                '若地址栏直接打开该 URL 是正常 JSON，说明浏览器缓存了旧的失败响应，' +
                '请 Ctrl+Shift+R 强刷。否则请确认后端已挂载 /static/models（backend/app/main.py）并重启。')
        }
        this.index = (await idxResp.json()) as SettlementIndex
        return this.index
    }

    /** 拉取位移场数据(一次即可,约 4 MB) */
    async load(): Promise<SettlementIndex> {
        const index = this.index ?? await this.loadIndex()
        if (this.offsetBlob) return index

        const binResp = await fetch(`${this.baseUrl}/vertex_offsets.bin`, { cache: 'no-store' })
        if (!binResp.ok) {
            throw new Error(
                `位移场数据 HTTP ${binResp.status}：${this.baseUrl}/vertex_offsets.bin`)
        }
        this.offsetBlob = await binResp.arrayBuffer()
        if (this.offsetBlob.byteLength < 12) {
            throw new Error('位移场二进制文件异常（长度不足），请检查文件是否完整。')
        }
        for (const layer of index.layers) {
            this.offsetByLayer.set(
                layer.code.toUpperCase(),
                new Float32Array(this.offsetBlob, layer.byteOffset, layer.count * 3),
            )
        }
        return index
    }

    /** 把位移场绑定到已加载的地层模型上 */
    attach(modelManager: { getAllModels(): Array<{ id: string; type: string; object: THREE.Object3D }> }): number {
        const index = this.index
        if (!index) return 0
        // 增量绑定:已绑定的 mesh 必须复用原状态。
        // 否则新增一层模型时会重新挂载全量,把“已变形后的位置”当成新基线,越拉越远。
        const existing = new Map<THREE.Mesh, MeshState>(this.states.map(s => [s.mesh, s]))
        const next: MeshState[] = []
        this.issues = []
        this._maxDzReal = 1
        this._maxMagReal = 1
        if (!this.offsetBlob) {
            // 只拉了索引、位移数据未到时会走到这里。必须显式报出,
            // 否则现场表现就是“地层已加载但提示未绑定”。
            this.issues.push({
                mesh: '-', layerCode: '-',
                reason: '位移场数据尚未加载(仅拉取了索引),请关闭后重新启用沉陷对比。',
            })
            return 0
        }
        const models = modelManager.getAllModels().filter(m => m.type === 'stratum')
        for (const model of models) {
            const code = String((model.object.userData?.modelData as any)?.metadata?.catalog_code ?? '')
                .toUpperCase()
            const meshes: THREE.Mesh[] = []
            model.object.traverse(child => {
                if ((child as THREE.Mesh).isMesh) meshes.push(child as THREE.Mesh)
            })
            meshes.forEach((mesh, i) => {
                const known = existing.get(mesh)
                if (known) {
                    next.push(known)
                    let layerMaxDz = 0
                    let layerMaxMag = 0
                    for (let v = 0; v < known.dz.length; v += 1) {
                        const ad = Math.abs(known.dz[v])
                        if (ad > layerMaxDz) layerMaxDz = ad
                        const ii = v * 3
                        const m = Math.hypot(known.offset[ii], known.offset[ii + 1], known.offset[ii + 2])
                        if (m > layerMaxMag) layerMaxMag = m
                    }
                    this._maxDzReal = Math.max(this._maxDzReal, layerMaxDz)
                    this._maxMagReal = Math.max(this._maxMagReal, layerMaxMag)
                    return
                }
                // 单层模型:整包共用该层位移;合并模型:按 GLB mesh 名(L01..L14)匹配
                const meshCode = (mesh.name || '').trim().toUpperCase()
                let layerCode = ''
                if (/^L\d{2}$/.test(code) && meshes.length === 1) layerCode = code
                else if (/^L\d{2}$/.test(meshCode)) layerCode = meshCode
                else if (/^L\d{2}$/.test(code)) layerCode = code
                const posAttr = mesh.geometry.getAttribute('position') as THREE.BufferAttribute
                if (!posAttr) return
                let offset = layerCode ? this.offsetByLayer.get(layerCode) : undefined
                if (!offset || offset.length !== posAttr.count * 3) {
                    // 回退:按顶点数唯一匹配。
                    // 用于 metadata.catalog_code 缺失(旧库导入)或层号写错的情况;
                    // 每层表面顶点数基本唯一,匹配到唯一候选才采纳。
                    const cands = index.layers.filter(l => l.count === posAttr.count)
                    if (cands.length === 1) {
                        const chosen = cands[0].code
                        const alt = this.offsetByLayer.get(chosen)
                        if (alt) {
                            if (layerCode && layerCode !== chosen) {
                                console.warn(
                                    `[Settlement] ${layerCode} 位移与顶点数不符,` +
                                    `按顶点数改判为 ${chosen}`)
                            }
                            layerCode = chosen
                            offset = alt
                        }
                    }
                }
                if (!offset) {
                    const expected = this.offsetByLayer.get(layerCode)?.length
                    this.issues.push({
                        mesh: mesh.name || `#${i}`,
                        layerCode: layerCode || '(未识别)',
                        reason: layerCode
                            ? '位移场里没有该层的位移数据'
                            : '未能从 catalog_code / mesh 名 / 顶点数识别出层号',
                        expected: expected ? expected / 3 : undefined,
                        actual: posAttr.count,
                    })
                    return
                }
                if (offset.length !== posAttr.count * 3) {
                    this.issues.push({
                        mesh: mesh.name || `#${i}`,
                        layerCode,
                        reason: '位移个数与顶点数不一致(位移场与这份 GLB 可能不是一对)',
                        expected: offset.length / 3,
                        actual: posAttr.count,
                    })
                    return
                }
                const base = new Float32Array(posAttr.array as ArrayLike<number>)
                const dz = new Float32Array(posAttr.count)
                let layerMaxDz = 0
                let layerMaxMag = 0
                for (let v = 0; v < posAttr.count; v += 1) {
                    const i3 = v * 3
                    dz[v] = offset[i3 + 2]
                    const ad = Math.abs(offset[i3 + 2])
                    if (ad > layerMaxDz) layerMaxDz = ad
                    const m = Math.hypot(offset[i3], offset[i3 + 1], offset[i3 + 2])
                    if (m > layerMaxMag) layerMaxMag = m
                }
                this._maxDzReal = Math.max(this._maxDzReal, layerMaxDz)
                this._maxMagReal = Math.max(this._maxMagReal, layerMaxMag)
                const colorAttr = mesh.geometry.getAttribute('color')
                next.push({
                    mesh,
                    base,
                    offset,
                    dz,
                    baseColors: colorAttr
                        ? new Float32Array(colorAttr.array as ArrayLike<number>)
                        : null,
                })
            })
        }
        this.states = next
        this.apply()
        return this.states.length
    }

    /** 把位置恢复到基线(卸载前必须调,否则再加载会以变形位置为基线) */
    restoreBase() {
        for (const st of this.states) {
            const posAttr = st.mesh.geometry.getAttribute('position') as THREE.BufferAttribute
            ;(posAttr.array as Float32Array).set(st.base)
            posAttr.needsUpdate = true
            st.mesh.geometry.computeBoundingSphere()
            st.mesh.geometry.computeBoundingBox()
        }
    }

    detach() {
        this.restoreBase()
        this.states = []
        this.issues = []
        this._t = 0
        this._appliedMaxDz = 0
        this._maxDzReal = 1
        this._maxMagReal = 1
    }

    setTime(t: number) {
        this._t = Math.min(1, Math.max(0, t))
        this.apply()
    }

    setExaggeration(x: number) {
        this._exaggeration = Math.max(1, x)
        this.apply()
    }

    setColorMode(mode: SettlementColorMode) {
        this._colorMode = mode
        this.apply()
    }

    /** 重置到沉陷前 */
    reset() {
        this._t = 0
        this.apply()
    }

    // ------------------------------------------------------------------
    private apply() {
        const k = this._exaggeration * this._t
        let maxDz = 0
        for (const st of this.states) {
            const posAttr = st.mesh.geometry.getAttribute('position') as THREE.BufferAttribute
            const arr = posAttr.array as Float32Array
            const n = posAttr.count
            for (let v = 0; v < n; v += 1) {
                const i3 = v * 3
                const ox = st.offset[i3]
                const oy = st.offset[i3 + 1]
                const oz = st.offset[i3 + 2]
                arr[i3] = st.base[i3] + k * ox
                arr[i3 + 1] = st.base[i3 + 1] + k * oy
                arr[i3 + 2] = st.base[i3 + 2] + k * oz
                const a = Math.abs(k * oz)
                if (a > maxDz) maxDz = a
            }
            posAttr.needsUpdate = true
            // 位移会改变包围体,必须重算,否则视锥剔除/相机取景会出错
            st.mesh.geometry.computeBoundingSphere()
            st.mesh.geometry.computeBoundingBox()
            this.applyVertexColors(st)
        }
        this._appliedMaxDz = maxDz
    }

    private applyVertexColors(st: MeshState) {
        const geo = st.mesh.geometry
        const posCount = (geo.getAttribute('position') as THREE.BufferAttribute).count
        let colorAttr = geo.getAttribute('color') as THREE.BufferAttribute | null
        if (this._colorMode === 'original') {
            if (st.baseColors && colorAttr) {
                (colorAttr.array as Float32Array).set(st.baseColors)
                colorAttr.needsUpdate = true
            }
            return
        }
        if (!colorAttr || colorAttr.count !== posCount) {
            colorAttr = new THREE.BufferAttribute(new Float32Array(posCount * 4), 4)
            geo.setAttribute('color', colorAttr)
        }
        const arr = colorAttr.array as Float32Array
        const ref = this._colorMode === 'dz' ? this._maxDzReal : this._maxMagReal
        const tmp = new THREE.Color()
        for (let v = 0; v < posCount; v += 1) {
            let u: number
            if (this._colorMode === 'dz') {
                u = Math.abs(st.dz[v]) / ref
            } else {
                const i3 = v * 3
                u = Math.hypot(st.offset[i3], st.offset[i3 + 1], st.offset[i3 + 2]) / ref
            }
            u = Math.min(1, Math.max(0, u))
            // 深青(无位移)→ 黄红(最大沉降)
            tmp.setHSL(0.62 * (1 - u), 0.72, 0.30 + 0.32 * u)
            arr[v * 4] = tmp.r
            arr[v * 4 + 1] = tmp.g
            arr[v * 4 + 2] = tmp.b
            arr[v * 4 + 3] = 1
        }
        colorAttr.needsUpdate = true
    }
}
