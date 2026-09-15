import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type SettlementColorMode = 'original' | 'dz' | 'magnitude'

/**
 * 沉陷对比面板状态。
 *
 * 与三维引擎侧的 `SettlementManager` 通过 SceneCanvas 的 watch 单向同步:
 * store 只存 UI 参数,不持有几何。
 */
export const useSettlementStore = defineStore('settlement', () => {
    /** 位移场是否已拉到(打开面板时才拉,避免无谓的 4 MB 请求) */
    const fieldLoaded = ref(false)
    const loading = ref(false)
    const loadError = ref<string | null>(null)

    /** 是否启用沉陷对比(启用才把位移挂到几何上) */
    const enabled = ref(false)
    /** 变形进程 0=沉陷前,1=沉陷后 */
    const time = ref(1)
    /** 沉陷夸大倍数(纯显示端) */
    const exaggeration = ref(10)
    /** 着色模式 */
    const colorMode = ref<SettlementColorMode>('original')

    /** 位移场元信息 */
    const maxSubsidenceM = ref(0)
    const maxHorizontalM = ref(0)
    const displayZScale = ref(20)
    const workingsFollow = ref(false)
    const generatedUtc = ref('')

    /** 已绑定到几何的层数 / 顶点总数 */
    const boundLayers = ref(0)
    const boundVertices = ref(0)

    /** 当前实际施加的最大竖向位移(模型单位,未乘显示 z 夸张) */
    const appliedMaxDz = ref(0)

    const timePercent = computed({
        get: () => Math.round(time.value * 100),
        set: (v: number) => { time.value = Math.min(1, Math.max(0, v / 100)) },
    })

    /** 夸大后、再乘显示 z 夸张,换算成场景里肉眼可见的高差 */
    const visibleDropDisplayUnits = computed(
        () => time.value * exaggeration.value * maxSubsidenceM.value * displayZScale.value,
    )

    function reset() {
        time.value = 1
        exaggeration.value = 10
        colorMode.value = 'original'
        appliedMaxDz.value = 0
        boundLayers.value = 0
        boundVertices.value = 0
    }

    function resetSession() {
        enabled.value = false
        fieldLoaded.value = false
        loading.value = false
        loadError.value = null
        reset()
    }

    return {
        fieldLoaded,
        loading,
        loadError,
        enabled,
        time,
        exaggeration,
        colorMode,
        maxSubsidenceM,
        maxHorizontalM,
        displayZScale,
        workingsFollow,
        generatedUtc,
        boundLayers,
        boundVertices,
        appliedMaxDz,
        timePercent,
        visibleDropDisplayUnits,
        reset,
        resetSession,
    }
})
