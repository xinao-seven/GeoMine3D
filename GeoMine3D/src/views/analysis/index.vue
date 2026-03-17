<template>
    <PageContainer title="统计分析">
        <div class="charts-grid">
            <!-- 地层厚度分布 -->
            <div class="chart-card">
                <div class="chart-card-title">地层厚度分布（均值）</div>
                <div class="chart-body">
                    <StatsChart :option="thicknessOption" :loading="loading.thickness" @item-click="onThicknessClick" />
                </div>
            </div>

            <!-- 钻孔总深度分布 -->
            <div class="chart-card">
                <div class="chart-card-title">钻孔总深度分布</div>
                <div class="chart-body">
                    <StatsChart :option="depthOption" :loading="loading.depth" @item-click="onDepthClick" />
                </div>
            </div>

            <!-- 钻孔位置散点图 -->
            <div class="chart-card">
                <div class="chart-card-title">钻孔位置散点图（原始 X-Y）</div>
                <div class="chart-body">
                    <StatsChart :option="boreholeLocationOption" :loading="loading.boreholeLocation" @item-click="onBoreholeLocationClick" />
                </div>
            </div>

            <!-- 地层频次统计 -->
            <div class="chart-card">
                <div class="chart-card-title">地层出现频次</div>
                <div class="chart-body">
                    <StatsChart :option="layerFreqOption" :loading="loading.layerFreq" />
                </div>
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

const loading = ref({ thickness: false, depth: false, boreholeLocation: false, layerFreq: false })

const thicknessOption = ref<ChartOption>({})
const depthOption = ref<ChartOption>({})
const boreholeLocationOption = ref<ChartOption>({})
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

async function loadBoreholeLocation() {
    loading.value.boreholeLocation = true
    try {
        const data = await analysisApi.getBoreholeXYRawStats()
        const points = data.items.map(item => ({
            name: item.name,
            id: item.id,
            value: [item.x, item.y, item.z],
        }))

        const xValues = points.map(p => p.value[0])
        const yValues = points.map(p => p.value[1])
        const xMin = Math.min(...xValues)
        const xMax = Math.max(...xValues)
        const yMin = Math.min(...yValues)
        const yMax = Math.max(...yValues)
        const xSpan = xMax - xMin
        const ySpan = yMax - yMin
        const xPadding = xSpan > 0 ? xSpan * 0.08 : 10
        const yPadding = ySpan > 0 ? ySpan * 0.08 : 10

        boreholeLocationOption.value = {
            ...BASE_CHART_STYLE,
            tooltip: {
                trigger: 'item',
                backgroundColor: '#0d1f3c',
                borderColor: '#1e3a5f',
                textStyle: { color: '#e8f4ff' },
                formatter: (params: any) => {
                    const [x, y, z] = params.value
                    return `${params.name}<br/>X: ${x.toFixed(2)}<br/>Y: ${y.toFixed(2)}<br/>Z(高程): ${z.toFixed(2)}`
                },
            },
            xAxis: {
                type: 'value',
                name: 'X (m)',
                min: xMin - xPadding,
                max: xMax + xPadding,
                nameTextStyle: { color: '#8ab4d4' },
                axisLabel: {
                    color: '#8ab4d4',
                    formatter: (value: number) => Number(value).toExponential(2),
                },
                axisLine: { lineStyle: { color: '#1e3a5f' } },
                splitLine: { lineStyle: { color: 'rgba(30,58,95,0.5)' } },
            },
            yAxis: {
                type: 'value',
                name: 'Y (m)',
                min: yMin - yPadding,
                max: yMax + yPadding,
                nameTextStyle: { color: '#8ab4d4' },
                axisLabel: {
                    color: '#8ab4d4',
                    formatter: (value: number) => Number(value).toExponential(2),
                },
                axisLine: { lineStyle: { color: '#1e3a5f' } },
                splitLine: { lineStyle: { color: 'rgba(30,58,95,0.5)' } },
            },
            grid: { left: 60, right: 20, top: 30, bottom: 70 },
            dataZoom: [
                {
                    type: 'inside',
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    filterMode: 'none',
                },
                {
                    type: 'slider',
                    xAxisIndex: 0,
                    filterMode: 'none',
                    height: 14,
                    bottom: 18,
                    borderColor: '#1e3a5f',
                    fillerColor: 'rgba(0, 200, 255, 0.2)',
                    textStyle: { color: '#8ab4d4' },
                },
                {
                    type: 'slider',
                    yAxisIndex: 0,
                    filterMode: 'none',
                    width: 14,
                    right: 4,
                    borderColor: '#1e3a5f',
                    fillerColor: 'rgba(0, 200, 255, 0.2)',
                    textStyle: { color: '#8ab4d4' },
                },
            ],
            series: [
                {
                    type: 'scatter',
                    data: points,
                    symbolSize: 10,
                    itemStyle: { color: '#ee6666' },
                    emphasis: { itemStyle: { color: '#ff9f43' } },
                },
            ],
        }
    } finally {
        loading.value.boreholeLocation = false
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

function onBoreholeLocationClick(params: any) {
    if (!params?.data?.id) return
    analysisStore.setActiveLinkItem({ type: 'borehole', value: params.name })
    sceneStore.locateTo({ type: 'borehole', id: String(params.data.id), name: params.name })
    router.push('/dashboard')
    ElMessage.success(`已定位到钻孔: ${params.name}`)
}

onMounted(() => {
    loadThickness()
    loadDepth()
    loadBoreholeLocation()
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
    min-height: 0;
}

.chart-card-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin-bottom: 8px;
    flex-shrink: 0;
}

.chart-body {
    flex: 1;
    min-height: 0;
}

.chart-body :deep(.stats-chart) {
    height: 100%;
}
</style>
