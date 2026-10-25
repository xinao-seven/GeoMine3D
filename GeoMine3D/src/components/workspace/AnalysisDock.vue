<template>
    <section class="analysis-dock">
        <nav class="dock-tabs">
            <button v-for="item in tabs" :key="item.id" :class="{ active: activeDock === item.id }"
                @click="store.openDock(item.id)">
                <el-icon>
                    <component :is="item.icon" />
                </el-icon>{{ item.label }}
            </button>
            <button class="dock-close" title="收起" @click="store.toggleBottom"><el-icon>
                    <ArrowDown />
                </el-icon></button>
        </nav>
        <div class="dock-content">
            <template v-if="activeDock === 'overview'">
                <div class="metric"><span>SCENE OBJECTS</span><strong>{{ objectCount }}</strong><small>已登记对象</small>
                </div>
                <div class="metric"><span>ACTIVE LAYERS</span><strong>{{ activeLayerCount }}</strong><small>可见图层</small>
                </div>
                <div class="metric"><span>MEASUREMENTS</span><strong>{{ measurements.length
                        }}</strong><small>测量记录</small></div>
                <div class="analysis-summary" v-if="overview">
                    <div class="summary-row">
                        <div class="summary-cell"><b>{{ overview.borehole_count }}</b><small>钻孔</small></div>
                        <div class="summary-cell"><b>{{ overview.strata_layer_count }}</b><small>地层单元</small></div>
                        <div class="summary-cell"><b>{{ formatMeters(overview.total_drilling_depth) }}</b><small>总进尺/m</small>
                        </div>
                        <div class="summary-cell"><b>{{ overview.model_count }}</b><small>模型</small></div>
                        <div class="summary-cell"><b>{{ overview.workingface_count }}</b><small>工作面</small></div>
                        <div class="summary-cell"><b>{{ overview.max_borehole_depth }}</b><small>最大孔深/m</small></div>
                    </div>
                    <div ref="thicknessChartRef" class="thickness-chart"></div>
                </div>
                <div class="dock-empty analysis-empty" v-else>
                    {{ analysisLoading ? '统计数据加载中...' : (isLocal ? '本地演示模式无统计数据' : '暂无统计数据') }}
                </div>
            </template>
            <template v-else-if="activeDock === 'borehole'">
                <div v-if="currentDetail" class="borehole-workbench">
                    <aside class="borehole-brief">
                        <span>SELECTED BOREHOLE</span><strong>{{ currentDetail.name }}</strong>
                        <div><b>{{ currentDetail.totalDepth.toFixed(2) }}</b><small>总深度 / m</small></div>
                        <div><b>{{ currentDetail.layers.length }}</b><small>地层数量</small></div>
                        <small class="borehole-hint">点击柱状图地层可在三维中定位</small>
                    </aside>
                    <BoreholeChart :borehole="currentDetail" class="borehole-chart" @layer-click="onLayerClick" />
                </div>
                <div v-else class="dock-empty">选择一个钻孔后显示地层柱状图</div>
            </template>
            <template v-else-if="activeDock === 'table'">
                <div class="data-table-head"><span>对象名称</span><span>类型</span><span>状态</span></div>
                <div class="data-row" v-if="selectedObject"><span>{{ selectedObject.name }}</span><span>{{
                    selectedObject.type }}</span><span>SELECTED</span></div>
                <div class="dock-empty" v-else>场景对象属性表将在加载数据后显示</div>
            </template>
            <template v-else-if="activeDock === 'records'">
                <div class="records-panel">
                    <div class="records-column">
                        <div class="records-head">
                            <span>测量记录（{{ measurements.length }}）</span>
                            <button :disabled="!measurements.length" @click="exportMeasurementsCsv">导出 CSV</button>
                        </div>
                        <div class="records-body">
                            <div v-for="(item, index) in measurements" :key="item.id" class="record-row">
                                <b>{{ index + 1 }}</b>
                                <span class="record-main">{{ item.distance.toFixed(2) }} m</span>
                                <small>{{ formatCoord(item.start) }} → {{ formatCoord(item.end) }}</small>
                                <button class="record-del" title="删除" @click="sceneStore.requestRemoveMeasurement(item.id)">×</button>
                            </div>
                            <div v-if="!measurements.length" class="records-empty">暂无测量记录</div>
                        </div>
                    </div>
                    <div class="records-column">
                        <div class="records-head">
                            <span>空间标注（{{ annotations.length }}）<i v-if="!isProjectMode" class="local-tag">会话内</i></span>
                            <button :disabled="!annotations.length" @click="exportAnnotationsCsv">导出 CSV</button>
                        </div>
                        <div class="records-body">
                            <div v-for="item in annotations" :key="item.id" class="record-row">
                                <b>{{ item.serverId ? '云' : '本' }}</b>
                                <span class="record-main">{{ item.text }}</span>
                                <small>{{ formatCoord(item.position) }}</small>
                                <button class="record-del" title="删除" @click="sceneStore.requestRemoveAnnotation(item.id)">×</button>
                            </div>
                            <div v-if="!annotations.length" class="records-empty">暂无标注（项目模式下自动保存）</div>
                        </div>
                    </div>
                </div>
            </template>
            <template v-else-if="activeDock === 'volume'">
                <div class="volume-panel">
                    <div class="records-column">
                        <div class="records-head">
                            <span>分层模型体积（世界体积 ÷ 竖向{{ verticalScale }}×）</span>
                            <button :disabled="volumeComputing" @click="sceneStore.requestVolumeStats()">
                                {{ volumeComputing ? '计算中...' : (stratumVolumes.length ? '重算' : '计算') }}
                            </button>
                        </div>
                        <div class="records-body">
                            <div class="data-table-head volume-head"><span>地层</span><span>体积 m³</span><span>三角面</span></div>
                            <div v-for="item in stratumVolumes" :key="item.layerName" class="record-row volume-row">
                                <span class="record-main">{{ item.layerName }}</span>
                                <small>{{ item.volumeM3.toLocaleString() }}</small>
                                <small>{{ compactNumber(item.triangles) }}</small>
                            </div>
                            <div v-if="!stratumVolumes.length && !volumeComputing" class="records-empty">
                                尚未计算——加载地层模型后点击“计算”
                            </div>
                        </div>
                    </div>
                    <div class="records-column">
                        <div class="records-head">
                            <span>工作面煤炭资源量估算<span class="local-tag" v-if="isLocal">本地无</span></span>
                            <button :disabled="reservesLoading || isLocal" @click="loadReserves">
                                {{ reservesLoading ? '估算中...' : (reserves ? '刷新' : '开始估算') }}
                            </button>
                        </div>
                        <div class="records-body">
                            <template v-if="reserves">
                                <div class="data-table-head volume-head reserve-head">
                                    <span>工作面</span><span>面积㎡</span><span>孔数</span><span>煤厚m</span><span>资源量万t</span>
                                </div>
                                <div v-for="item in reserves.items" :key="item.name" class="record-row reserve-row">
                                    <span class="record-main">{{ item.name }}</span>
                                    <small>{{ compactNumber(item.area_m2) }}</small>
                                    <small>{{ item.borehole_count }}</small>
                                    <small>{{ item.mean_coal_thickness_m ?? '—' }}</small>
                                    <small class="reserve-value">{{ item.reserve_wan_t ?? '—' }}</small>
                                </div>
                                <div class="reserve-total">
                                    合计资源量 <b>{{ reserves.total_reserve_wan_t.toLocaleString() }}</b> 万吨
                                    · 密度 {{ reserves.density_t_m3 }} t/m³ · {{ reserves.face_count }} 个圈闭
                                </div>
                            </template>
                            <div v-else-if="!reservesLoading" class="records-empty">
                                {{ isLocal ? '本地演示模式无储量数据' : '基于工作面圈闭(SHP)与圈闭内钻孔煤层厚度估算' }}
                            </div>
                        </div>
                    </div>
                </div>
            </template>
            <template v-else>
                <div class="metric"><span>FPS</span><strong>{{ performance.fps }}</strong><small>500ms 滑动窗口</small>
                </div>
                <div class="metric"><span>DRAW CALLS</span><strong>{{ performance.calls
                        }}</strong><small>renderer.info</small></div>
                <div class="metric"><span>TRIANGLES</span><strong>{{ compactNumber(performance.triangles)
                        }}</strong><small>当前帧</small></div>
                <div class="performance-note">GPU 资源：{{ performance.geometries }} geometries / {{ performance.textures
                    }} textures</div>
            </template>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import BoreholeChart from '@/components/workspace/BoreholeChart.vue'
