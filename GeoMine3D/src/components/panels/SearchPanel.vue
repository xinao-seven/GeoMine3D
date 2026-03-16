<template>
  <div class="search-panel">
    <el-input
      v-model="keyword"
      placeholder="搜索钻孔/工作面..."
      size="small"
      clearable
      @keyup.enter="handleSearch"
    >
      <template #prefix><el-icon><Search /></el-icon></template>
    </el-input>

    <div class="result-list" v-if="results.length">
      <div
        class="result-item"
        v-for="item in results"
        :key="item.id"
        @click="handleLocate(item)"
      >
        <el-tag :type="item.type === 'borehole' ? 'primary' : 'warning'" size="small">
          {{ item.type === 'borehole' ? '钻孔' : '工作面' }}
        </el-tag>
        <span class="item-name">{{ item.name }}</span>
      </div>
    </div>

    <div class="no-result" v-else-if="searched && !loading">
      暂无结果
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { boreholeApi, workingfaceApi } from '@/api'
import { useSceneStore } from '@/stores'
import { useRouter } from 'vue-router'

interface ResultItem { id: string; name: string; type: string }

const router = useRouter()
const sceneStore = useSceneStore()
const keyword = ref('')
const results = ref<ResultItem[]>([])
const loading = ref(false)
const searched = ref(false)

async function handleSearch() {
  if (!keyword.value.trim()) return
  loading.value = true
  searched.value = true
  try {
    const [boreholes, workingfaces] = await Promise.all([
      boreholeApi.searchBoreholes(keyword.value),
      workingfaceApi.getWorkingFaceList({ keyword: keyword.value }),
    ])
    results.value = [
      ...boreholes.map(b => ({ id: b.id, name: b.name, type: 'borehole' })),
      ...workingfaces.map(w => ({ id: w.id, name: w.name, type: 'workingface' })),
    ]
  } finally {
    loading.value = false
  }
}

function handleLocate(item: ResultItem) {
  sceneStore.locateTo(item)
  // 如果不在 dashboard，跳转过去
  router.push({ path: '/dashboard', query: { locate: item.id, type: item.type } })
}
</script>

<style scoped>
.search-panel {
  padding: 8px;
}

.result-list {
  margin-top: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.result-item:hover {
  background: var(--color-bg-card);
}

.item-name {
  font-size: 13px;
  color: var(--color-text-primary);
}

.no-result {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
}
</style>
