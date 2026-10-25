<template>
    <main class="geo-workspace" @keydown.ctrl.k.prevent="workspace.commandPaletteVisible = true">
        <header class="workspace-header">
            <button class="brand-button" @click="router.push('/projects')"><span
                    class="brand-glyph">G</span><b>GEOMINE</b></button>
            <div class="project-identity"><span>ACTIVE PROJECT</span><strong>{{ projectName }}</strong></div>
            <button class="command-trigger" @click="workspace.commandPaletteVisible = true"><el-icon>
                    <Search />
                </el-icon><span>搜索对象或执行命令</span><kbd>Ctrl K</kbd></button>
            <div class="header-tools">
                <button title="左侧面板" :class="{ active: leftVisible }" @click="workspace.toggleLeft"><el-icon>
                        <Tickets />
                    </el-icon></button>
                <button title="分析面板" :class="{ active: bottomVisible }" @click="workspace.toggleBottom"><el-icon>
                        <DataAnalysis />
                    </el-icon></button>
                <button title="属性面板" :class="{ active: rightVisible }" @click="workspace.toggleRight"><el-icon>
                        <Operation />
                    </el-icon></button>
                <span class="tool-divider"></span>
                <button title="保存场景 / 视角书签" @click="openSceneManager"><el-icon>
                        <Collection />
                    </el-icon></button>
                <button class="export-button" @click="takeSnapshot"><el-icon>
                        <Camera />
                    </el-icon> 快照</button>
            </div>
        </header>

        <section class="workspace-grid"
            :class="{ 'no-left': !leftVisible, 'no-right': !rightVisible, 'no-bottom': !bottomVisible }">
            <ResourceExplorer v-if="leftVisible" class="left-dock" />
            <div class="viewport-shell">
                <div class="viewport-ruler top-ruler"></div>
                <div class="viewport-ruler left-ruler"></div>
                <SceneCanvas ref="sceneCanvasRef" />
                <div class="viewport-badge"><i></i> WEBGL / PERSPECTIVE</div>
            </div>
            <InspectorPanel v-if="rightVisible" class="right-dock" />
            <AnalysisDock v-if="bottomVisible" class="bottom-dock" />
        </section>

        <footer class="status-bar">
            <span><i class="online"></i> ENGINE READY</span><span>CRS {{ project?.coordinate_system || 'LOCAL' }}</span>
            <span class="cursor-coords">{{ cursorText }}</span><span class="status-spacer"></span><span>FPS {{ performance.fps
                }}</span><span>CALLS {{ performance.calls }}</span><span>TRI {{ compactNumber(performance.triangles)
                }}</span>
        </footer>

        <el-dialog v-model="sceneDialogVisible" title="场景管理" width="500px" class="scene-dialog" append-to-body>
            <div class="scene-save-row">
                <el-input v-model="sceneName" placeholder="场景名称，例如：3号勘探线视角" maxlength="60"
                    @keyup.enter="saveScene" />
                <el-button type="primary" :loading="sceneSaving" :disabled="isLocal" @click="saveScene">保存当前视角</el-button>
            </div>
            <p v-if="isLocal" class="scene-hint">本地演示模式不连接数据服务，无法保存场景；视角仍可在会话内切换。</p>
            <div class="scene-list">
                <div v-for="item in scenes" :key="item.id" class="scene-item">
                    <div class="scene-item-info">
                        <strong>{{ item.name }}</strong>
                        <small>{{ formatSceneTime(item.updated_at) }}</small>
                    </div>
                    <div class="scene-item-actions">
                        <el-button size="small" @click="applyScene(item)">载入</el-button>
                        <el-button size="small" type="danger" plain @click="removeScene(item)">删除</el-button>
                    </div>
                </div>
                <div v-if="!scenes.length" class="scene-hint">暂无已保存场景</div>
            </div>
        </el-dialog>

        <el-dialog v-model="workspace.sectionDialogVisible" title="勘探线剖面图（沿线钻孔投影）" width="min(1100px, 94vw)"
            append-to-body class="section-dialog" @opened="renderSectionChart" @closed="disposeSectionChart">
            <div class="section-toolbar">
                <span class="section-meta">{{ sectionMetaText }}</span>
                <el-button size="small" :disabled="!boreholesInSection.length" @click="exportSectionChart">导出 PNG</el-button>
            </div>
            <div ref="sectionChartRef" class="section-chart"></div>
            <p v-if="!boreholesInSection.length" class="section-empty">
                剖面线走廊（±300m）内没有已加载分层数据的钻孔——请先在左侧资源面板加载钻孔。
            </p>
        </el-dialog>

        <el-dialog v-model="workspace.commandPaletteVisible" width="560px" :show-close="false" class="command-dialog">
            <el-input v-model="command" size="large" placeholder="输入命令，例如“启用剖切”" @keyup.enter="executeCommand"><template
                    #prefix><el-icon>
                        <Search />
                    </el-icon></template></el-input>
            <div class="command-list">
                <button v-for="item in filteredCommands" :key="item.name" @click="runCommand(item)"><el-icon>
                        <component :is="item.icon" />
                    </el-icon><span>{{ item.name }}</span><kbd>{{ item.shortcut }}</kbd></button>
            </div>
        </el-dialog>
    </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import SceneCanvas from '@/components/three/SceneCanvas.vue'