import { workspaceApi, type AnalysisOverview } from '@/api/workspace'
import { useBoreholeStore, useSceneStore, useWorkspaceStore } from '@/stores'
import type { WorkspaceDock } from '@/stores/workspaceStore'
const store = useWorkspaceStore(); const sceneStore = useSceneStore(); const boreholeStore = useBoreholeStore()
const route = useRoute()
const { activeDock, performance } = storeToRefs(store); const { selectedObject, layerVisible, measurements, modelLoadStatus, annotations, coordinateOrigin, verticalScale, stratumVolumes, volumeComputing } = storeToRefs(sceneStore); const { currentDetail } = storeToRefs(boreholeStore)
const tabs: Array<{ id: WorkspaceDock; label: string; icon: string }> = [{ id: 'overview', label: '场景概览', icon: 'DataAnalysis' }, { id: 'borehole', label: '钻孔柱状图', icon: 'Histogram' }, { id: 'records', label: '测量与标注', icon: 'List' }, { id: 'volume', label: '体积与储量', icon: 'Box' }, { id: 'table', label: '属性表', icon: 'Grid' }, { id: 'performance', label: '性能', icon: 'Odometer' }]
const activeLayerCount = computed(() => Object.values(layerVisible.value).filter(Boolean).length)
const objectCount = computed(() => Object.values(modelLoadStatus.value).filter(item => item.loaded).length)
const isLocal = computed(() => String(route.params.projectId) === 'local')
const isProjectMode = computed(() => !isLocal.value)
function compactNumber(value: number) { return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value) }
function formatMeters(value: number) {
    return value >= 10000 ? compactNumber(value) : String(Math.round(value))
}

