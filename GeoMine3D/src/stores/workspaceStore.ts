import { defineStore } from 'pinia'
import { ref } from 'vue'

export type WorkspaceDock = 'overview' | 'borehole' | 'table' | 'performance'

export const useWorkspaceStore = defineStore('workspace', () => {
    const leftVisible = ref(true)
    const rightVisible = ref(true)
    const bottomVisible = ref(true)
    const activeDock = ref<WorkspaceDock>('overview')
    const commandPaletteVisible = ref(false)

    function toggleLeft() { leftVisible.value = !leftVisible.value }
    function toggleRight() { rightVisible.value = !rightVisible.value }
    function toggleBottom() { bottomVisible.value = !bottomVisible.value }
    function openDock(dock: WorkspaceDock) {
        activeDock.value = dock
        bottomVisible.value = true
    }

    return {
        leftVisible,
        rightVisible,
        bottomVisible,
        activeDock,
        commandPaletteVisible,
        toggleLeft,
        toggleRight,
        toggleBottom,
        openDock,
    }
})
