import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { BoreholeItem, BoreholeDetail, BoreholeListQuery } from '@/types'
import { boreholeApi } from '@/api'

export const useBoreholeStore = defineStore('borehole', () => {
    // 钻孔列表数据（管理页和场景导入使用）
    const list = ref<BoreholeItem[]>([])
    // 当前查看的钻孔详情
    const currentDetail = ref<BoreholeDetail | null>(null)
    // 钻孔相关接口加载状态
    const loading = ref(false)
    // 钻孔列表查询条件（分页/筛选参数）
    const query = ref<BoreholeListQuery>({})

    async function fetchList(params?: BoreholeListQuery) {
        loading.value = true
        try {
            if (params) query.value = params
            list.value = await boreholeApi.getBoreholeList(query.value)
        } finally {
            loading.value = false
        }
    }

    async function fetchDetail(id: string) {
        loading.value = true
        try {
            currentDetail.value = await boreholeApi.getBoreholeDetail(id)
        } finally {
            loading.value = false
        }
    }

    return { list, currentDetail, loading, query, fetchList, fetchDetail }
})
