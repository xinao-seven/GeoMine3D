<template>
    <div class="dashboard">
        <!-- 左侧面板 -->
        <div class="left-panel">
            <SearchPanel />
            <el-divider />
            <LayerPanel />
        </div>

        <!-- 三维场景区 -->
        <div class="scene-area">
            <SceneCanvas />
        </div>

        <!-- 右侧面板 -->
        <div class="right-panel">
            <PropertyPanel />
            <el-divider />
            <div class="borehole-chart-area" v-if="currentDetail">
                <div class="chart-title">{{ currentDetail.name }} · 柱状图</div>
                <BoreholeChart :borehole="currentDetail" @layer-click="onLayerClick" style="height: 360px;" />
            </div>
            <div class="chart-placeholder" v-else>
                <el-icon :size="32" color="#1e3a5f">
                    <SetUp />
                </el-icon>
                <p>点击钻孔查看柱状图</p>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { storeToRefs } from 'pinia'
import SceneCanvas from '@/components/three/SceneCanvas.vue'
import LayerPanel from '@/components/panels/LayerPanel.vue'
import PropertyPanel from '@/components/panels/PropertyPanel.vue'
import SearchPanel from '@/components/panels/SearchPanel.vue'
import BoreholeChart from '@/components/charts/BoreholeChart.vue'
import { useSceneStore, useBoreholeStore } from '@/stores'

defineOptions({
    name: 'DashboardView',
})

const sceneStore = useSceneStore()
const boreholeStore = useBoreholeStore()
const { selectedObject } = storeToRefs(sceneStore)
const { currentDetail } = storeToRefs(boreholeStore)

// 点击钻孔对象后自动加载详情
watch(selectedObject, async (obj) => {
    if (obj?.type === 'borehole') {
        await boreholeStore.fetchDetail(obj.id)
    }
})

function onLayerClick(layerName: string) {
    sceneStore.setHighlight(layerName)
}
</script>

<style scoped>
.dashboard {
    display: flex;
    height: 100%;
    overflow: hidden;
}

.left-panel {
    width: 220px;
    flex-shrink: 0;
    background: var(--color-bg-panel);
    border-right: 1px solid var(--color-border);
    overflow-y: auto;
    padding: 8px 0;
}

:deep(.el-divider) {
    margin: 8px 0;
    border-color: var(--color-border);
}

.scene-area {
    flex: 1;
    overflow: hidden;
}

.right-panel {
    width: 260px;
    flex-shrink: 0;
    background: var(--color-bg-panel);
    border-left: 1px solid var(--color-border);
    overflow-y: auto;
    padding: 8px 0;
}

.borehole-chart-area {
    padding: 8px;
}

.chart-title {
    font-size: 12px;
    color: var(--color-accent);
    margin-bottom: 6px;
}

.chart-placeholder {
    padding: 40px 20px;
    text-align: center;
    color: var(--color-text-secondary);
}

.chart-placeholder p {
    margin-top: 10px;
    font-size: 12px;
}
</style>
