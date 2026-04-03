<template>
    <div class="dashboard">
        <!-- 左侧面板 -->
        <aside class="left-panel" :class="{ collapsed: leftCollapsed }">
            <button class="panel-toggle left-toggle" type="button" :aria-label="leftCollapsed ? '展开左侧面板' : '收起左侧面板'"
                @click="toggleLeftPanel">
                <el-icon :size="12">
                    <ArrowRightBold v-if="leftCollapsed" />
                    <ArrowLeftBold v-else />
                </el-icon>
            </button>
            <div class="collapsed-label" v-if="leftCollapsed">图层</div>
            <div class="panel-scroll-content" v-else>
                <SearchPanel />
                <el-divider />
                <LayerPanel />
            </div>
        </aside>

        <!-- 三维场景区 -->
        <div class="scene-area">
            <SceneCanvas />
        </div>

        <!-- 右侧面板 -->
        <aside class="right-panel" :class="{ collapsed: rightCollapsed }">
            <button class="panel-toggle right-toggle" type="button" :aria-label="rightCollapsed ? '展开右侧面板' : '收起右侧面板'"
                @click="toggleRightPanel">
                <el-icon :size="12">
                    <ArrowLeftBold v-if="rightCollapsed" />
                    <ArrowRightBold v-else />
                </el-icon>
            </button>
            <div class="collapsed-label" v-if="rightCollapsed">属性</div>
            <div class="panel-scroll-content" v-else>
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
        </aside>
    </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
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
const leftCollapsed = ref(false)
const rightCollapsed = ref(false)

// 点击钻孔对象后自动加载详情
watch(selectedObject, async (obj) => {
    if (obj?.type === 'borehole') {
        await boreholeStore.fetchDetail(obj.id)
    }
})

function onLayerClick(layerName: string) {
    sceneStore.setHighlight(layerName)
}

function toggleLeftPanel() {
    leftCollapsed.value = !leftCollapsed.value
}

function toggleRightPanel() {
    rightCollapsed.value = !rightCollapsed.value
}
</script>

<style scoped>
.dashboard {
    display: flex;
    height: 100%;
    overflow: hidden;
}

.left-panel,
.right-panel {
    position: relative;
    flex-shrink: 0;
    background: var(--color-bg-panel);
    overflow: hidden;
    transition: width 0.24s ease;
}

.left-panel {
    width: 220px;
    border-right: 1px solid var(--color-border);
}

:deep(.el-divider) {
    margin: 8px 0;
    border-color: var(--color-border);
}

.scene-area {
    flex: 1;
    overflow: hidden;
    min-width: 0;
}

.right-panel {
    width: 260px;
    border-left: 1px solid var(--color-border);
}

.panel-scroll-content {
    overflow-y: auto;
    height: 100%;
    padding: 8px 0;
}

.left-panel.collapsed,
.right-panel.collapsed {
    width: 40px;
}

.panel-toggle {
    position: absolute;
    top: 12px;
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid rgba(0, 200, 255, 0.35);
    border-radius: 50%;
    background: linear-gradient(145deg, rgba(0, 200, 255, 0.16), rgba(0, 200, 255, 0.04));
    color: var(--color-accent);
    cursor: pointer;
    z-index: 2;
    transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.panel-toggle:hover {
    transform: scale(1.05);
    border-color: rgba(0, 200, 255, 0.55);
    background: linear-gradient(145deg, rgba(0, 200, 255, 0.24), rgba(0, 200, 255, 0.08));
    color: #e8f8ff;
}

.left-toggle {
    right: 8px;
}

.right-toggle {
    left: 8px;
}

.collapsed-label {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    writing-mode: vertical-rl;
    text-orientation: mixed;
    letter-spacing: 2px;
    font-size: 11px;
    color: var(--color-text-secondary);
    user-select: none;
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
