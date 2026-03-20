import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardSummary } from '@/types'
import { analysisApi } from '@/api'

export const useProjectStore = defineStore('project', () => {
  // 仪表盘汇总数据（统计卡片、概览等）
  const summary = ref<DashboardSummary | null>(null)
  // 项目概览请求加载状态
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
