import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import type { SceneObject, LayerState, OpacityState } from '@/types'

type ModelType = 'stratum' | 'borehole' | 'workingface'

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

  // 各类型模型加载状态（供 LayerPanel 按钮使用）
  const modelStatus = reactive<Record<ModelType, { loaded: boolean; loading: boolean }>>({
    stratum:     { loaded: false, loading: false },
    borehole:    { loaded: false, loading: false },
    workingface: { loaded: false, loading: false },
  })

  // 每次点击加载按钮时递增，对应类型由 SceneCanvas 监听并执行加载
  const loadRequestTick = reactive<Record<ModelType, number>>({
    stratum: 0,
    borehole: 0,
    workingface: 0,
  })

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

  function setModelStatus(type: ModelType, status: Partial<{ loaded: boolean; loading: boolean }>) {
    Object.assign(modelStatus[type], status)
  }

  function requestLoadModel(type: ModelType) {
    if (modelStatus[type].loaded || modelStatus[type].loading) return
    loadRequestTick[type] += 1
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
    modelStatus,
    loadRequestTick,
    locateTarget,
    selectObject,
    setHighlight,
    setLayerVisible,
    setOpacity,
    setShowEdges,
    setModelStatus,
    requestLoadModel,
    locateTo,
  }
})
