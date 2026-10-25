import * as THREE from 'three'
import type { ModelItem } from '@/types'
import { StratumModelLoader } from '../loaders/StratumModelLoader'

interface LodEntry {
    modelId: string
    label: string
    high: THREE.Object3D
    low: THREE.Object3D | null
    lowActive: boolean
    loading: boolean
    failed: boolean
    center: THREE.Vector3
    radius: number
    lodUrl: string
    source: ModelItem
}

/** 距离超过包围球半径的该倍数时切换低模 */
const SWITCH_FAR_FACTOR = 14
/** 低于该倍数切回高模（与 FAR 形成滞回，避免边界抖动） */
const SWITCH_NEAR_FACTOR = 9
const TICK_INTERVAL_MS = 800

/**
 * 由 catalog 模型的 source_file 推导 50% 抽稀 LOD 的静态地址。
 * web_package/L01.glb → /static/models/web_package/lods/L01_lod50.glb；
 * 上传模型 / 无 source_file 的模型不参与 LOD。
 */
export function deriveLodUrl(model: ModelItem): string | null {
    const sourceFile = String(model.metadata?.source_file || '')
    const lower = sourceFile.toLowerCase()
    if (!lower.endsWith('.glb')) return null
    const basePath = sourceFile.slice(0, lower.lastIndexOf('.glb'))
    const slash = basePath.lastIndexOf('/')
    if (slash < 0) return null
    const lodPath = `${basePath.slice(0, slash + 1)}lods/${basePath.slice(slash + 1)}_lod50.glb`
    return `/static/models/${lodPath}`
}

function disposeObject(object: THREE.Object3D) {
    object.traverse((child) => {
        const mesh = child as THREE.Mesh
        mesh.geometry?.dispose?.()
        const material = (mesh as any).material
        if (Array.isArray(material)) material.forEach((mat: any) => mat?.dispose?.())
        else material?.dispose?.()
    })
}

/**
 * 地层模型 LOD 控制器。
 *
 * 高/低模是同一父节点下的兄弟对象，按相机距离切换 visible（低模由
 * StratumModelLoader 用同一份元数据加载，材质/竖向比例与高模一致）。
 * 沉陷对比与地层炸开启用时抑制切换并回退高模，避免位移/错位作用在低模上。
 */
export class StratumLodController {
    private entries = new Map<string, LodEntry>()
    private loader = new StratumModelLoader()
    private timer: ReturnType<typeof setInterval> | null = null
    private camera: THREE.Camera
    enabled = false
    suppressed = false
    lowActiveCount = 0
    availableCount = 0

    constructor(camera: THREE.Camera) {
        this.camera = camera
    }

    register(model: ModelItem, object: THREE.Object3D) {
        const lodUrl = deriveLodUrl(model)
        if (!lodUrl) return
        const box = new THREE.Box3().setFromObject(object)
        if (box.isEmpty()) return
        this.entries.set(model.id, {
            modelId: model.id,
            label: model.name,
            high: object,
            low: null,
            lowActive: false,
            loading: false,
            failed: false,
            center: box.getCenter(new THREE.Vector3()),
            radius: Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1),
            lodUrl,
            source: model,
        })
        this.availableCount = this.entries.size
        if (this.enabled) this.ensureTimer()
    }

    unregister(modelId: string) {
        const entry = this.entries.get(modelId)
        if (!entry) return
        if (entry.low) {
            entry.low.parent?.remove(entry.low)
            disposeObject(entry.low)
        }
        this.entries.delete(modelId)
        this.availableCount = this.entries.size
    }

    setEnabled(enabled: boolean) {
        this.enabled = enabled
        if (!enabled) {
            this.restoreAllHigh()
            this.stopTimer()
            return
        }
        this.ensureTimer()
        void this.tick()
    }

    /** 沉陷/炸开等会移动几何的功能启用期间抑制切换（并回退高模） */
    setSuppressed(suppressed: boolean) {
        this.suppressed = suppressed
        if (suppressed) this.restoreAllHigh()
    }

    restoreAllHigh() {
        for (const entry of this.entries.values()) {
            if (entry.lowActive) this.deactivate(entry)
        }
    }

    dispose() {
        this.stopTimer()
        for (const modelId of [...this.entries.keys()]) {
            this.unregister(modelId)
        }
    }

    private ensureTimer() {
        if (this.timer) return
        this.timer = setInterval(() => void this.tick(), TICK_INTERVAL_MS)
    }

    private stopTimer() {
        if (this.timer) {
            clearInterval(this.timer)
            this.timer = null
        }
    }

    private async loadLow(entry: LodEntry) {
        entry.loading = true
        try {
            const low = await this.loader.load({
                ...entry.source,
                id: `${entry.modelId}__lod50`,
                name: `${entry.label}_lod50`,
                fileUrl: entry.lodUrl,
            })
            low.visible = false
            low.userData.overlayHelper = true
            entry.high.parent?.add(low)
            entry.low = low
        } catch {
            // LOD 文件缺失（如上传模型/旧交付包）时静默放弃该模型
            entry.failed = true
        } finally {
            entry.loading = false
        }
    }

    private activate(entry: LodEntry) {
        if (!entry.low || entry.lowActive) return
        entry.low.visible = true
        entry.high.visible = false
        entry.lowActive = true
        this.lowActiveCount += 1
    }

    private deactivate(entry: LodEntry) {
        if (!entry.low || !entry.lowActive) return
        entry.low.visible = false
        entry.high.visible = true
        entry.lowActive = false
        this.lowActiveCount = Math.max(0, this.lowActiveCount - 1)
    }

    async tick() {
        if (!this.enabled || this.suppressed) return
        for (const entry of this.entries.values()) {
            if (!entry.high.parent) continue
            const distance = this.camera.position.distanceTo(entry.center)
            if (distance > entry.radius * SWITCH_FAR_FACTOR && !entry.lowActive && !entry.loading && !entry.failed) {
                if (!entry.low) await this.loadLow(entry)
                this.activate(entry)
            } else if (distance < entry.radius * SWITCH_NEAR_FACTOR && entry.lowActive) {
                this.deactivate(entry)
            }
        }
    }
}
