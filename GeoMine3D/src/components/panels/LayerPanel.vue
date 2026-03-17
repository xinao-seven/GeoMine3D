<template>
    <div class="layer-panel">
        <div class="panel-title">图层控制</div>

        <div class="edge-toggle">
            <span class="edge-label">显示边缘线</span>
            <el-switch v-model="edgeVisible" size="small" @change="onEdgeVisibleChange" />
        </div>

        <div class="layer-item" v-for="layer in layers" :key="layer.type">
            <div class="layer-header">
                <el-switch v-model="layer.visible" @change="onVisibleChange(layer.type, $event as boolean)"
                    size="small" />
                <span class="layer-name">{{ layer.label }}</span>
                <el-button class="load-btn" size="small" :loading="modelStatus[layer.type].loading"
                    :disabled="modelStatus[layer.type].loaded || modelStatus[layer.type].loading"
                    @click="onLoadClick(layer.type)">
                    {{ modelStatus[layer.type].loaded ? '已加载' : '加载' }}
                </el-button>
            </div>
            <div class="layer-opacity" v-if="layer.type === 'stratum'">
                <span class="opacity-label">透明度</span>
                <el-slider v-model="layer.opacity" :min="0" :max="100" :step="5" size="small"
                    @change="onOpacityChange(layer.type, $event as number)" />
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { storeToRefs } from 'pinia'
import { useSceneStore } from '@/stores'

const sceneStore = useSceneStore()
const { modelStatus, showEdges } = storeToRefs(sceneStore)
const edgeVisible = showEdges

type ModelType = 'stratum' | 'borehole' | 'workingface'

const layers = reactive<Array<{ type: ModelType; label: string; visible: boolean; opacity: number }>>([
    { type: 'stratum', label: '地层模型', visible: true, opacity: 100 },
    { type: 'borehole', label: '钻孔', visible: true, opacity: 100 },
    { type: 'workingface', label: '工作面', visible: true, opacity: 100 },
])

function onVisibleChange(type: string, visible: boolean) {
    sceneStore.setLayerVisible(type as any, visible)
}

function onOpacityChange(type: string, value: number) {
    sceneStore.setOpacity(type as any, value / 100)
}

function onLoadClick(type: ModelType) {
    sceneStore.requestLoadModel(type)
}

function onEdgeVisibleChange(visible: boolean) {
    sceneStore.setShowEdges(visible)
}
</script>

<style scoped>
.layer-panel {
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

.edge-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    padding: 6px 8px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
}

.edge-label {
    font-size: 12px;
    color: var(--color-text-secondary);
}

.layer-item {
    margin-bottom: 12px;
}

.layer-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.layer-name {
    font-size: 13px;
    color: var(--color-text-primary);
    flex: 1;
}

.load-btn {
    margin-left: auto;
}

.layer-opacity {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-left: 32px;
}

.opacity-label {
    font-size: 11px;
    color: var(--color-text-secondary);
    flex-shrink: 0;
    width: 36px;
}

:deep(.el-slider) {
    flex: 1;
}
</style>
