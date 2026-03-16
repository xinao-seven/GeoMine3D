<template>
  <PageContainer title="钻孔管理">
    <template #actions>
      <el-input v-model="keyword" placeholder="搜索钻孔名称" size="small" clearable style="width:200px" @keyup.enter="fetchData" @clear="fetchData" />
      <el-button size="small" type="primary" icon="Search" style="margin-left:8px" @click="fetchData">搜索</el-button>
    </template>

    <div style="display:flex;gap:16px;height:100%">
      <el-table :data="list" v-loading="loading" style="flex:1" highlight-current-row @current-change="handleRowSelect" :row-style="{ background: 'var(--color-bg-card)', color: 'var(--color-text-primary)' }" :header-cell-style="{ background: 'var(--color-bg-panel)', color: 'var(--color-text-secondary)' }">
        <el-table-column prop="name" label="钻孔名称" min-width="100" />
        <el-table-column prop="totalDepth" label="总深度(m)" width="110">
          <template #default="{ row }">{{ row.totalDepth.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="layerCount" label="层数" width="70" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewDetail(row)">详情</el-button>
            <el-button size="small" type="success" link @click="locateToScene(row)">定位</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 详情侧边栏 -->
      <div class="detail-panel" v-if="currentDetail">
        <div class="detail-title">{{ currentDetail.name }}</div>
        <div class="detail-meta">总深度: {{ currentDetail.totalDepth.toFixed(1) }}m · {{ currentDetail.layerCount }} 层</div>
        <el-table :data="currentDetail.layers" size="small" :row-style="{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)' }" :header-cell-style="{ background: 'var(--color-bg-panel)', color: 'var(--color-text-secondary)' }">
          <el-table-column prop="layerName" label="地层" min-width="80" />
          <el-table-column prop="topDepth" label="顶深" width="70"><template #default="{row}">{{ row.topDepth }}m</template></el-table-column>
          <el-table-column prop="bottomDepth" label="底深" width="70"><template #default="{row}">{{ row.bottomDepth }}m</template></el-table-column>
          <el-table-column prop="thickness" label="厚度" width="70"><template #default="{row}">{{ row.thickness }}m</template></el-table-column>
        </el-table>
        <BoreholeChart :borehole="currentDetail" style="height:300px;margin-top:16px" />
      </div>
    </div>
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageContainer from '@/components/common/PageContainer.vue'
import BoreholeChart from '@/components/charts/BoreholeChart.vue'
import { boreholeApi } from '@/api'
import { useSceneStore, useBoreholeStore } from '@/stores'
import { storeToRefs } from 'pinia'
import type { BoreholeItem } from '@/types'

const router = useRouter()
const sceneStore = useSceneStore()
const boreholeStore = useBoreholeStore()
const { currentDetail } = storeToRefs(boreholeStore)

const list = ref<BoreholeItem[]>([])
const loading = ref(false)
const keyword = ref('')

async function fetchData() {
  loading.value = true
  try {
    list.value = await boreholeApi.getBoreholeList({ keyword: keyword.value || undefined })
  } finally {
    loading.value = false
  }
}

async function handleRowSelect(row: BoreholeItem | null) {
  if (row) await boreholeStore.fetchDetail(row.id)
}

async function viewDetail(row: BoreholeItem) {
  await boreholeStore.fetchDetail(row.id)
}

function locateToScene(row: BoreholeItem) {
  sceneStore.locateTo({ type: 'borehole', id: row.id, name: row.name })
  router.push('/dashboard')
}

onMounted(fetchData)
</script>

<style scoped>
.detail-panel {
  width: 320px;
  flex-shrink: 0;
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 12px;
  overflow-y: auto;
}

.detail-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-accent);
  margin-bottom: 4px;
}

.detail-meta {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}
</style>