import ResourceExplorer from '@/components/workspace/ResourceExplorer.vue'
import InspectorPanel from '@/components/workspace/InspectorPanel.vue'
import AnalysisDock from '@/components/workspace/AnalysisDock.vue'
import { workspaceApi, type ProjectRecord, type SceneRecord } from '@/api/workspace'
import { useSceneStore, useWorkspaceStore, useBoreholeStore } from '@/stores'
import type { SceneSnapshot } from '@/stores/sceneStore'
import { boreholeLayerColor } from '@/constants/strataColors'
import type { BoreholeLayer } from '@/types'

const route = useRoute(); const router = useRouter(); const workspace = useWorkspaceStore(); const sceneStore = useSceneStore(); const boreholeStore = useBoreholeStore()
const { leftVisible, rightVisible, bottomVisible, performance, cursorCoordinate } = storeToRefs(workspace); const project = ref<ProjectRecord | null>(null); const command = ref('')
const projectName = computed(() => project.value?.name || (route.params.projectId === 'local' ? '本地演示工作区' : '三维地质项目'))
const isLocal = computed(() => String(route.params.projectId) === 'local')
const commands = [
    { name: '启用三轴剖切', icon: 'Crop', shortcut: 'C', run: () => sceneStore.activateTool('clip') },
    { name: '开始距离测量', icon: 'ScaleToOriginal', shortcut: 'M', run: () => sceneStore.activateTool('measure') },
    { name: '创建空间标注', icon: 'Location', shortcut: 'A', run: () => sceneStore.activateTool('annotation') },
    { name: '退出当前工具', icon: 'Close', shortcut: 'Esc', run: () => sceneStore.activateTool(null) },
    { name: '打开性能面板', icon: 'Odometer', shortcut: '', run: () => workspace.openDock('performance') },
]
const filteredCommands = computed(() => commands.filter(item => item.name.includes(command.value.trim())))
function runCommand(item: typeof commands[number]) { item.run(); workspace.commandPaletteVisible = false; command.value = '' }
function executeCommand() { if (filteredCommands.value[0]) runCommand(filteredCommands.value[0]) }
function compactNumber(value: number) { return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value) }

// ==================== 快照与场景管理 ====================

const sceneCanvasRef = ref<InstanceType<typeof SceneCanvas> | null>(null)
const sceneDialogVisible = ref(false)
const sceneName = ref('')
const sceneSaving = ref(false)
const scenes = ref<SceneRecord[]>([])

const cursorText = computed(() => {
    const c = cursorCoordinate.value
    if (!c) return 'X —   Y —   高程 —'
    const zText = c.z === null ? '—' : c.z.toFixed(2)
    return `X ${c.x.toFixed(2)}   Y ${c.y.toFixed(2)}   高程 ${zText}`
})

function takeSnapshot() {
    const dataUrl = sceneCanvasRef.value?.captureImage()
    if (!dataUrl) {
        ElMessage.warning('场景尚未就绪，无法截图')
        return
    }
    const link = document.createElement('a')
    link.href = dataUrl
    link.download = `geomine-snapshot-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.png`
    link.click()
    ElMessage.success('快照已导出为 PNG')
}

