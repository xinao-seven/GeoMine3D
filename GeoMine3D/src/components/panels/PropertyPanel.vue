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

      <div v-if="selectedBorehole" class="borehole-detail">
        <div class="borehole-metrics">
          <div><span>总深度</span><strong>{{ selectedBorehole.totalDepth.toFixed(2) }}</strong><small>m</small></div>
          <div><span>地层数</span><strong>{{ selectedBorehole.layers.length }}</strong><small>层</small></div>
        </div>
        <div v-if="selectedBorehole.location" class="coordinate-block">
          <span>投影坐标</span>
          <code>X {{ selectedBorehole.location.x.toFixed(2) }}</code>
          <code>Y {{ selectedBorehole.location.y.toFixed(2) }}</code>
          <code>Z {{ selectedBorehole.location.z.toFixed(2) }}</code>
        </div>
        <div class="strata-heading"><span>钻孔分层</span><b>{{ selectedBorehole.layers.length }}</b></div>
        <div class="strata-list">
          <div v-for="(layer, index) in selectedBorehole.layers" :key="`${layer.layerName}-${index}`" class="strata-item">
            <i :style="{ background: layerColor(index) }"></i>
            <div><strong>{{ layer.layerName }}</strong><span>{{ layer.topDepth.toFixed(2) }} — {{ layer.bottomDepth.toFixed(2) }} m</span></div>
            <b>{{ layer.thickness.toFixed(2) }}</b>
          </div>
        </div>
      </div>

      <div v-else class="prop-list">
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
import { useSceneStore, useBoreholeStore, useWorkspaceStore } from '@/stores'
import { storeToRefs } from 'pinia'
import type { BoreholeDetail } from '@/types'

const sceneStore = useSceneStore()
const boreholeStore = useBoreholeStore()
const workspaceStore = useWorkspaceStore()
const { selectedObject } = storeToRefs(sceneStore)

const typeLabel = computed(() => {
  const map: Record<string, string> = { stratum: '地层', borehole: '钻孔', workingface: '工作面' }
  return map[selectedObject.value?.type ?? ''] ?? '未知'
})

const tagType = computed(() => {
  const map: Record<string, string> = { stratum: 'success', borehole: 'primary', workingface: 'warning' }
  return (map[selectedObject.value?.type ?? ''] ?? 'info') as any
})

const selectedBorehole = computed(() => {
  if (selectedObject.value?.type !== 'borehole') return null
  const data = selectedObject.value.data as Partial<BoreholeDetail> | undefined
  return data?.layers && typeof data.totalDepth === 'number' ? data as BoreholeDetail : null
})

const strataColors = ['#a98a5f', '#766950', '#876345', '#586c60', '#6f7776', '#3f4642', '#b69763']
function layerColor(index: number) { return strataColors[index % strataColors.length] }

const filteredData = computed(() => {
  const data = selectedObject.value?.data
  if (!data) return {}
  const skip = ['id', 'name', 'type', 'modelData', 'boreholeData', 'layers', 'location']
  return Object.fromEntries(Object.entries(data).filter(([k]) => !skip.includes(k)))
})

async function loadBoreholeChart() {
  const obj = selectedObject.value
  if (obj?.type === 'borehole') {
    await boreholeStore.fetchDetail(obj.id)
    workspaceStore.openDock('borehole')
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
  justify-content: space-between;
}

.prop-key {
  color: var(--color-text-secondary);
  width: 50px;
  flex-shrink: 0;
}

.prop-value {
  color: var(--color-text-primary);
  
  word-break: break-all;
}

.borehole-action {
  margin-top: 12px;
}

.borehole-detail { display:flex; flex-direction:column; gap:12px; }
.borehole-metrics { display:grid; grid-template-columns:1fr 1fr; gap:7px; }
.borehole-metrics>div { padding:10px; border-left:2px solid #80603a; background:#171c18; }
.borehole-metrics span { display:block; color:#707971; font-size:9px; }
.borehole-metrics strong { color:#ddd8ca; font:20px Bahnschrift,sans-serif; }
.borehole-metrics small { margin-left:4px; color:#7d867e; font-size:9px; }
.coordinate-block { display:grid; grid-template-columns:1fr; gap:4px; padding:9px 10px; border:1px solid #303731; }
.coordinate-block span { margin-bottom:3px; color:#8e9790; font-size:10px; }
.coordinate-block code { color:#68736b; font:9px Bahnschrift,sans-serif; }
.strata-heading { display:flex; justify-content:space-between; padding-bottom:7px; border-bottom:1px solid #303731; color:#9da59e; font-size:10px; }
.strata-heading b { color:#a87943; font:9px Bahnschrift,sans-serif; }
.strata-list { max-height:300px; overflow:auto; }
.strata-item { min-height:43px; display:grid; grid-template-columns:5px minmax(0,1fr) 42px; align-items:center; gap:8px; border-bottom:1px solid #272d28; }
.strata-item i { width:5px; height:25px; }
.strata-item div { min-width:0; display:flex; flex-direction:column; gap:3px; }
.strata-item strong { overflow:hidden; color:#b9beb7; font-size:10px; font-weight:500; text-overflow:ellipsis; white-space:nowrap; }
.strata-item span { color:#626b64; font:8px Bahnschrift,sans-serif; }
.strata-item>b { color:#8f795c; font:9px Bahnschrift,sans-serif; text-align:right; }
</style>
