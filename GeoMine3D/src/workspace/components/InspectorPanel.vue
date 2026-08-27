<template>
    <aside class="inspector-panel">
        <div class="panel-heading"><div><span>CONTEXT</span><h2>属性检查器</h2></div><el-icon><Operation /></el-icon></div>
        <div class="selection-summary" v-if="selectedObject">
            <span class="selection-type">{{ typeLabel }}</span>
            <h3>{{ selectedObject.name }}</h3>
            <code>{{ selectedObject.id }}</code>
        </div>
        <div class="empty-selection" v-else>
            <div class="crosshair">＋</div><strong>没有选中对象</strong><span>在场景或图层树中选择对象以检查属性</span>
        </div>
        <div class="property-wrap"><PropertyPanel /></div>
        <div class="inspector-section">
            <div class="section-title">显示参数</div>
            <label><span>地层透明度</span><b>{{ Math.round(opacity.stratum * 100) }}%</b></label>
            <el-slider :model-value="opacity.stratum * 100" :show-tooltip="false" @input="setOpacity" />
            <label><span>边缘线</span><el-switch :model-value="showEdges" size="small" @change="sceneStore.setShowEdges($event as boolean)" /></label>
        </div>
    </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import PropertyPanel from '@/components/panels/PropertyPanel.vue'
import { useSceneStore } from '@/stores'
const sceneStore = useSceneStore()
const { selectedObject, opacity, showEdges } = storeToRefs(sceneStore)
const typeLabels: Record<string, string> = { stratum: '地层单元', borehole: '钻孔', workingface: '工作面' }
const typeLabel = computed(() => typeLabels[selectedObject.value?.type || ''] || '空间对象')
function setOpacity(value: number | number[]) { if (typeof value === 'number') sceneStore.setOpacity('stratum', value / 100) }
</script>

<style scoped>
.inspector-panel{height:100%;overflow:auto;background:#121714;border-left:1px solid var(--studio-border)}.panel-heading{height:70px;padding:15px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--studio-border)}.panel-heading span{font:9px Bahnschrift,sans-serif;letter-spacing:.18em;color:var(--studio-copper)}.panel-heading h2{font-size:15px;margin-top:3px}.panel-heading>.el-icon{color:#69736b}.selection-summary{padding:18px 16px;background:linear-gradient(135deg,rgba(177,124,62,.16),transparent);border-bottom:1px solid var(--studio-border)}.selection-type{font-size:10px;color:#c29157}.selection-summary h3{font-size:18px;margin:5px 0}.selection-summary code{font-size:9px;color:#667068}.empty-selection{height:170px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;text-align:center;border-bottom:1px solid var(--studio-border);color:#667068}.empty-selection .crosshair{font:300 35px Georgia;color:#8a6840}.empty-selection strong{font-size:12px;color:#9aa39b}.empty-selection span{font-size:10px;line-height:1.5;max-width:190px}.property-wrap :deep(.panel-title),.property-wrap :deep(.empty-hint){display:none}.property-wrap :deep(.property-panel){padding:15px 16px}.inspector-section{padding:14px 16px;border-top:1px solid var(--studio-border)}.section-title{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#6f7971;margin-bottom:14px}.inspector-section label{display:flex;justify-content:space-between;align-items:center;color:#9ca49d;font-size:11px;margin:9px 0}.inspector-section label b{font:10px Bahnschrift;color:#c38c4c}
</style>