async function openSceneManager() {
    sceneDialogVisible.value = true
    if (isLocal.value) return
    try {
        scenes.value = await workspaceApi.listScenes(String(route.params.projectId))
    } catch { /* 列表加载失败时保留空态 */ }
}

function buildScenePayload(name: string) {
    const state = sceneCanvasRef.value?.getSceneState()
    return {
        name,
        camera_json: state?.camera ?? {},
        layers_json: state?.layers ?? [],
        clipping_json: state?.clip ?? {},
        explode_json: state?.explode ?? {},
        render_settings_json: { verticalScale: state?.verticalScale, showEdges: state?.showEdges },
    }
}

async function saveScene() {
    const name = sceneName.value.trim()
    if (!name) {
        ElMessage.warning('请输入场景名称')
        return
    }
    if (isLocal.value || !sceneCanvasRef.value) return
    sceneSaving.value = true
    try {
        const existing = scenes.value.find(item => item.name === name)
        if (existing) {
            const updated = await workspaceApi.updateScene(existing.id, buildScenePayload(name))
            const index = scenes.value.findIndex(item => item.id === existing.id)
            if (index >= 0 && updated) scenes.value[index] = updated
            ElMessage.success(`场景「${name}」已更新`)
        } else {
            const created = await workspaceApi.createScene(String(route.params.projectId), buildScenePayload(name))
            if (created) scenes.value.unshift(created)
            ElMessage.success(`场景「${name}」已保存`)
        }
        sceneName.value = ''
    } catch {
        ElMessage.error('场景保存失败')
    } finally {
        sceneSaving.value = false
    }
}

function sceneToSnapshot(record: SceneRecord): SceneSnapshot {
    return {
        camera: (record.camera_json || {}) as SceneSnapshot['camera'],
        layers: (record.layers_json || []) as SceneSnapshot['layers'],
        showEdges: record.render_settings_json?.showEdges,
        verticalScale: record.render_settings_json?.verticalScale,
        clip: (record.clipping_json || {}) as SceneSnapshot['clip'],
        explode: (record.explode_json || {}) as SceneSnapshot['explode'],
    }
}

function applyScene(item: SceneRecord) {
    sceneCanvasRef.value?.applySceneState(sceneToSnapshot(item))
    sceneDialogVisible.value = false
    ElMessage.success(`已载入场景「${item.name}」`)
}

async function removeScene(item: SceneRecord) {
    try {
        await workspaceApi.deleteScene(item.id)
        scenes.value = scenes.value.filter(s => s.id !== item.id)
    } catch {
        ElMessage.error('场景删除失败')
    }
}

