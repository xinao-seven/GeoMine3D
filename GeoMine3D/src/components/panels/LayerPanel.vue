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
            </div>
            <div class="layer-opacity" v-if="layer.type === 'stratum'">
                <span class="opacity-label">透明度</span>
                <el-slider v-model="layer.opacity" :min="0" :max="100" :step="5" size="small"
                    @change="onOpacityChange(layer.type, $event as number)" />
            </div>

            <div class="stratum-controls" v-if="layer.type === 'stratum' && stratumLayers.length">
                <div class="stratum-title">地层单元控制</div>
                <div class="stratum-item" v-for="item in stratumLayers" :key="item.key">
                    <div class="stratum-item-head">
                        <el-switch :model-value="item.visible"
                            @change="onStratumVisibleChange(item, $event as boolean)" size="small" />
                        <span class="stratum-name" :title="`${item.modelName} / ${item.layerName}`">{{ item.layerName }}</span>
                        <el-color-picker :model-value="item.color" size="small" @change="onStratumColorChange(item, $event)" />
                    </div>
                    <div class="stratum-item-opacity">
                        <span class="stratum-opacity-label">透明度</span>
                        <el-slider :model-value="Math.round(item.opacity * 100)" :min="0" :max="100" :step="5"
                            size="small" @input="onStratumOpacityChange(item, $event as number)"
                            @change="onStratumOpacityChange(item, $event as number)" />
                    </div>
                </div>
            </div>

            <div class="model-list" v-loading="optionLoading[layer.type]">
                <template v-if="layer.type === 'borehole'">
                    <div class="model-row">
                        <span class="model-name">共 {{ optionsByType.borehole.length }} 个钻孔</span>
                        <el-button class="load-btn" size="small"
                            :loading="sceneStore.getModelLoadStatus('borehole', BOREHOLE_ALL_ID).loading"
                            :disabled="sceneStore.getModelLoadStatus('borehole', BOREHOLE_ALL_ID).loaded || sceneStore.getModelLoadStatus('borehole', BOREHOLE_ALL_ID).loading || optionsByType.borehole.length === 0"
                            @click="onLoadAllBoreholes()">
                            {{ sceneStore.getModelLoadStatus('borehole', BOREHOLE_ALL_ID).loaded ? '已全部导入' : '全部导入' }}
                        </el-button>
                    </div>
                </template>
                <template v-else>
                    <div class="model-row" v-for="(item, idx) in optionsByType[layer.type]" :key="item.id">
                        <span class="model-name" :title="item.name">{{ item.name }}</span>
                        <el-button class="load-btn" size="small"
                            :loading="sceneStore.getModelLoadStatus(layer.type, item.id).loading"
                            :disabled="sceneStore.getModelLoadStatus(layer.type, item.id).loaded || sceneStore.getModelLoadStatus(layer.type, item.id).loading"
                            @click="onLoadClick(layer.type, item)">
                            {{ sceneStore.getModelLoadStatus(layer.type, item.id).loaded ? '已导入' : '导入' }}
                        </el-button>
                    </div>
                    <div class="model-empty" v-if="!optionLoading[layer.type] && optionsByType[layer.type].length === 0">
                        暂无可导入模型
                    </div>
                </template>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useSceneStore } from '@/stores'
import { modelApi, boreholeApi } from '@/api'
import type { ModelItem, BoreholeItem, StratumLayerControl } from '@/types'

const sceneStore = useSceneStore()
const { showEdges, stratumLayers } = storeToRefs(sceneStore)
const edgeVisible = showEdges

type ModelType = 'stratum' | 'borehole' | 'workingface'
type ModelOption = Pick<ModelItem, 'id' | 'name'> | Pick<BoreholeItem, 'id' | 'name'>
const BOREHOLE_ALL_ID = '__all__'

const layers = reactive<Array<{ type: ModelType; label: string; visible: boolean; opacity: number }>>([
    { type: 'stratum', label: '地层模型', visible: true, opacity: 100 },
    { type: 'borehole', label: '钻孔', visible: true, opacity: 100 },
    { type: 'workingface', label: '工作面', visible: true, opacity: 100 },
])

const optionLoading = reactive<Record<ModelType, boolean>>({
    stratum: false,
    borehole: false,
    workingface: false,
})

