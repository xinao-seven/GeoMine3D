import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardSummary } from '@/types'
import { analysisApi } from '@/api'

export const useProjectStore = defineStore('project', () => {
  const summary = ref<DashboardSummary | null>(null)
  const loading = ref(false)

  async function fetchSummary() {
    loading.value = true
    try {
      summary.value = await analysisApi.getDashboardSummary()
    } finally {
      loading.value = false
    }
  }

  return { summary, loading, fetchSummary }
})