function formatSceneTime(value: string) {
    return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

// ==================== 勘探线剖面图 ====================

const SECTION_CORRIDOR_M = 300

interface SectionHole {
    name: string
    s: number
    t: number
    layers: BoreholeLayer[]
}

const sectionChartRef = ref<HTMLDivElement>()
let sectionChart: import('echarts').ECharts | null = null
const boreholesInSection = ref<SectionHole[]>([])

const sectionMetaText = computed(() => {
    const a = sceneStore.sectionState.pointA
    const b = sceneStore.sectionState.pointB
    if (!a || !b) return '剖面线未定义'
    const length = Math.hypot(b.x - a.x, b.y - a.y)
    const bearing = (Math.atan2(b.x - a.x, b.y - a.y) * 180 / Math.PI + 360) % 360
    return `方位角 ${bearing.toFixed(1)}° · 长度 ${length.toFixed(0)} m · 沿线钻孔 ${boreholesInSection.value.length} 个（走廊 ±${SECTION_CORRIDOR_M}m）`
})

/** 把剖面线走廊内的钻孔投影到剖面线坐标系（s=沿线距离, t=偏距） */
function computeSectionHoles(): SectionHole[] {
    const a = sceneStore.sectionState.pointA
    const b = sceneStore.sectionState.pointB
    if (!a || !b) return []
    const dx = b.x - a.x
    const dy = b.y - a.y
    const length = Math.hypot(dx, dy)
    if (length < 1) return []
    const ux = dx / length
    const uy = dy / length
    const holes: SectionHole[] = []
    for (const item of boreholeStore.list) {
        if (!item.location || !item.layers?.length) continue
        const vx = item.location.x - a.x
        const vy = item.location.y - a.y
        const s = vx * ux + vy * uy
        if (s < -50 || s > length + 50) continue
        const t = Math.abs(vx * uy - vy * ux)
        if (t > SECTION_CORRIDOR_M) continue
        holes.push({ name: item.name, s, t, layers: item.layers })
    }
    holes.sort((x, y) => x.s - y.s)
    return holes
}

function buildSectionOption(holes: SectionHole[]) {
    const maxDepth = Math.max(1, ...holes.flatMap(hole => hole.layers.map(layer => layer.bottomDepth)))
    // 柱宽取相邻孔距中位数的 45%，夹在 8~40
    const gaps: number[] = []
    for (let i = 1; i < holes.length; i += 1) gaps.push(holes[i].s - holes[i - 1].s)
    gaps.sort((x, y) => x - y)
    const medianGap = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 120
    const barWidth = Math.min(40, Math.max(8, medianGap * 0.45))

    const data = holes.flatMap((hole, holeIndex) =>
        hole.layers.map((layer, layerIndex) => ({
            value: [hole.s, layer.topDepth],
            holeIndex,
            layerIndex,
            layer,
        }))
    )

    return {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'item',
            formatter: (params: any) => {
                const d = params.data
                const layer = d?.layer
                const hole = holes[d?.holeIndex]
                if (!layer || !hole) return ''
                return `<b>${hole.name}</b><br/>${layer.layerName}<br/>顶深 ${layer.topDepth} m · 底深 ${layer.bottomDepth} m<br/>偏距 ${hole.t.toFixed(0)} m`
            },
        },
        grid: { left: 56, right: 24, top: 30, bottom: 34 },
        xAxis: {
            type: 'value',
            name: '沿线距离 m',
            nameTextStyle: { color: '#77807a', fontSize: 10 },
            min: 0,
            max: Math.ceil(Math.max(1, holes.length ? holes[holes.length - 1].s : 1)),
            axisLabel: { color: '#8b948c', fontSize: 10 },
            splitLine: { lineStyle: { color: '#1f251f' } },
        },
        yAxis: {
            type: 'value',
            inverse: true,
            name: '深度 m',
            nameTextStyle: { color: '#77807a', fontSize: 10 },
            max: Math.ceil(maxDepth * 1.05),
            axisLabel: { color: '#8b948c', fontSize: 10 },
            splitLine: { lineStyle: { color: '#1f251f' } },
        },
        series: [
            {
                type: 'custom',
                renderItem: (params: any, api: any) => {
                    const d = params.data
                    const hole = holes[d.holeIndex]
                    const layer = d.layer
                    const x0 = api.coord([hole.s - barWidth / 2, layer.topDepth])
                    const x1 = api.coord([hole.s + barWidth / 2, layer.topDepth])
                    const y1 = api.coord([hole.s, layer.bottomDepth])
                    return {
                        type: 'rect',
                        shape: {
                            x: x0[0],
                            y: x0[1],
                            width: Math.max(2, x1[0] - x0[0]),
                            height: Math.max(1, y1[1] - x0[1]),
                        },
                        style: {
                            fill: boreholeLayerColor(layer.color, d.layerIndex),
                            opacity: 0.92,
                            stroke: 'rgba(255,255,255,0.25)',
                            lineWidth: 0.5,
                        },
                    }
                },
                data,
                encode: { x: 0, y: 1 },
                clip: true,
            },
        ],
    }
}

async function renderSectionChart() {
    boreholesInSection.value = computeSectionHoles()
    if (!sectionChartRef.value) return
    const echarts = await import('echarts')
    if (!sectionChartRef.value) return
    if (!sectionChart) sectionChart = echarts.init(sectionChartRef.value)
    if (!boreholesInSection.value.length) {
        sectionChart.clear()
        return
    }
    sectionChart.setOption(buildSectionOption(boreholesInSection.value), true)
}

function disposeSectionChart() {
    sectionChart?.dispose()
    sectionChart = null
}

function exportSectionChart() {
    if (!sectionChart) return
    const url = sectionChart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#101411' })
    const link = document.createElement('a')
    link.href = url
    link.download = `section-${Date.now()}.png`
    link.click()
}

