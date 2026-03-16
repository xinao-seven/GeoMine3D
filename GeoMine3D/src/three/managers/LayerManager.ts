import type { ModelManager } from './ModelManager'

export class LayerManager {
  private modelManager: ModelManager

  constructor(modelManager: ModelManager) {
    this.modelManager = modelManager
  }

  setLayerVisible(type: string, visible: boolean) {
    const models = this.modelManager.getModelsByType(type)
    for (const model of models) {
      model.object.visible = visible
    }
  }

  setLayerOpacity(type: string, opacity: number) {
    const models = this.modelManager.getModelsByType(type)
    for (const model of models) {
      model.object.traverse((child) => {
        if ((child as any).isMesh) {
          const mesh = child as any
          if (mesh.material) {
            const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
            for (const mat of mats) {
              mat.transparent = opacity < 1
              mat.opacity = opacity
            }
          }
        }
      })
    }
  }

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
