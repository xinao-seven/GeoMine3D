<template>
    <PageContainer title="工作面管理">
        <template #actions>
            <el-select v-model="statusFilter" placeholder="全部状态" clearable size="small" style="width:130px"
                @change="fetchData">
                <el-option label="开采中" value="开采中" />
                <el-option label="已完成" value="已完成" />
                <el-option label="规划中" value="规划中" />
            </el-select>
            <el-input v-model="keyword" placeholder="搜索工作面" size="small" clearable style="width:180px;margin-left:8px"
                @keyup.enter="fetchData" />
        </template>

        <el-table :data="list" v-loading="loading" style="width:100%"
            :row-style="{ background: 'var(--color-bg-card)', color: 'var(--color-text-primary)' }"
            :header-cell-style="{ background: 'var(--color-bg-panel)', color: 'var(--color-text-secondary)' }">
            <el-table-column prop="code" label="编号" width="90" />
            <el-table-column prop="name" label="工作面名称" min-width="150" />
            <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                    <el-tag :type="statusTagMap[row.status]" size="small">{{ row.status }}</el-tag>
                </template>
            </el-table-column>
            <el-table-column prop="coalSeam" label="煤层" width="80" />
            <el-table-column prop="length" label="走向(m)" width="90" />
            <el-table-column prop="width" label="倾向(m)" width="90" />
            <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="130" fixed="right">
                <template #default="{ row }">
                    <el-button size="small" type="primary" link @click="viewDetail(row)">详情</el-button>
                    <el-button size="small" type="success" link @click="locateToScene(row)">定位</el-button>
                </template>
            </el-table-column>
        </el-table>
    </PageContainer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageContainer from '@/components/common/PageContainer.vue'
import { workingfaceApi } from '@/api'
import { useSceneStore } from '@/stores'
import { ElMessage } from 'element-plus'
import type { WorkingFaceItem } from '@/types'

const router = useRouter()
const sceneStore = useSceneStore()

const list = ref<WorkingFaceItem[]>([])
const loading = ref(false)
const statusFilter = ref('')
const keyword = ref('')

const statusTagMap: Record<string, any> = { '开采中': 'success', '已完成': 'info', '规划中': 'warning' }

async function fetchData() {
    loading.value = true
    try {
        list.value = await workingfaceApi.getWorkingFaceList({
            status: (statusFilter.value as any) || undefined,
            keyword: keyword.value || undefined,
        })
    } finally {
        loading.value = false
    }
}

function viewDetail(row: WorkingFaceItem) {
    ElMessage.info(`工作面详情: ${row.name}`)
}

function locateToScene(row: WorkingFaceItem) {
    sceneStore.locateTo({ type: 'workingface', id: row.modelId ?? row.id, name: row.name })
    router.push('/dashboard')
}

onMounted(fetchData)
</script>