// 剖面线第二点落定后自动打开剖面图
watch(() => sceneStore.sectionState.pointB, (pointB) => {
    if (pointB) workspace.openSectionDialog()
})
watch(() => workspace.sectionDialogVisible, (visible) => {
    if (visible) void renderSectionChart()
})
function onGlobalKeydown(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        workspace.commandPaletteVisible = true
    }
    if (event.key === 'Escape') workspace.commandPaletteVisible = false
}
onMounted(async () => {
    window.addEventListener('keydown', onGlobalKeydown)
    if (route.params.projectId !== 'local') {
        try {
            project.value = await workspaceApi.getProject(String(route.params.projectId))
            sceneStore.setCoordinateOrigin({ x: project.value.origin_x, y: project.value.origin_y, z: project.value.origin_z, verticalScale: project.value.vertical_scale })
        } catch { }
    } else {
        sceneStore.setCoordinateOrigin(null)
    }
})
onUnmounted(() => {
    window.removeEventListener('keydown', onGlobalKeydown)
    sceneStore.setCoordinateOrigin(null)
})
</script>

<style scoped>
.geo-workspace {
    width: 100vw;
    height: 100vh;
    display: grid;
    grid-template-rows: 52px minmax(0, 1fr) 24px;
    background: #0b0f0c;
    color: #d8d9d2;
    --studio-border: #29302a;
    --studio-copper: #b57d3d
}

.workspace-header {
    display: flex;
    align-items: center;
    border-bottom: 1px solid var(--studio-border);
    background: #101411;
    z-index: 5
}

.brand-button {
    height: 100%;
    width: 150px;
    border: 0;
    border-right: 1px solid var(--studio-border);
    background: #151a16;
    color: #e2ddd0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 14px;
    cursor: pointer;
    font: 12px Bahnschrift;
    letter-spacing: .12em
}

.brand-glyph {
    width: 24px;
    height: 24px;
    display: grid;
    place-items: center;
    background: #a66f34;
    color: #16120d;
    font-weight: 800
}

.project-identity {
    height: 100%;
    min-width: 220px;
    padding: 9px 18px;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--studio-border)
}

.project-identity span {
    font: 8px Bahnschrift;
    letter-spacing: .16em;
    color: #5f685f
}

.project-identity strong {
    font-size: 12px;
    margin-top: 2px
}

.command-trigger {
    width: min(390px, 30vw);
    height: 32px;
    margin-left: 18px;
    padding: 0 10px;
    border: 1px solid #303831;
    background: #171c18;
    color: #687168;
    display: flex;
    align-items: center;
    gap: 9px;
    cursor: pointer;
    text-align: left
}

.command-trigger span {
    flex: 1;
    font-size: 11px
}

.command-trigger kbd,
.command-list kbd {
    font: 9px Bahnschrift;
    color: #596159;
    border: 1px solid #313832;
    padding: 2px 5px
}

.header-tools {
    margin-left: auto;
    height: 100%;
    display: flex;
    align-items: center;
    padding-right: 8px
}

.header-tools button {
    height: 32px;
    min-width: 34px;
    margin: 0 2px;
    border: 1px solid transparent;
    background: transparent;
    color: #788178;
    cursor: pointer
}

.header-tools button:hover,
.header-tools button.active {
    color: #d7d4ca;
    background: #1d241e;
    border-color: #333c34
}

.header-tools .export-button {
    padding: 0 11px;
    display: flex;
    align-items: center;
    gap: 6px;
    border-color: #604927;
    color: #d0a168
}

.tool-divider {
    height: 22px;
    width: 1px;
    background: #2b322c;
    margin: 0 5px
}

.workspace-grid {
    min-height: 0;
    display: grid;
    grid-template-columns: 270px minmax(0, 1fr) 300px;
    grid-template-rows: minmax(0, 1fr) 280px;
    grid-template-areas: "left viewport right" "left bottom right"
}

.workspace-grid.no-left {
    grid-template-columns: minmax(0, 1fr) 300px;
    grid-template-areas: "viewport right" "bottom right"
}

.workspace-grid.no-right {
    grid-template-columns: 270px minmax(0, 1fr);
    grid-template-areas: "left viewport" "left bottom"
}

.workspace-grid.no-left.no-right {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas: "viewport" "bottom"
}

.workspace-grid.no-bottom {
    grid-template-rows: minmax(0, 1fr);
    grid-template-areas: "left viewport right"
}

.workspace-grid.no-left.no-bottom {
    grid-template-areas: "viewport right"
}