// ==================== 项目统计概览 ====================
const overview = ref<AnalysisOverview | null>(null)
const analysisLoading = ref(false)
const thicknessChartRef = ref<HTMLDivElement>()
let thicknessChart: echarts.ECharts | null = null

async function loadOverview() {
    if (isLocal.value || overview.value || analysisLoading.value) return
    analysisLoading.value = true
    try {
        overview.value = await workspaceApi.getAnalysisOverview(String(route.params.projectId))
        renderThicknessChart()
    } catch { /* 统计加载失败不打断场景使用 */ }
    finally { analysisLoading.value = false }
}

function renderThicknessChart() {
    if (!thicknessChartRef.value || !overview.value) return
    if (!thicknessChart) thicknessChart = echarts.init(thicknessChartRef.value)
    const stats = overview.value.thickness_distribution.slice(0, 16)
    thicknessChart.setOption({
        backgroundColor: 'transparent',
        grid: { left: 8, right: 8, top: 22, bottom: 38, containLabel: true },
        tooltip: {
            trigger: 'axis',
            formatter: (params: any) => {
                const s = params[0]?.data
                if (!s) return ''
                const stat = stats[s.dataIndex]
                return `<b>${stat.layer_name}</b><br/>平均厚度 ${stat.avg_thickness} m<br/>范围 ${stat.min_thickness}~${stat.max_thickness} m<br/>统计段数 ${stat.count}`
            },
        },
        xAxis: {
            type: 'category',
            data: stats.map(item => item.layer_name),
            axisLabel: { color: '#8b948c', fontSize: 9, interval: 0, rotate: 38 },
            axisLine: { lineStyle: { color: '#333b34' } },
        },
        yAxis: {
            type: 'value',
            name: '平均厚度 m',
            nameTextStyle: { color: '#667068', fontSize: 9 },
            axisLabel: { color: '#77807a', fontSize: 9 },
            splitLine: { lineStyle: { color: '#232824' } },
        },
        series: [{
            type: 'bar',
            barMaxWidth: 22,
            itemStyle: { color: '#7c9c72', opacity: 0.85 },
            data: stats.map((item, dataIndex) => ({ value: item.avg_thickness, dataIndex })),
        }],
    }, true)
}

watch(activeDock, (dock) => {
    if (dock === 'overview') {
        void loadOverview()
        // 从其它页签切回时图表容器刚重新显示，需要 resize
        requestAnimationFrame(() => thicknessChart?.resize())
    }
})

function onLayerClick(layerName: string) {
    sceneStore.requestFocusStratum(layerName)
}

// ==================== 测量/标注管理 ====================

/** 世界坐标 → 真实投影坐标（与 SceneCanvas 同一换算），无原点时按原值输出 */
function toProjectCoords(point: { x: number; y: number; z: number }) {
    const origin = coordinateOrigin.value
    if (!origin) return point
    return {
        x: origin.x + point.x,
        y: origin.y - point.z,
        z: origin.z + point.y / verticalScale.value,
    }
}

function formatCoord(point: { x: number; y: number; z: number }) {
    const projected = toProjectCoords(point)
    return `${projected.x.toFixed(1)}, ${projected.y.toFixed(1)}, ${projected.z === undefined ? '—' : projected.z.toFixed(1)}`
}

