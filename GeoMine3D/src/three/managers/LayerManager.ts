import type { ModelManager } from './ModelManager'
import type { HighlightManager } from './HighlightManager'

export class LayerManager {
    private modelManager: ModelManager
    private highlightManager?: HighlightManager

    constructor(modelManager: ModelManager, highlightManager?: HighlightManager) {
        this.modelManager = modelManager
        this.highlightManager = highlightManager
    }

    // 统一切换指定类型图层可见性。
    setLayerVisible(type: string, visible: boolean) {
        const models = this.modelManager.getModelsByType(type)
        for (const model of models) {
            model.object.visible = visible
        }
    }

    // 批量调整指定类型图层透明度。
    setLayerOpacity(type: string, opacity: number) {
        const models = this.modelManager.getModelsByType(type)
        for (const model of models) {
            model.object.traverse((child) => {
                if ((child as any).isMesh) {
                    const mesh = child as any
                    if (mesh.material) {
                        const mats = this.highlightManager?.getEditableMaterials(mesh)
                            ?? (Array.isArray(mesh.material) ? mesh.material : [mesh.material])
                        for (const mat of mats) {
                            mat.transparent = opacity < 1
                            mat.opacity = opacity
                            mat.needsUpdate = true
                        }
                    }
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
