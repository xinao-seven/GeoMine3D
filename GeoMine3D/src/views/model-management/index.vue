<template>
  <PageContainer title="模型管理">
    <template #actions>
      <div class="toolbar-actions">
        <el-select v-model="typeFilter" class="toolbar-select" placeholder="全部类型" clearable size="small" @change="fetchData">
          <el-option label="地层模型" value="stratum" />
          <el-option label="钻孔模型" value="borehole" />
          <el-option label="工作面模型" value="workingface" />
        </el-select>
        <el-input v-model="keyword" class="toolbar-input" placeholder="搜索模型" size="small" clearable @change="fetchData" />
        <el-button class="primary-action-btn" size="small" type="primary" @click="handleUpload">上传模型</el-button>
      </div>
    </template>

    <el-table class="main-table" :data="list" v-loading="loading" style="width:100%" :row-style="{ background: 'var(--color-bg-card)', color: 'var(--color-text-primary)' }" :header-cell-style="{ background: 'var(--color-bg-panel)', color: 'var(--color-text-secondary)' }">
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="type" label="类型" width="110">
        <template #default="{ row }">
          <el-tag :type="typeTagMap[row.type]" size="small">{{ typeLabelMap[row.type] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column prop="format" label="格式" width="80">
        <template #default="{ row }">
          <el-tag size="small">{{ row.format.toUpperCase() }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button class="table-action-btn" size="small" type="primary" link @click="handleView(row)">查看</el-button>
          <el-button class="table-action-btn danger-action" size="small" type="danger" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageContainer from '@/components/common/PageContainer.vue'
import { modelApi } from '@/api'
import { useSceneStore } from '@/stores'
import type { ModelItem } from '@/types'

const router = useRouter()
const sceneStore = useSceneStore()

const list = ref<ModelItem[]>([])
const loading = ref(false)
const typeFilter = ref('')
const keyword = ref('')

const typeTagMap: Record<string, any> = { stratum: 'success', borehole: 'primary', workingface: 'warning' }
const typeLabelMap: Record<string, string> = { stratum: '地层', borehole: '钻孔', workingface: '工作面' }

async function fetchData() {
  loading.value = true
  try {
    list.value = await modelApi.getModelList({ type: typeFilter.value || undefined, keyword: keyword.value || undefined })
  } finally {
    loading.value = false
  }
}

function handleView(row: ModelItem) {
  sceneStore.locateTo({ type: row.type, id: row.id, name: row.name })
  router.push('/dashboard')
}

async function handleDelete(row: ModelItem) {
  await ElMessageBox.confirm(`确认删除模型「${row.name}」？`, '提示', { type: 'warning' })
  ElMessage.info('删除功能本阶段为占位实现')
}

function handleUpload() {
  ElMessage.info('上传功能本阶段为占位实现')
}

onMounted(fetchData)
</script>

<style scoped>
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-select {
  width: 130px;
}

.toolbar-input {
  width: 160px;
}

.primary-action-btn {
  margin-left: 4px;
  border: 1px solid rgba(0, 200, 255, 0.35);
  background: linear-gradient(135deg, #00c8ff 0%, #0094ff 100%);
  box-shadow: 0 6px 16px rgba(0, 148, 255, 0.28);
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
}

.primary-action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 18px rgba(0, 148, 255, 0.32);
  filter: brightness(1.05);
}

.primary-action-btn:active {
  transform: translateY(0);
}

.table-action-btn {
  font-weight: 600;
  letter-spacing: 0.2px;
  transition: color 0.2s ease, opacity 0.2s ease;
}

.table-action-btn:not(.is-disabled):hover {
  color: var(--color-accent-hover);
}

.table-action-btn.danger-action:not(.is-disabled):hover {
  color: #ff7a7a;
}

.main-table {
  --el-table-bg-color: var(--color-bg-card);
  --el-table-border-color: var(--color-border);
  --el-table-tr-bg-color: var(--color-bg-card);
  --el-table-row-hover-bg-color: rgba(0, 200, 255, 0.12);
  --el-table-current-row-bg-color: rgba(0, 200, 255, 0.2);
}

.main-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background-color: rgba(0, 200, 255, 0.12) !important;
}

.main-table :deep(.el-table__body tr.current-row > td.el-table__cell) {
  background-color: rgba(0, 200, 255, 0.2) !important;
  box-shadow: inset 0 0 0 1px rgba(0, 200, 255, 0.25);
}

.main-table :deep(.el-table__fixed-right-patch),
.main-table :deep(.el-table__fixed),
.main-table :deep(.el-table__fixed-right) {
  background-color: var(--color-bg-card);
}
</style>
