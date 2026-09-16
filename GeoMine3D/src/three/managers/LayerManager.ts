import * as THREE from 'three'
import type { ModelManager } from './ModelManager'

export class LayerManager {
    private modelManager: ModelManager
    // 材质自身的不透明度基准值:整体透明度是乘在这个基准上的系数,
    // 反复拖动滑块也不会因为累乘而失真。
    private baseOpacity = new WeakMap<THREE.Material, number>()

    constructor(modelManager: ModelManager) {
        this.modelManager = modelManager
    }

    // 统一切换指定类型图层可见性。
    setLayerVisible(type: string, visible: boolean) {
        const models = this.modelManager.getModelsByType(type)
        for (const model of models) {
            model.object.visible = visible
        }
    }

    // 按类型整体调整不透明度;factor 为 0.05~1 的系数,1 表示还原材质原始透明度。
    setLayerOpacity(type: string, factor: number) {
        const opacity = Math.min(1, Math.max(0.05, Number.isFinite(factor) ? factor : 1))
        for (const model of this.modelManager.getModelsByType(type)) {
            model.object.traverse((child) => {
                if (!(child as THREE.Mesh).isMesh) return
                const mesh = child as THREE.Mesh
                const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
                for (const material of materials) {
                    if (!material) continue
                    if (!this.baseOpacity.has(material)) {
                        const current = (material as any).opacity
                        this.baseOpacity.set(material, typeof current === 'number' ? current : 1)
                    }
                    const base = this.baseOpacity.get(material) ?? 1
                    const next = base * opacity
                    ;(material as any).opacity = next
                    material.transparent = next < 1
                    material.needsUpdate = true
                }
            })
        }
    }

    // 控制地层边线辅助对象显隐。
    setLayerEdgesVisible(type: string, visible: boolean) {
        const models = this.modelManager.getModelsByType(type)
        for (const model of models) {
            model.object.traverse((child) => {
                const edgeLines = (child as any).userData?.edgeLines
                if (edgeLines) {
                    edgeLines.visible = visible && (child as any).visible !== false
                }
            })
        }
    }
}
