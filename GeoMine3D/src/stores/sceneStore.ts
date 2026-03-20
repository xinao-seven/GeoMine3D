import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import type {
    SceneObject,
    LayerState,
    OpacityState,
    ModelItem,
    BoreholeItem,
    StratumLayerControl,
    ToolState,
    MeasurementRecord,
} from '@/types'

type ModelType = 'stratum' | 'borehole' | 'workingface'

export interface ModelLoadRequest {
    requestId: number
    type: ModelType
    id: string
    name: string
    model?: ModelItem
    borehole?: BoreholeItem
    boreholeList?: BoreholeItem[]
    index?: number
}

export const useSceneStore = defineStore('scene', () => {
    // 当前在三维场景中被选中的对象（用于属性面板展示）
    const selectedObject = ref<SceneObject | null>(null)
    // 当前高亮对象 id（用于跨组件高亮联动）
    const highlightedId = ref<string | null>(null)

    // 三类图层的显示开关状态
    const layerVisible = reactive<LayerState>({
        stratum: true,
        borehole: true,
        workingface: true,
    })

    // 三类图层的透明度状态（0~1）
    const opacity = reactive<OpacityState>({
        stratum: 1.0,
        borehole: 1.0,
        workingface: 1.0,
    })

    // 地层边缘线显示开关
    const showEdges = ref(false)
    // 工具运行状态（剖切/测量/标注）
    const toolState = reactive<ToolState>({
        clipEnabled: false,
        clipHeight: 0,
        clipAxis: 'y',
        clipKeepLower: true,
        clipHelperVisible: true,
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
    // 地层单元控制项（显隐/颜色/透明度）
    const stratumLayers = ref<StratumLayerControl[]>([])

    // 定位目标（用于从其他页面跳转到 dashboard 时定位）
    const locateTarget = ref<{ type: string; id: string; name: string } | null>(null)

    function selectObject(obj: SceneObject | null) {
        selectedObject.value = obj
    }

    function setHighlight(id: string | null) {
        highlightedId.value = id
    }

    function setLayerVisible(type: keyof LayerState, visible: boolean) {
        layerVisible[type] = visible
    }

    function setOpacity(type: keyof OpacityState, value: number) {
        opacity[type] = Math.max(0, Math.min(1, value))
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

    function setClipHelperVisible(visible: boolean) {
        toolState.clipHelperVisible = visible
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

    function requestLoadModel(payload: Omit<ModelLoadRequest, 'requestId'>) {
        const status = getModelLoadStatus(payload.type, payload.id)
        if (status.loaded || status.loading) return
        setModelLoadStatus(payload.type, payload.id, { loading: true })
        loadRequest.value = {
            ...payload,
            requestId: Date.now(),
        }
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

    function locateTo(target: { type: string; id: string; name: string }) {
        locateTarget.value = target
    }

    return {
        selectedObject,
        highlightedId,
        layerVisible,
        opacity,
        showEdges,
        toolState,
        measurements,
        lastMeasurementDistance,
        modelLoadStatus,
        loadRequest,
        stratumLayers,
        locateTarget,
        selectObject,
        setHighlight,
        setLayerVisible,
        setOpacity,
        setShowEdges,
        activateTool,
        setClipHeight,
        setClipAxis,
        setClipKeepLower,
        setClipHelperVisible,
        addMeasurement,
        clearMeasurements,
        getModelKey,
        getModelLoadStatus,
        setModelLoadStatus,
        requestLoadModel,
        registerStratumLayers,
        updateStratumLayer,
        locateTo,
    }
})
