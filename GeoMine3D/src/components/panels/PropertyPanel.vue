<template>
  <div class="property-panel">
    <div class="panel-title">属性信息</div>

    <div v-if="!selectedObject" class="empty-hint">
      点击三维场景中的对象查看属性
    </div>

    <template v-else>
      <div class="object-type-tag">
        <el-tag :type="tagType" size="small">{{ typeLabel }}</el-tag>
      </div>

      <div class="prop-list">
        <div class="prop-item">
          <span class="prop-key">名称</span>
          <span class="prop-value">{{ selectedObject.name }}</span>
        </div>
        <div class="prop-item">
          <span class="prop-key">类型</span>
          <span class="prop-value">{{ typeLabel }}</span>
        </div>
        <template v-if="selectedObject.data">
          <div class="prop-item" v-for="(val, key) in filteredData" :key="key">
            <span class="prop-key">{{ key }}</span>
            <span class="prop-value">{{ val }}</span>
          </div>
        </template>
      </div>

      <div v-if="selectedObject.type === 'borehole'" class="borehole-action">
        <el-button size="small" type="primary" @click="loadBoreholeChart">
          查看柱状图
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSceneStore, useBoreholeStore } from '@/stores'
import { storeToRefs } from 'pinia'

const sceneStore = useSceneStore()
const boreholeStore = useBoreholeStore()
const { selectedObject } = storeToRefs(sceneStore)

const typeLabel = computed(() => {
  const map: Record<string, string> = { stratum: '地层', borehole: '钻孔', workingface: '工作面' }
  return map[selectedObject.value?.type ?? ''] ?? '未知'
})

const tagType = computed(() => {
  const map: Record<string, string> = { stratum: 'success', borehole: 'primary', workingface: 'warning' }
  return (map[selectedObject.value?.type ?? ''] ?? 'info') as any
})

const filteredData = computed(() => {
  const data = selectedObject.value?.data
  if (!data) return {}
  const skip = ['id', 'name', 'type', 'modelData', 'boreholeData']
  return Object.fromEntries(Object.entries(data).filter(([k]) => !skip.includes(k)))
})

async function loadBoreholeChart() {
  const obj = selectedObject.value
  if (obj?.type === 'borehole') {
    await boreholeStore.fetchDetail(obj.id)
  }
}
</script>

<style scoped>
.property-panel {
  padding: 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-accent);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.empty-hint {
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: center;
  padding: 20px 0;
}

.object-type-tag {
  margin-bottom: 10px;
}

.prop-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.prop-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.prop-key {
  color: var(--color-text-secondary);
  width: 50px;
  flex-shrink: 0;
}

.prop-value {
  color: var(--color-text-primary);
  flex: 1;
  word-break: break-all;
}

.borehole-action {
  margin-top: 12px;
}
</style>
