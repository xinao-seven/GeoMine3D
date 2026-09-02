import * as THREE from 'three'
import type { ModelManager } from '@/three/managers/ModelManager'

interface StratumExplodeToolOptions {
    gap?: number
}

/**
 * 地层炸开工具：对当前已加载地层按层序沿“场景上方向”做分层位移。
 */
export class StratumExplodeTool {
    private readonly modelManager: ModelManager
    private readonly worldUp = new THREE.Vector3(0, 1, 0)
    private readonly baseLocalPositions = new Map<string, THREE.Vector3>()
    private exploded = false
    private gap: number

    constructor(modelManager: ModelManager, options: StratumExplodeToolOptions = {}) {
        this.modelManager = modelManager
        this.gap = options.gap ?? 18
    }

    // 切换炸开状态，返回切换后的状态。
    toggle() {
        this.setExploded(!this.exploded)
        return this.exploded
    }

    // 设置炸开状态。
    setExploded(exploded: boolean) {
        if (exploded === this.exploded) return

        if (exploded) {
            this.snapshotCurrentStratumBasePositions()
        }

        this.exploded = exploded
        this.sync()

        if (!exploded) {
            this.baseLocalPositions.clear()
        }
    }

    // 设置炸开间距(世界显示单位),炸开状态下即时生效。
    setGap(gap: number) {
        if (!Number.isFinite(gap) || gap === this.gap) return
        this.gap = gap
        if (this.exploded) this.sync()
    }

    // 获取当前是否处于炸开状态。
    isExploded() {
        return this.exploded
    }

    // 在外部场景方向变化时，重新应用当前炸开偏移。
    sync() {
        const models = this.modelManager.getModelsByType('stratum')
        for (const model of models) {
            this.syncForModel(model.id)
        }
    }

    // 释放内部缓存。
    dispose() {
        this.baseLocalPositions.clear()
        this.exploded = false
    }

    // 记录当前已加载地层的基准位置，仅用于本次炸开/还原周期。
    private snapshotCurrentStratumBasePositions() {
        this.baseLocalPositions.clear()

        const models = this.modelManager.getModelsByType('stratum')
        for (const model of models) {
            model.object.traverse((child) => {
                if (!(child as THREE.Mesh).isMesh) return
                const mesh = child as THREE.Mesh
                const key = String(mesh.userData?.id || `${model.id}::${mesh.uuid}`)
                this.baseLocalPositions.set(key, mesh.position.clone())
            })
        }
    }

    // 对单个地层模型应用炸开/还原位移。
    private syncForModel(modelId: string) {
        const model = this.modelManager.getModel(modelId)
        if (!model || model.type !== 'stratum') return

        const layers: Array<{ mesh: THREE.Mesh; key: string; order: number }> = []
        let fallbackOrder = 0

        model.object.traverse((child) => {
            if (!(child as THREE.Mesh).isMesh) return
            const mesh = child as THREE.Mesh
            const key = String(mesh.userData?.id || `${modelId}::${mesh.uuid}`)
            if (!this.baseLocalPositions.has(key)) return

            // 按包围盒中心的世界高度排序(底→顶),不依赖网格在文件中的节点顺序
            mesh.updateWorldMatrix(true, false)
            const box = new THREE.Box3().setFromObject(mesh)
            const order = box.isEmpty() ? fallbackOrder : box.getCenter(new THREE.Vector3()).y
            layers.push({ mesh, key, order })
            fallbackOrder += 1
        })

        if (!layers.length) return

        layers.sort((a, b) => a.order - b.order)
        const centerOffset = (layers.length - 1) / 2

        layers.forEach((layer, index) => {
            const base = this.baseLocalPositions.get(layer.key)
            if (!base) return

            const offsetDisplay = this.exploded ? (index - centerOffset) * this.gap : 0
            if (!layer.mesh.parent) {
                layer.mesh.position.set(base.x, base.y + offsetDisplay, base.z)
                return
            }

            // 炸开始终沿“旋转后场景上方向”（世界 Y）进行位移；
            // gap 以世界显示单位定义，需按父节点沿该方向的世界缩放换算回局部单位
            //（如 catalog 模型组带 scale.z=20 竖向夸张时，避免位移被放大）。
            const parent = layer.mesh.parent
            const parentQuat = new THREE.Quaternion()
            parent.getWorldQuaternion(parentQuat)
            const localUp = this.worldUp.clone().applyQuaternion(parentQuat.invert()).normalize()

            const e = parent.matrixWorld.elements
            const worldStep = new THREE.Vector3(
                e[0] * localUp.x + e[4] * localUp.y + e[8] * localUp.z,
                e[1] * localUp.x + e[5] * localUp.y + e[9] * localUp.z,
                e[2] * localUp.x + e[6] * localUp.y + e[10] * localUp.z,
            )
            const unitsPerDisplay = worldStep.length() || 1
            const offset = offsetDisplay / unitsPerDisplay

            layer.mesh.position.set(
                base.x + localUp.x * offset,
                base.y + localUp.y * offset,
                base.z + localUp.z * offset,
            )
        })
    }
}