function downloadCsv(filename: string, rows: string[][]) {
    const csv = '\uFEFF' + rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\r\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    link.click()
    URL.revokeObjectURL(link.href)
}

function exportMeasurementsCsv() {
    const rows: string[][] = [['序号', '距离m', '起点X', '起点Y', '起点Z', '终点X', '终点Y', '终点Z']]
    measurements.value.forEach((item, index) => {
        const start = toProjectCoords(item.start)
        const end = toProjectCoords(item.end)
        rows.push([
            String(index + 1), item.distance.toFixed(2),
            start.x.toFixed(2), start.y.toFixed(2), (start.z ?? 0).toFixed(2),
            end.x.toFixed(2), end.y.toFixed(2), (end.z ?? 0).toFixed(2),
        ])
    })
    downloadCsv(`geomine-measurements-${Date.now()}.csv`, rows)
}

function exportAnnotationsCsv() {
    const rows: string[][] = [['序号', '内容', 'X', 'Y', '高程Z', '持久化']]
    annotations.value.forEach((item, index) => {
        const projected = toProjectCoords(item.position)
        rows.push([
            String(index + 1), item.text,
            projected.x.toFixed(2), projected.y.toFixed(2), (projected.z ?? 0).toFixed(2),
            item.serverId ? '是' : '否',
        ])
    })
    downloadCsv(`geomine-annotations-${Date.now()}.csv`, rows)
}

// ==================== 体积与储量 ====================

const reserves = ref<import('@/api/workspace').ReservesResponse | null>(null)
const reservesLoading = ref(false)
let reservesRequested = false

async function loadReserves() {
    if (isLocal.value || reservesLoading.value) return
    reservesLoading.value = true
    try {
        reserves.value = await workspaceApi.getReserves(String(route.params.projectId))
    } catch {
        reserves.value = null
    } finally {
        reservesLoading.value = false
    }
}

watch(activeDock, (dock) => {
    if (dock === 'volume') {
        if (!stratumVolumes.value.length && !volumeComputing.value) {
            sceneStore.requestVolumeStats()
        }
        if (!reservesRequested && !isLocal.value) {
            reservesRequested = true
            void loadReserves()
        }
        requestAnimationFrame(() => thicknessChart?.resize())
    }
})

let chartResizeObserver: ResizeObserver | null = null
onMounted(() => {
    if (activeDock.value === 'overview') void loadOverview()
    if (thicknessChartRef.value) {
        chartResizeObserver = new ResizeObserver(() => thicknessChart?.resize())
        chartResizeObserver.observe(thicknessChartRef.value)
    }
})

onUnmounted(() => {
    chartResizeObserver?.disconnect()
    thicknessChart?.dispose()
    thicknessChart = null
})
</script>

<style scoped>
.analysis-dock {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #101411;
    border-top: 1px solid var(--studio-border)
}

.dock-tabs {
    height: 36px;
    display: flex;
    border-bottom: 1px solid var(--studio-border);
    padding-left: 8px
}

.dock-tabs button {
    height: 36px;
    padding: 0 14px;
    border: 0;
    border-right: 1px solid #282e29;
    background: transparent;
    color: #707970;
    font-size: 10px;
    display: flex;
    gap: 7px;
    align-items: center;
    cursor: pointer
}

.dock-tabs button.active {
    color: #dfd9ca;
    background: #1a201b;
    box-shadow: inset 0 2px var(--studio-copper)
}

.dock-tabs .dock-close {
    margin-left: auto;
    border-left: 1px solid #282e29
}

.dock-content {
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: stretch;
    padding: 10px 16px;
    gap: 12px;
    overflow: hidden
}

.metric {
    width: 180px;
    padding: 13px 15px;
    border-left: 2px solid #735431;
    background: #151a16;
    display: flex;
    flex-direction: column
}

.metric span {
    font: 9px Bahnschrift;
    letter-spacing: .12em;
    color: #667068
}

.metric strong {
    font: 28px Bahnschrift;
    color: #d8d6cc;
    margin: 4px 0
}

.metric small {
    color: #5e665f;
    font-size: 9px
}

.analysis-summary {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border-left: 2px solid #4f6658;
    background: #151a16
}

.summary-row {
    display: flex;
    gap: 8px
}

.summary-cell {
    flex: 1;
    text-align: center;
    padding: 4px 2px;
    background: #1a201b
}

.summary-cell b {
    display: block;
    color: #c8b489;
    font: 16px Bahnschrift
}

