import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { BoreholeItem, BoreholeDetail, BoreholeListQuery } from '@/types'
import { boreholeApi } from '@/api'

export const useBoreholeStore = defineStore('borehole', () => {
  const list = ref<BoreholeItem[]>([])
  const currentDetail = ref<BoreholeDetail | null>(null)
  const loading = ref(false)
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
