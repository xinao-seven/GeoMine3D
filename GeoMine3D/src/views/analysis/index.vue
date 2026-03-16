<template>
    <PageContainer title="统计分析">
        <div class="charts-grid">
            <!-- 地层厚度分布 -->
            <div class="chart-card">
                <div class="chart-card-title">地层厚度分布（均值）</div>
                <StatsChart :option="thicknessOption" :loading="loading.thickness" @item-click="onThicknessClick"
                    style="height: 240px" />
            </div>

            <!-- 钻孔总深度分布 -->
            <div class="chart-card">
                <div class="chart-card-title">钻孔总深度分布</div>
                <StatsChart :option="depthOption" :loading="loading.depth" @item-click="onDepthClick"
                    style="height: 240px" />
            </div>

            <!-- 工作面状态统计 -->
            <div class="chart-card">
                <div class="chart-card-title">工作面状态统计</div>
                <StatsChart :option="wfStatusOption" :loading="loading.wfStatus" @item-click="onWfStatusClick"
                    style="height: 240px" />
            </div>

            <!-- 地层频次统计 -->
            <div class="chart-card">
                <div class="chart-card-title">地层出现频次</div>
                <StatsChart :option="layerFreqOption" :loading="loading.layerFreq" style="height: 240px" />
            </div>
        </div>
    </PageContainer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageContainer from '@/components/common/PageContainer.vue'
import StatsChart from '@/components/charts/StatsChart.vue'
import { analysisApi } from '@/api'
import { useAnalysisStore, useSceneStore } from '@/stores'
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ChartOption = Record<string, any>

const router = useRouter()
const analysisStore = useAnalysisStore()
const sceneStore = useSceneStore()

const loading = ref({ thickness: false, depth: false, wfStatus: false, layerFreq: false })

const thicknessOption = ref<ChartOption>({})
const depthOption = ref<ChartOption>({})
const wfStatusOption = ref<ChartOption>({})
const layerFreqOption = ref<ChartOption>({})

const BASE_CHART_STYLE = {
    backgroundColor: 'transparent',
    textStyle: { color: '#e8f4ff' },
}

async function loadThickness() {
    loading.value.thickness = true
    try {
        const data = await analysisApi.getThicknessStats()
        thicknessOption.value = {
            ...BASE_CHART_STYLE,
            tooltip: { trigger: 'axis', backgroundColor: '#0d1f3c', borderColor: '#1e3a5f', textStyle: { color: '#e8f4ff' } },
            grid: { left: 60, right: 20, top: 30, bottom: 40 },
            xAxis: { type: 'category', data: data.labels, axisLabel: { color: '#8ab4d4', rotate: 30, fontSize: 11 }, axisLine: { lineStyle: { color: '#1e3a5f' } } },
            yAxis: { type: 'value', name: '厚度(m)', nameTextStyle: { color: '#8ab4d4' }, axisLabel: { color: '#8ab4d4' }, splitLine: { lineStyle: { color: '#1e3a5f' } } },
            series: [{ type: 'bar', data: data.values, itemStyle: { color: '#5470c6', borderRadius: [4, 4, 0, 0] }, emphasis: { itemStyle: { color: '#00c8ff' } } }],
        }
    } finally {
        loading.value.thickness = false
    }
}

async function loadDepth() {
    loading.value.depth = true
    try {
        const data = await analysisApi.getBoreholeDepthStats()
        depthOption.value = {
            ...BASE_CHART_STYLE,
            tooltip: { trigger: 'axis', backgroundColor: '#0d1f3c', borderColor: '#1e3a5f', textStyle: { color: '#e8f4ff' } },
            grid: { left: 60, right: 20, top: 30, bottom: 40 },
            xAxis: { type: 'category', data: data.labels, axisLabel: { color: '#8ab4d4', rotate: 30, fontSize: 11 }, axisLine: { lineStyle: { color: '#1e3a5f' } } },
            yAxis: { type: 'value', name: '深度(m)', nameTextStyle: { color: '#8ab4d4' }, axisLabel: { color: '#8ab4d4' }, splitLine: { lineStyle: { color: '#1e3a5f' } } },
            series: [{ type: 'bar', data: data.values, itemStyle: { color: '#91cc75', borderRadius: [4, 4, 0, 0] }, emphasis: { itemStyle: { color: '#00d98b' } } }],
        }
    } finally {
        loading.value.depth = false
    }
}

async function loadWfStatus() {
    loading.value.wfStatus = true
    try {
        const data = await analysisApi.getWorkingFaceStats()
        wfStatusOption.value = {
            ...BASE_CHART_STYLE,
            tooltip: { trigger: 'item', backgroundColor: '#0d1f3c', borderColor: '#1e3a5f', textStyle: { color: '#e8f4ff' } },
            legend: { orient: 'vertical', right: '5%', textStyle: { color: '#8ab4d4' } },
            series: [{
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['40%', '50%'],
                data: data.items.map(i => ({ name: i.status, value: i.count })),
                itemStyle: { borderColor: '#0a1628', borderWidth: 2 },
                label: { color: '#e8f4ff' },
            }],
        }
    } finally {
        loading.value.wfStatus = false
    }
}

async function loadLayerFreq() {
    loading.value.layerFreq = true
    try {
        const data = await analysisApi.getLayerFrequencyStats()
        layerFreqOption.value = {
            ...BASE_CHART_STYLE,
            tooltip: { trigger: 'axis', backgroundColor: '#0d1f3c', borderColor: '#1e3a5f', textStyle: { color: '#e8f4ff' } },
            grid: { left: 80, right: 20, top: 30, bottom: 40 },
            xAxis: { type: 'value', axisLabel: { color: '#8ab4d4' }, splitLine: { lineStyle: { color: '#1e3a5f' } } },
            yAxis: { type: 'category', data: data.labels, axisLabel: { color: '#8ab4d4', fontSize: 11 }, axisLine: { lineStyle: { color: '#1e3a5f' } } },
            series: [{ type: 'bar', data: data.values, itemStyle: { color: '#fac858', borderRadius: [0, 4, 4, 0] }, emphasis: { itemStyle: { color: '#ffb020' } } }],
        }
    } finally {
        loading.value.layerFreq = false
    }
}

function onThicknessClick(params: any) {
    // 图表点击 -> 跳转到 dashboard 并筛选
    analysisStore.setActiveLinkItem({ type: 'layer', value: params.name })
    router.push('/dashboard')
    ElMessage.success(`已定位到地层: ${params.name}`)
}

function onDepthClick(params: any) {
    // 图表点击 -> 定位到对应钻孔
    analysisStore.setActiveLinkItem({ type: 'borehole', value: params.name })
    router.push('/borehole-management')
}

function onWfStatusClick(params: any) {
    ElMessage.info(`工作面状态: ${params.name}，共 ${params.value} 个`)
}

onMounted(() => {
    loadThickness()
    loadDepth()
    loadWfStatus()
    loadLayerFreq()
})
</script>

<style scoped>
.charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
    gap: 16px;
    height: 100%;
}

.chart-card {
    background: var(--color-bg-panel);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
}

.chart-card-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin-bottom: 8px;
    flex-shrink: 0;
}
</style>