.summary-cell small {
    color: #5e665f;
    font-size: 8px
}

.thickness-chart {
    flex: 1;
    min-height: 0
}

.analysis-empty {
    flex: 1;
    border: 1px dashed #313832
}

.borehole-hint {
    margin-top: 8px;
    color: #6d766e;
    font-size: 8px
}

.borehole-workbench {
    width: min(760px, 100%);
    height: 100%;
    display: grid;
    grid-template-columns: 170px minmax(300px, 520px);
    gap: 14px;
    margin: 0 auto
}

.borehole-brief {
    padding: 12px;
    border-left: 2px solid #80603a;
    background: #151a16;
    display: flex;
    flex-direction: column
}

.borehole-brief>span {
    color: #6d766e;
    font: 8px Bahnschrift;
    letter-spacing: .13em
}

.borehole-brief>strong {
    margin: 5px 0 10px;
    color: #d6d3c9;
    font-size: 15px
}

.borehole-brief>div {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 7px 0;
    border-top: 1px solid #2b312c
}

.borehole-brief b {
    color: #bd8950;
    font: 17px Bahnschrift
}

.borehole-brief small {
    color: #656e67;
    font-size: 8px
}

.borehole-chart {
    min-width: 0;
    width: 100%;
    height: 100%;
    min-height: 0;
    background: #131815;
    border: 1px solid #29302a
}

.dock-empty,
.performance-note {
    margin: auto;
    color: #677068;
    font-size: 11px
}

/* ── 测量与标注管理 ── */
.records-panel {
    flex: 1;
    min-width: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px
}

.records-column {
    min-width: 0;
    display: flex;
    flex-direction: column;
    border-left: 2px solid #4f6658;
    background: #151a16
}

.records-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    border-bottom: 1px solid #2b312c
}

.records-head span {
    color: #a9b2a9;
    font-size: 11px
}

.local-tag {
    margin-left: 6px;
    padding: 1px 5px;
    font-size: 8px;
    font-style: normal;
    color: #b98548;
    border: 1px solid #5a4a2c
}

.records-head button {
    border: 1px solid #37403a;
    background: #1a201b;
    color: #9fb5a2;
    font-size: 10px;
    padding: 3px 8px;
    cursor: pointer
}

.records-head button:disabled {
    opacity: .4;
    cursor: not-allowed
}

.records-body {
    flex: 1;
    overflow: auto;
    padding: 4px 0
}

.record-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px;
    font-size: 10px;
    color: #b9beb7
}

.record-row b {
    flex-shrink: 0;
    width: 18px;
    height: 18px;
    display: grid;
    place-items: center;
    background: #222a23;
    color: #93a093;
    font-size: 9px
}

.record-main {
    flex-shrink: 0;
    color: #d8d6cc;
    max-width: 45%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap
}

.record-row small {
    flex: 1;
    color: #6c756d;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: Consolas, monospace
}

.record-del {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    border: 1px solid #3a423b;
    background: transparent;
    color: #8d968d;
    cursor: pointer
}

.record-del:hover {
    color: #e08a7a;
    border-color: #6b423a
}

.records-empty {
    padding: 18px 10px;
    text-align: center;
    color: #677068;
    font-size: 10px
}

/* ── 体积与储量 ── */
.volume-panel {
    flex: 1;
    min-width: 0;
    display: grid;
    grid-template-columns: 1fr 1.2fr;
    gap: 12px
}

.volume-head {
    border-bottom: 1px solid #2b312c;
    color: #646d65
}

.volume-row,
.reserve-row {
    font-family: Consolas, monospace
}

.volume-row small,
.reserve-row small {
    flex: 1;
    text-align: right;
    color: #9aa39b
}

.volume-row span.record-main,
.reserve-row span.record-main {
    flex: 2
}

.reserve-value {
    color: #c8b489
}

.reserve-total {
    padding: 8px 10px;
    border-top: 1px solid #2b312c;
    color: #a9b2a9;
    font-size: 10px
}

.reserve-total b {
    color: #c8b489;
    font-family: Bahnschrift
}

.data-table-head,
.data-row {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr;
    width: 100%;
    padding: 8px 12px;
    font-size: 10px
}

.data-table-head {
    color: #646d65;
    border-bottom: 1px solid #2b312c
}

.data-row {
    color: #b9beb7;
    background: #151a16
}

.performance-note {
    margin: 0;
    flex: 1;
    display: grid;
    place-items: center;
    border: 1px dashed #313832
}
</style>
