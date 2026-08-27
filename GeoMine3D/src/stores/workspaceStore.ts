import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'

export type WorkspaceDock = 'overview' | 'borehole' | 'table' | 'performance'

export interface RenderPerformance {
    fps: number
    calls: number
    triangles: number
    geometries: number
    textures: number
}

export const useWorkspaceStore = defineStore('workspace', () => {
    const leftVisible = ref(true)
    const rightVisible = ref(true)
    const bottomVisible = ref(true)
    const activeDock = ref<WorkspaceDock>('overview')
    const commandPaletteVisible = ref(false)
    const performance = reactive<RenderPerformance>({ fps: 0, calls: 0, triangles: 0, geometries: 0, textures: 0 })

    function toggleLeft() { leftVisible.value = !leftVisible.value }
    function toggleRight() { rightVisible.value = !rightVisible.value }
    function toggleBottom() { bottomVisible.value = !bottomVisible.value }
    function openDock(dock: WorkspaceDock) {
        activeDock.value = dock
        bottomVisible.value = true
    }
    function updatePerformance(stats: RenderPerformance) { Object.assign(performance, stats) }

    return {
        leftVisible,
        rightVisible,
        bottomVisible,
        activeDock,
        commandPaletteVisible,
        performance,
        toggleLeft,
        toggleRight,
        toggleBottom,
        openDock,
        updatePerformance,
    }
})
