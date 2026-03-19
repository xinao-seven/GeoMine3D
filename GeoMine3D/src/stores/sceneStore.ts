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
    const selectedObject = ref<SceneObject | null>(null)
    const highlightedId = ref<string | null>(null)

    const layerVisible = reactive<LayerState>({
        stratum: true,
        borehole: true,
        workingface: true,
    })

    const opacity = reactive<OpacityState>({
        stratum: 1.0,
        borehole: 1.0,
        workingface: 1.0,
    })

    const showEdges = ref(false)
    const toolState = reactive<ToolState>({
        clipEnabled: false,
        clipHeight: 0,
        clipAxis: 'y',
        clipKeepLower: true,
        clipHelperVisible: true,
        measureEnabled: false,
        annotationEnabled: false,
    })
    const measurements = ref<MeasurementRecord[]>([])
    const lastMeasurementDistance = ref<number | null>(null)

    const modelLoadStatus = reactive<Record<string, { loaded: boolean; loading: boolean }>>({})
    const loadRequest = ref<ModelLoadRequest | null>(null)
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
