import { Axis, Cartesian3, Matrix4, Model, Transforms, Viewer } from 'cesium'

type ModelOptions = Parameters<typeof Model.fromGltfAsync>[0]

export interface DegreeAnchor {
    lon: number
    lat: number
    alt?: number
}

export class ModelLoader {
    private readonly viewer: Viewer

    /**
     * 创建 glTF 模型加载器。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    /**
     * 根据经纬度锚点创建模型矩阵。
     */
    createModelMatrix(anchor: DegreeAnchor): Matrix4 {
        const origin = Cartesian3.fromDegrees(anchor.lon, anchor.lat, anchor.alt ?? 0)
        return Transforms.eastNorthUpToFixedFrame(origin)
    }

    /**
     * 异步加载 glTF/GLB 模型，并可选择直接加入场景。
     */
    async loadGltf(
        url: string,
        options: Partial<ModelOptions> = {},
        addToScene = true,
    ): Promise<Model> {
        const model = await Model.fromGltfAsync({
            url,
            upAxis: Axis.Y,
            scale: 1,
            minimumPixelSize: 0,
            allowPicking: true,
            incrementallyLoadTextures: true,
            ...options,
        })

        if (addToScene) {
            this.viewer.scene.primitives.add(model)
        }

        return model
    }

    /**
     * 等待模型 ready 状态，包含事件与轮询双重兜底。
     */
    waitForReady(model: Model, timeoutMs = 20000): Promise<void> {
        if (model.ready) {
            return Promise.resolve()
        }

        return new Promise((resolve, reject) => {
            let settled = false
            const removeListener = model.readyEvent.addEventListener(() => {
                if (settled) {
                    return
                }
                settled = true
                clearInterval(pollTimer)
                clearTimeout(timeout)
                removeListener()
                resolve()
            })

            const pollTimer = setInterval(() => {
                if (settled || !model.ready) {
                    return
                }
                settled = true
                clearInterval(pollTimer)
                clearTimeout(timeout)
                removeListener()
                resolve()
            }, 50)

            const timeout = setTimeout(() => {
                if (settled) {
                    return
                }
                settled = true
                clearInterval(pollTimer)
                removeListener()
                reject(new Error('Model load timeout'))
            }, timeoutMs)
        })
    }

    /**
     * 将模型包围球中心平移到指定锚点。
     */
    recenterToAnchor(model: Model, anchor: Cartesian3) {
        const currentCenter = model.boundingSphere?.center
        if (!currentCenter) {
            return
        }

        const delta = Cartesian3.subtract(anchor, currentCenter, new Cartesian3())
        const distance = Cartesian3.magnitude(delta)
        if (!Number.isFinite(distance) || distance < 1) {
            return
        }

        const translation = Matrix4.fromTranslation(delta)
        model.modelMatrix = Matrix4.multiply(translation, model.modelMatrix, new Matrix4())
    }

    /**
     * 从场景中移除模型。
     */
    remove(model: Model, destroy = true) {
        return this.viewer.scene.primitives.remove(model)
    }
}
