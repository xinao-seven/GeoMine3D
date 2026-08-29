import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { BoreholeItem, BoreholeDetail } from '@/types'
import { toBoreholeDetail, workspaceApi } from '@/api/workspace'

export const useBoreholeStore = defineStore('borehole', () => {
    // 钻孔列表数据（管理页和场景导入使用）
    const list = ref<BoreholeItem[]>([])
    // 当前查看的钻孔详情
    const currentDetail = ref<BoreholeDetail | null>(null)
    // 钻孔相关接口加载状态
    const loading = ref(false)
    async function fetchDetail(id: string) {
        loading.value = true
        try {
            const cached = list.value.find(item => item.id === id) as BoreholeDetail | undefined
            if (cached?.layers) {
                currentDetail.value = cached
                return
            }
            currentDetail.value = toBoreholeDetail(await workspaceApi.getBorehole(id))
        } finally {
            loading.value = false
        }
    }

    return { list, currentDetail, loading, fetchDetail }
})
