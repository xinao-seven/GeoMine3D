import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAnalysisStore = defineStore('analysis', () => {
    // 当前图表联动项（如点击某个 series 条目）
    const activeLinkItem = ref<{ type: string; value: string } | null>(null)
    // 图表筛选条件集合（key-value）
    const filterCondition = ref<Record<string, unknown>>({})

    function setActiveLinkItem(item: { type: string; value: string } | null) {
        activeLinkItem.value = item
    }

    function setFilter(key: string, value: unknown) {
        filterCondition.value = { ...filterCondition.value, [key]: value }
    }

    return { activeLinkItem, filterCondition, setActiveLinkItem, setFilter }
})
