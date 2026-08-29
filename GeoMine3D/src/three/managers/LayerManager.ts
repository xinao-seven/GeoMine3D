import type { ModelManager } from './ModelManager'

export class LayerManager {
    private modelManager: ModelManager

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
