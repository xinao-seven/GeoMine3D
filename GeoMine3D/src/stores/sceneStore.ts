import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import type {
    SceneObject,
    LayerState,
    ModelItem,
    BoreholeItem,
    StratumLayerControl,
    ToolState,
    MeasurementRecord,
} from '@/types'

type ModelType = 'stratum' | 'borehole' | 'workingface'

export type ModelLoadPayload = {
    type: 'stratum' | 'workingface'
    id: string
    name: string
    model: ModelItem
} | {
    type: 'borehole'
    id: '__all__'
    name: string
    boreholeList: BoreholeItem[]
}

export type ModelLoadRequest = ModelLoadPayload & { requestId: number }

export type ModelUnloadRequest = { type: 'stratum' | 'borehole' | 'workingface'; id: string; requestId: number }

export const useSceneStore = defineStore('scene', () => {
    // 当前在三维场景中被选中的对象（用于属性面板展示）
    const selectedObject = ref<SceneObject | null>(null)
    // 三类图层的显示开关状态
    const layerVisible = reactive<LayerState>({
        stratum: true,
        borehole: true,
        workingface: true,
    })

    // 地层边缘线显示开关
    const showEdges = ref(false)
    // 工具运行状态（剖切/测量/标注）
    const toolState = reactive<ToolState>({
        clipEnabled: false,
        clipHeight: 0,
        clipAxis: 'y',
        clipKeepLower: true,
        measureEnabled: false,
        annotationEnabled: false,
    })
    // 测量结果列表（历史记录）
    const measurements = ref<MeasurementRecord[]>([])
    // 最近一次测量距离（用于快捷展示）
    const lastMeasurementDistance = ref<number | null>(null)

    // 模型加载状态表，key 为 type:id
    const modelLoadStatus = reactive<Record<string, { loaded: boolean; loading: boolean }>>({})
    // 待处理模型加载请求（由 SceneCanvas 监听并消费）
    const loadRequest = ref<ModelLoadRequest | null>(null)
    // 待处理模型移除请求（由 SceneCanvas 监听并消费）
    const unloadRequest = ref<ModelUnloadRequest | null>(null)
    // 地层单元控制项（显隐/颜色/透明度）
    const stratumLayers = ref<StratumLayerControl[]>([])
    // 数据库项目的投影坐标原点；用于让真实坐标模型与钻孔使用同一局部坐标系。
    const coordinateOrigin = ref<{ x: number; y: number; z: number; verticalScale: number } | null>(null)

    function selectObject(obj: SceneObject | null) {
        selectedObject.value = obj
    }

    function setLayerVisible(type: keyof LayerState, visible: boolean) {
        layerVisible[type] = visible
    }

    function setShowEdges(visible: boolean) {
        showEdges.value = visible
    }

    function activateTool(tool: 'clip' | 'measure' | 'annotation' | null) {
        toolState.clipEnabled = tool === 'clip'
        toolState.measureEnabled = tool === 'measure'
        toolState.annotationEnabled = tool === 'annotation'
    }

    function setClipHeight(height: number) {
        toolState.clipHeight = height
    }

    function setClipAxis(axis: 'x' | 'y' | 'z') {
        toolState.clipAxis = axis
    }

    function setClipKeepLower(keepLower: boolean) {
        toolState.clipKeepLower = keepLower
    }

    function addMeasurement(record: MeasurementRecord) {
        measurements.value.push(record)
        lastMeasurementDistance.value = record.distance
    }

    function clearMeasurements() {
        measurements.value = []
        lastMeasurementDistance.value = null
    }

    function getModelKey(type: ModelType, id: string) {
        return `${type}:${id}`
    }

    function getModelLoadStatus(type: ModelType, id: string) {
        const key = getModelKey(type, id)
        return modelLoadStatus[key] || { loaded: false, loading: false }
    }

    function setModelLoadStatus(type: ModelType, id: string, status: Partial<{ loaded: boolean; loading: boolean }>) {
        const key = getModelKey(type, id)
        const current = modelLoadStatus[key] || { loaded: false, loading: false }
        modelLoadStatus[key] = { ...current, ...status }
    }

    function requestLoadModel(payload: ModelLoadPayload) {
        const status = getModelLoadStatus(payload.type, payload.id)
        if (status.loaded || status.loading) return
        setModelLoadStatus(payload.type, payload.id, { loading: true })
        loadRequest.value = {
            ...payload,
            requestId: Date.now(),
        }
    }

    function requestUnloadModel(payload: { type: 'stratum' | 'borehole' | 'workingface'; id: string }) {
        unloadRequest.value = { ...payload, requestId: Date.now() }
    }

    // 清除加载状态；不传参时清空全部（离开工作区时使用）
    function clearLoadStatus(type?: 'stratum' | 'borehole' | 'workingface', id?: string) {
        if (!type) {
            for (const key of Object.keys(modelLoadStatus)) delete modelLoadStatus[key]
            return
        }
        if (id) delete modelLoadStatus[getModelKey(type, id)]
    }

    // 移除模型时同步清掉该模型登记的地层单元控制项
    function removeStratumLayersByModel(modelId: string) {
        stratumLayers.value = stratumLayers.value.filter(item => item.modelId !== modelId)
    }

    // 离开工作区时重置场景会话：模型对象已随画布销毁，相关状态一并清空，
    // 避免重进后列表残留"已加载"导致无法再次加载。
    function resetSceneSession() {
        clearLoadStatus()
        stratumLayers.value = []
        selectObject(null)
        measurements.value = []
        lastMeasurementDistance.value = null
        loadRequest.value = null
        unloadRequest.value = null
    }

    function registerStratumLayers(layers: StratumLayerControl[]) {
        for (const layer of layers) {
            const index = stratumLayers.value.findIndex((item) => item.key === layer.key)
            if (index >= 0) {
                Object.assign(stratumLayers.value[index], layer)
            } else {
                stratumLayers.value.push(layer)
            }
        }
    }

    function updateStratumLayer(key: string, patch: Partial<StratumLayerControl>) {
        const index = stratumLayers.value.findIndex((item) => item.key === key)
        if (index < 0) return
        Object.assign(stratumLayers.value[index], patch)
    }

    function setCoordinateOrigin(origin: { x: number; y: number; z: number; verticalScale: number } | null) {
        coordinateOrigin.value = origin
    }

    return {
        selectedObject,
        layerVisible,
        showEdges,
        toolState,
        measurements,
        lastMeasurementDistance,
        modelLoadStatus,
        loadRequest,
        unloadRequest,
        stratumLayers,
        coordinateOrigin,
        selectObject,
        setLayerVisible,
        setShowEdges,
        activateTool,
        setClipHeight,
        requestUnloadModel,
        clearLoadStatus,
        removeStratumLayersByModel,
        resetSceneSession,
        setClipAxis,
        setClipKeepLower,
        addMeasurement,
        clearMeasurements,
        getModelKey,
        getModelLoadStatus,
        setModelLoadStatus,
        requestLoadModel,
        registerStratumLayers,
        updateStratumLayer,
        setCoordinateOrigin,
    }
})
