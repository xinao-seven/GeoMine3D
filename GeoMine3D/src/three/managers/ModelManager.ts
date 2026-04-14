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

    // 注册模型并加入场景。
    addModel(model: ManagedModel) {
        this.models.set(model.id, model)
        this.sceneManager.addObject(model.object)
    }

    // 按 id 移除模型并从场景解绑。
    removeModel(id: string) {
        const model = this.models.get(id)
        if (model) {
            this.sceneManager.removeObject(model.object)
            this.models.delete(id)
        }
    }

    // 查询单个模型。
    getModel(id: string): ManagedModel | undefined {
        return this.models.get(id)
    }

    // 获取当前全部已管理模型。
    getAllModels(): ManagedModel[] {
        return Array.from(this.models.values())
    }

    // 按类型筛选模型。
    getModelsByType(type: string): ManagedModel[] {
        return Array.from(this.models.values()).filter(m => m.type === type)
    }

    // 清空全部模型并释放场景引用。
    clear() {
        for (const model of this.models.values()) {
            this.sceneManager.removeObject(model.object)
        }
        this.models.clear()
    }
}