const optionsByType = reactive<Record<ModelType, ModelOption[]>>({
    stratum: [],
    borehole: [],
    workingface: [],
})

function onVisibleChange(type: string, visible: boolean) {
    sceneStore.setLayerVisible(type as any, visible)
}

function onOpacityChange(type: string, value: number) {
    sceneStore.setOpacity(type as any, value / 100)
}

function onLoadClick(type: ModelType, item: ModelOption) {
    sceneStore.requestLoadModel({
        type,
        id: item.id,
        name: item.name,
        model: item as ModelItem,
    })
}

function onLoadAllBoreholes() {
    sceneStore.requestLoadModel({
        type: 'borehole',
        id: BOREHOLE_ALL_ID,
        name: '全部钻孔',
        boreholeList: optionsByType.borehole as BoreholeItem[],
    })
}

function onEdgeVisibleChange(visible: boolean) {
    sceneStore.setShowEdges(visible)
}

function onStratumVisibleChange(layer: StratumLayerControl, visible: boolean) {
    sceneStore.updateStratumLayer(layer.key, { visible })
}

function onStratumColorChange(layer: StratumLayerControl, color: string | null) {
    if (!color) return
    sceneStore.updateStratumLayer(layer.key, { color })
}

function onStratumOpacityChange(layer: StratumLayerControl, value: number) {
    sceneStore.updateStratumLayer(layer.key, { opacity: value / 100 })
}

async function loadOptions() {
    optionLoading.stratum = true
    optionLoading.workingface = true
    optionLoading.borehole = true
    try {
        const [stratum, workingface, borehole] = await Promise.all([
            modelApi.getModelList({ type: 'stratum' }),
            modelApi.getModelList({ type: 'workingface' }),
            boreholeApi.getBoreholeList(),
        ])
        optionsByType.stratum = stratum
        optionsByType.workingface = workingface
        optionsByType.borehole = borehole
    } finally {
        optionLoading.stratum = false
        optionLoading.workingface = false
        optionLoading.borehole = false
    }
}

onMounted(() => {
    loadOptions()
})
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
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 8px;
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
    min-width: 45px;
    border: 1px solid rgba(0, 200, 255, 0.34);
    border-radius: 6px;
    background: linear-gradient(140deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.02));
    color: #d9f4ff;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 6px 14px rgba(2, 18, 36, 0.25);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.load-btn:hover:not(.is-disabled) {
    transform: translateY(-1px);
    border-color: rgba(0, 200, 255, 0.6);
    background: linear-gradient(140deg, rgba(0, 200, 255, 0.26), rgba(255, 255, 255, 0.05));
    color: #f2fbff;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 10px 16px rgba(0, 86, 132, 0.28);
}

.load-btn:active:not(.is-disabled) {
    transform: translateY(0);
}

.load-btn.is-disabled,
.load-btn.is-disabled:hover {
    background: linear-gradient(140deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.02));
    border-color: rgba(138, 180, 212, 0.3);
    color: rgba(138, 180, 212, 0.8);
    box-shadow: none;
}

.model-list {
    margin-top: 6px;
    max-height: 400px;
    overflow-y: auto;
    border-top: 1px dashed var(--color-border);
    padding-top: 6px;
}

.model-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
}

.model-name {
    font-size: 12px;
    color: var(--color-text-secondary);
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.model-empty {
    font-size: 12px;
    color: var(--color-text-secondary);
    padding: 6px 0;
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

.stratum-controls {
    margin-top: 8px;
    border-top: 1px dashed var(--color-border);
    padding-top: 8px;
}

.stratum-title {
    font-size: 12px;
    color: var(--color-text-secondary);
    margin-bottom: 6px;
}

.stratum-item {
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 6px;
    margin-bottom: 6px;
}

.stratum-item-head {
    display: flex;
    align-items: center;
    gap: 8px;
}

.stratum-name {
    font-size: 12px;
    color: var(--color-text-primary);
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.stratum-item-opacity {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
}

.stratum-opacity-label {
    font-size: 11px;
    color: var(--color-text-secondary);
    width: 40px;
    flex-shrink: 0;
}

:deep(.el-slider) {
    flex: 1;
}
</style>
