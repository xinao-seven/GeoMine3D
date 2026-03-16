import * as THREE from 'three'
import type { SceneManager } from '../core/SceneManager'

export interface ManagedModel {
  id: string
  name: string
  type: string
  object: THREE.Object3D
}

export class ModelManager {
  private models = new Map<string, ManagedModel>()
  private sceneManager: SceneManager

  constructor(sceneManager: SceneManager) {
    this.sceneManager = sceneManager
  }

  addModel(model: ManagedModel) {
    this.models.set(model.id, model)
    this.sceneManager.addObject(model.object)
  }

  removeModel(id: string) {
    const model = this.models.get(id)
    if (model) {
      this.sceneManager.removeObject(model.object)
      this.models.delete(id)
    }
  }

  getModel(id: string): ManagedModel | undefined {
    return this.models.get(id)
  }

  getAllModels(): ManagedModel[] {
    return Array.from(this.models.values())
  }

  getModelsByType(type: string): ManagedModel[] {
    return Array.from(this.models.values()).filter(m => m.type === type)
  }

  clear() {
    for (const model of this.models.values()) {
      this.sceneManager.removeObject(model.object)
    }
    this.models.clear()
  }
}
