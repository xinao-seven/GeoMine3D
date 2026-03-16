<template>
  <PageContainer title="模型管理">
    <template #actions>
      <el-select v-model="typeFilter" placeholder="全部类型" clearable size="small" style="width:130px" @change="fetchData">
        <el-option label="地层模型" value="stratum" />
        <el-option label="钻孔模型" value="borehole" />
        <el-option label="工作面模型" value="workingface" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索模型" size="small" clearable style="width:160px;margin-left:8px" @change="fetchData" />
      <el-button size="small" type="primary" style="margin-left:8px" @click="handleUpload">上传模型</el-button>
    </template>

    <el-table :data="list" v-loading="loading" style="width:100%" :row-style="{ background: 'var(--color-bg-card)', color: 'var(--color-text-primary)' }" :header-cell-style="{ background: 'var(--color-bg-panel)', color: 'var(--color-text-secondary)' }">
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
          <el-button size="small" type="primary" link @click="handleView(row)">查看</el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row)">删除</el-button>
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