.workspace-grid.no-right.no-bottom {
    grid-template-areas: "left viewport"
}

.workspace-grid.no-left.no-right.no-bottom {
    grid-template-areas: "viewport"
}

.left-dock {
    grid-area: left
}

.right-dock {
    grid-area: right
}

.bottom-dock {
    grid-area: bottom
}

.viewport-shell {
    grid-area: viewport;
    position: relative;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background: #090d0b
}

.viewport-shell::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    box-shadow: inset 0 0 80px rgba(0, 0, 0, .35)
}

.viewport-shell :deep(.tools-bar) {
    top: 14px !important;
    bottom: auto !important;
    right: 16px;
    max-width: calc(100% - 32px);
    overflow-x: auto;
    overflow-y: hidden;
    border-radius: 2px;
    background: rgba(16, 21, 17, .9);
    border-color: #3b443c;
    box-shadow: 0 12px 32px rgba(0, 0, 0, .35)
}

.viewport-shell :deep(.tools-group) {
    flex-shrink: 0
}

.viewport-shell :deep(.tool-btn) {
    border-radius: 1px;
    background: #1a211b;
    border-color: #374038
}

.viewport-ruler {
    position: absolute;
    z-index: 3;
    pointer-events: none;
    opacity: .45
}

.top-ruler {
    left: 25px;
    right: 0;
    top: 0;
    height: 7px;
    background: repeating-linear-gradient(90deg, #687068 0 1px, transparent 1px 25px)
}

.left-ruler {
    top: 25px;
    bottom: 0;
    left: 0;
    width: 7px;
    background: repeating-linear-gradient(#687068 0 1px, transparent 1px 25px)
}

.viewport-badge {
    position: absolute;
    z-index: 4;
    left: 15px;
    bottom: 14px;
    font: 8px Bahnschrift;
    letter-spacing: .14em;
    color: #778078;
    background: rgba(12, 16, 13, .78);
    padding: 6px 8px
}

.viewport-badge i {
    display: inline-block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #6d9873;
    margin-right: 6px
}

.status-bar {
    display: flex;
    align-items: center;
    gap: 22px;
    padding: 0 10px;
    background: #151a16;
    border-top: 1px solid #303731;
    color: #697169;
    font: 8px Bahnschrift;
    letter-spacing: .1em
}

.status-bar i {
    display: inline-block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    margin-right: 5px
}

.status-bar i.online {
    background: #6c9672
}

.cursor-coords {
    color: #9aa39a;
    font-family: Consolas, monospace;
    letter-spacing: .02em
}

.scene-save-row {
    display: flex;
    gap: 10px
}

.scene-hint {
    margin: 10px 0 0;
    color: #8a938a;
    font-size: 12px
}

.scene-list {
    margin-top: 14px;
    max-height: 320px;
    overflow: auto;
    border-top: 1px solid #ebeef5
}

.scene-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 2px;
    border-bottom: 1px solid #f0f2f5
}

.scene-item-info strong {
    display: block;
    font-size: 13px;
    color: #303133
}

.scene-item-info small {
    color: #909399;
    font-size: 11px
}

.scene-item-actions {
    display: flex;
    gap: 6px
}

.section-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px
}

.section-meta {
    flex: 1;
    color: #606266;
    font-size: 12px
}

.section-chart {
    width: 100%;
    height: 460px;
    background: #101411
}

.section-empty {
    margin: 6px 0 0;
    color: #909399;
    font-size: 12px
}

.status-spacer {
    flex: 1
}

.command-list {
    display: flex;
    flex-direction: column;
    margin-top: 10px
}

.command-list button {
    height: 42px;
    border: 0;
    border-bottom: 1px solid #2a302b;
    background: transparent;
    color: #adb4ad;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 10px;
    text-align: left;
    cursor: pointer
}

.command-list button:hover {
    background: #1b211c;
    color: #e5e1d6
}

.command-list button span {
    flex: 1
}

@media(max-width:1000px) {
    .workspace-grid {
        grid-template-columns: 220px minmax(0, 1fr);
        grid-template-areas: "left viewport" "left bottom"
    }

    .right-dock {
        display: none
    }

    .project-identity {
        min-width: 160px
    }

    .command-trigger {
        display: none
    }
}
</style>
