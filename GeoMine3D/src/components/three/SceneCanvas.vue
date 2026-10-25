<template>
    <div ref="containerRef" class="scene-canvas" @dragover="onDragOver" @dragleave="onDragLeave" @drop="onDrop">
        <canvas ref="canvasRef" class="canvas" />

        <!-- 工具箱:所有视口操作 + 沉陷对比统一收在此处(见 SceneToolbox.vue) -->
        <SceneToolbox :groups="toolGroups" :initial="initialToolGroup" @tool="onToolEvent" />

        <div v-if="lastMeasurementDistance !== null" class="measure-chip">
            最近测量 {{ lastMeasurementDistance.toFixed(2) }} m
        </div>

        <!-- 沉陷对比状态与位移色标(启用对比时显示) -->
        <div v-if="settlementStore.enabled" class="settlement-legend">
            <div class="sl-head">
                <span>SETTLEMENT OVERLAY</span>
                <b>沉陷对比 · t={{ Math.round(settlementStore.timePercent) }}%</b>
            </div>
            <template v-if="settlementStore.colorMode !== 'original'">
                <div class="sl-bar"></div>
                <div class="sl-scale">
                    <span>0</span>
                    <span>{{ settlementStore.colorMode === 'dz'
                        ? `竖向位移 ≤ ${settlementStore.maxSubsidenceM.toFixed(2)} m`
                        : `水平位移幅值 ≤ ${settlementStore.maxHorizontalM.toFixed(2)} m` }}</span>
                </div>
            </template>
            <div class="sl-note">沉陷夸大 {{ settlementStore.exaggeration }}× · 叠加Z向 {{ verticalScale }}×</div>
        </div>

        <div v-if="hoverLabel.visible" class="entity-hover-label"
            :style="{ left: `${hoverLabel.x}px`, top: `${hoverLabel.y}px` }">
            {{ hoverLabel.name }}
        </div>

        <!-- 地层颜色图例（与图层树/钻孔配色一致） -->
        <div v-if="legendEnabled && legendItems.length" class="strata-legend">
            <button class="lg-head" @click="legendCollapsed = !legendCollapsed">
                <span>STRATA LEGEND</span>
                <b>{{ legendCollapsed ? `图例 (${legendItems.length})` : '收起' }}</b>
            </button>
            <div v-if="!legendCollapsed" class="lg-body">
                <div v-for="item in legendItems" :key="item.name" class="lg-row">
                    <i :style="{ background: item.color }"></i><span>{{ item.name }}</span>
                </div>
            </div>
        </div>

        <!-- 拖放加载遮罩 -->
        <div v-if="isDragOver" class="drop-overlay">
            <div class="drop-indicator">
                <span class="drop-icon">⊕</span>
                <span class="drop-text">释放以加载 .glb 模型</span>
            </div>
        </div>
        <div v-if="dropError" class="drop-error">{{ dropError }}</div>

        <!-- 模型加载中遮罩 -->
        <div v-if="isLoading" class="loading-overlay">
            <div class="loading-card">
                <span class="loading-spinner"></span>
                <span class="loading-text">{{ loadingText || '模型加载中...' }}</span>
            </div>
        </div>

        <form v-if="annotationDraft.visible" class="annotation-composer" @submit.prevent="confirmAnnotation">
            <div class="annotation-composer__head"><span>NEW ANNOTATION</span><button type="button"
                    @click="cancelAnnotation">×</button></div>
            <strong>空间标注 {{ annotationDraft.index }}</strong>
            <small>X {{ annotationDraft.x.toFixed(2) }} · Y {{ annotationDraft.y.toFixed(2) }} · Z {{
                annotationDraft.z.toFixed(2) }}</small>
            <el-input ref="annotationInputRef" v-model="annotationDraft.text" maxlength="80" placeholder="输入标注内容" />
            <div class="annotation-composer__actions"><button type="button" @click="cancelAnnotation">取消</button><button
                    class="confirm" type="submit">创建标注</button></div>
        </form>

        <!-- 虚拟钻孔查询结果 -->
        <div v-if="virtualBoreholeResult" class="virtual-card">
            <div class="vc-head"><span>VIRTUAL BOREHOLE</span><button @click="closeVirtualBoreholeResult">×</button></div>
            <strong>虚拟钻孔</strong>
            <small>X {{ virtualBoreholeResult.x.toFixed(1) }} · Y {{ virtualBoreholeResult.y.toFixed(1) }} ·
                邻孔 {{ virtualBoreholeResult.used_neighbors }} · 最近 {{ virtualBoreholeResult.nearest_distance_m === null
                    ? '—' : virtualBoreholeResult.nearest_distance_m.toFixed(0) }} m</small>
            <div class="vc-layers">
                <div v-for="layer in virtualBoreholeResult.layers" :key="layer.layer_name" class="vc-layer">
                    <i :style="{ background: layer.color }"></i>
                    <span class="vc-name">{{ layer.layer_name }}</span>
                    <span class="vc-depth">{{ layer.top_depth }}~{{ layer.bottom_depth }} m</span>
                </div>
                <div v-if="!virtualBoreholeResult.layers.length" class="vc-empty">该位置附近没有可用钻孔</div>
            </div>
            <div class="vc-actions">
                <button :disabled="!virtualBoreholeResult.layers.length" @click="openVirtualChart">查看柱状图</button>
                <button @click="closeVirtualBoreholeResult">关闭</button>
            </div>
        </div>

    </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, onActivated, onDeactivated, watch } from 'vue'
import { useRoute } from 'vue-router'
import * as THREE from 'three'
import { storeToRefs } from 'pinia'
import { DropLoader } from '@/three/loaders/DropLoader'
import { SceneManager } from '@/three/core/SceneManager'
import { CameraManager } from '@/three/core/CameraManager'
import { RendererManager } from '@/three/core/RendererManager'
import { ControlsManager } from '@/three/core/ControlsManager'
import { installRemoteControl } from '@/three/core/remoteControl'
import { LightManager } from '@/three/core/LightManager'
import { ModelManager } from '@/three/managers/ModelManager'
import { LayerManager } from '@/three/managers/LayerManager'
import { HighlightManager } from '@/three/managers/HighlightManager'
import { SelectionManager } from '@/three/managers/SelectionManager'
import { SettlementManager } from '@/three/managers/SettlementManager'
import { BoundaryOverlay } from '@/three/managers/BoundaryOverlay'
import type { SettlementIndex } from '@/three/managers/SettlementManager'
import SceneToolbox from '@/components/three/SceneToolbox.vue'
import type { ToolGroup } from '@/components/three/SceneToolbox.vue'
import { StratumModelLoader } from '@/three/loaders/StratumModelLoader'
import { BoreholeModelLoader } from '@/three/loaders/BoreholeModelLoader'
import { WorkingFaceModelLoader } from '@/three/loaders/WorkingFaceModelLoader'
import { ClipTool } from '@/three/tools/ClipTool'
import { MeasureTool } from '@/three/tools/MeasureTool'
import { AnnotationTool } from '@/three/tools/AnnotationTool'
import type { AnnotationResult } from '@/three/tools/AnnotationTool'
import { StratumExplodeTool } from '@/three/tools/StratumExplodeTool'
import { AxisGizmoTool } from '@/three/tools/AxisGizmoTool'
import { BoundingBoxTool } from '@/three/tools/BoundingBoxTool'
import { workspaceApi, type BoundariesPayload, type VirtualBoreholeResult } from '@/api/workspace'
import { useSceneStore, useBoreholeStore, useWorkspaceStore } from '@/stores'
import type { SceneSnapshot } from '@/stores/sceneStore'
import { useSettlementStore } from '@/stores/settlementStore'
import type { ModelItem, BoreholeItem, StratumLayerControl } from '@/types'
import type { ModelLoadRequest } from '@/stores/sceneStore'

// ==================== Store & State ====================

const sceneStore = useSceneStore()
const boreholeStore = useBoreholeStore()
const workspaceStore = useWorkspaceStore()
const settlementStore = useSettlementStore()
const route = useRoute()
const isProjectMode = computed(() => String(route.params.projectId) !== 'local')

const {
    layerVisible,
    loadRequest,
    unloadRequest,
    showEdges,
    groupOpacity,
    stratumLayers,
    coordinateOrigin,
    verticalScale,
    toolState,
    measurements,
    lastMeasurementDistance,
} = storeToRefs(sceneStore)

const containerRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const fileInputRef = ref<HTMLInputElement>()
const clipRange = ref({ min: -1000, max: 1000 })
const clipStep = ref(1)

// 剖切滑块操作的是场景局部坐标，标签换算回原始投影坐标显示：
// 世界X=东向偏移、世界Y=20倍夸张高程偏移、世界Z=负的北向偏移
const formatClipPosition = computed(() => {
    const value = toolState.value.clipHeight
    const origin = coordinateOrigin.value
    if (!origin) return value.toFixed(2)
    if (toolState.value.clipAxis === 'x') return (origin.x + value).toFixed(2)
    // 世界坐标 y 已是夸张后的高程,除回**当前生效**的竖向倍数才是真实高程
    if (toolState.value.clipAxis === 'y') return (origin.z + value / verticalScale.value).toFixed(2)
    return (origin.y - value).toFixed(2)
})

const rotateXAxisEnabled = ref(true)
const stratumExploded = ref(false)
const outlineEnabled = ref(false)
const boundingBoxEnabled = ref(false)
// 与 initScene 中的 setHoverEnabled(true) 保持一致，避免开关显示“关”但行为是“开”
const hoverEnabled = ref(true)
// 矿区边界/地层图例叠加层开关（图例默认展开，边界默认关，避免首屏遮挡）
const boundaryEnabled = ref(false)
const legendEnabled = ref(true)
const legendCollapsed = ref(false)
// 矿区边界数据缓存（项目模式从后端拉取一次）
const boundariesData = ref<BoundariesPayload | null>(null)
let boundaryOverlay: BoundaryOverlay | null = null
// 虚拟钻孔查询
const virtualBoreholeActive = ref(false)
const virtualBoreholeLoading = ref(false)
const virtualBoreholeResult = ref<VirtualBoreholeResult | null>(null)
let virtualMarker: THREE.Group | null = null
let virtualMarkerResources: Array<THREE.BufferGeometry | THREE.Material> = []
const hoverLabel = ref({ visible: false, name: '', x: 0, y: 0 })
const isDragOver = ref(false)
const dropError = ref('')
const isLoading = ref(false)
const loadingText = ref('')
const annotationInputRef = ref()
const annotationDraft = ref({ visible: false, index: 1, text: '', x: 0, y: 0, z: 0 })

const BOREHOLE_VERTICAL_SCALE = 20
const dropLoader = new DropLoader()

let sceneManager: SceneManager
let cameraManager: CameraManager
let rendererManager: RendererManager
let controlsManager: ControlsManager
let lightManager: LightManager
let modelManager: ModelManager
let layerManager: LayerManager
let highlightManager: HighlightManager
let selectionManager: SelectionManager
let settlementManager: SettlementManager | null = null
let clipTool: ClipTool
let measureTool: MeasureTool
let annotationTool: AnnotationTool
let axisGizmoTool: AxisGizmoTool | null = null
let boundingBoxTool: BoundingBoxTool | null = null
// 远程控制桥(含 WS 中继客户端)的清理函数,随画布卸载
let disposeRemoteBridge: (() => void) | null = null
let stratumExplodeTool: StratumExplodeTool | null = null
let animFrameId: number
let resizeObserver: ResizeObserver
let isAnimating = false
let performanceWindowStarted = performance.now()
let performanceFrameCount = 0

// ==================== Animation ====================

function animate() {
    if (!isAnimating) return
    animFrameId = requestAnimationFrame(animate)
    controlsManager.update()
    annotationTool?.update()
    boundingBoxTool?.update()
    measureTool?.update()
    lightManager.updateFromCamera(cameraManager.camera)
    rendererManager.render(sceneManager.scene, cameraManager.camera)
    axisGizmoTool?.render()
    performanceFrameCount += 1
    const now = performance.now()
    const elapsed = now - performanceWindowStarted
    if (elapsed >= 500) {
        workspaceStore.updatePerformance({
            fps: Math.round(performanceFrameCount * 1000 / elapsed),
            calls: rendererManager.renderer.info.render.calls,
            triangles: rendererManager.renderer.info.render.triangles,
            geometries: rendererManager.renderer.info.memory.geometries,
            textures: rendererManager.renderer.info.memory.textures,
        })
        performanceWindowStarted = now
        performanceFrameCount = 0
    }
}

function startAnimate() {
    if (isAnimating) return
    isAnimating = true
    performanceWindowStarted = performance.now()
    performanceFrameCount = 0
    animate()
}

function stopAnimate() {
    if (!isAnimating) return
    isAnimating = false
    cancelAnimationFrame(animFrameId)
}

// ==================== Model Loading ====================

async function loadStratumModel(model: ModelItem) {
    const stratumLoader = new StratumModelLoader()
    try {
        const object = await stratumLoader.load(model)
        alignProjectedModel(object)
        modelManager.addModel({ id: model.id, name: model.name, type: 'stratum', object })
        registerStratumLayersFromObject(object, model.id, model.name)
    } catch {
        addPlaceholderStratum(model)
    }
    // 新层加载后同步沉陷绑定(增量式:已绑定的层不会被重置基线)
    syncSettlementBinding()
    layerManager.setLayerEdgesVisible('stratum', showEdges.value)
}

function alignProjectedModel(object: THREE.Object3D) {
    const origin = coordinateOrigin.value
    if (!origin) return
    const center = new THREE.Box3().setFromObject(object).getCenter(new THREE.Vector3())
    const xProjected = Math.abs(center.x) >= 100000
    const yProjected = Math.abs(center.y) >= 100000
    const zProjected = Math.abs(center.z) >= 100000
    if (!xProjected || (!yProjected && !zProjected)) return

    if (yProjected) {
        // 主数据格式：X/Y 为投影平面，Z 为已夸张高程。
        object.position.x -= origin.x
        object.position.y -= origin.y
        object.position.z -= origin.z * origin.verticalScale
        object.userData.axisMapping = 'XYZ'
    } else {
        // 部分旧模型为 Y-up：X/Z 为投影平面，Y 为已夸张高程，先交换 Y/Z。
        const axisMapping = new THREE.Matrix4().set(
            1, 0, 0, -origin.x,
            0, 0, 1, -origin.y,
            0, 1, 0, -origin.z * origin.verticalScale,
            0, 0, 0, 1,
        )
        object.applyMatrix4(axisMapping)
        object.userData.axisMapping = 'XZY'
    }
    object.updateMatrixWorld(true)
    object.userData.coordinateMode = 'projected'
    object.userData.coordinateOrigin = { ...origin }
}

async function loadWorkingFaceModel(model: ModelItem, renderType: 'workingface' | 'roadway' = 'workingface') {
    const workingFaceLoader = new WorkingFaceModelLoader()
    try {
        const object = await workingFaceLoader.load(model)
        modelManager.addModel({ id: model.id, name: model.name, type: renderType, object })
    } catch {
        addPlaceholderWorkingFace(model)
    }
}

async function loadBoreholeModel(
    borehole: BoreholeItem,
    index: number,
    origin?: { x: number; y: number; z: number; verticalScale: number },
) {
    const boreholeLoader = new BoreholeModelLoader()
    let position: { x: number; y: number; z: number }
    if (borehole.location) {
        position = {
            x: borehole.location.x - (origin?.x ?? 0),
            y: borehole.location.y - (origin?.y ?? 0),
            z: (borehole.location.z - (origin?.z ?? 0)) * (origin?.verticalScale ?? BOREHOLE_VERTICAL_SCALE),
        }
    } else {
        const spacing = 500
        const cols = 10
        position = {
            x: (index % cols) * spacing - (cols * spacing) / 2,
            y: Math.floor(index / cols) * spacing - (cols * spacing) / 2,
            z: 0,
        }
    }
    const object = boreholeLoader.createBoreholeObject(
        borehole,
        position,
        origin?.verticalScale ?? BOREHOLE_VERTICAL_SCALE,
    )
    modelManager.addModel({ id: borehole.id, name: borehole.name, type: 'borehole', object })
}

async function loadAllBoreholeModels(boreholes: BoreholeItem[]) {
    const located = boreholes.filter((item) => item.location).map((item) => item.location!)
    const projectOrigin = coordinateOrigin.value
    const origin = projectOrigin ?? (located.length
        ? {
            x: located.reduce((sum, item) => sum + item.x, 0) / located.length,
            y: located.reduce((sum, item) => sum + item.y, 0) / located.length,
            z: located.reduce((sum, item) => sum + item.z, 0) / located.length,
            verticalScale: BOREHOLE_VERTICAL_SCALE,
        }
        : undefined)
    for (let i = 0; i < boreholes.length; i += 1) {
        const borehole = boreholes[i]
        if (modelManager.getModel(borehole.id)) {
            sceneStore.setModelLoadStatus('borehole', borehole.id, { loaded: true, loading: false })
            continue
        }
        await loadBoreholeModel(borehole, i, origin)
        sceneStore.setModelLoadStatus('borehole', borehole.id, { loaded: true, loading: false })
    }
}

// 从场景中移除模型并同步清理状态、图层树与拾取目标。
function unloadModelByRequest(req: { type: 'stratum' | 'borehole' | 'workingface' | 'roadway'; id: string }) {
    if (req.type === 'borehole') {
        // '__all__' 移除整组；否则只移除指定钻孔
        const targets = req.id === '__all__'
            ? modelManager.getModelsByType('borehole')
            : [modelManager.getModel(req.id)].filter((item): item is NonNullable<typeof item> => Boolean(item))
        for (const model of targets) {
            modelManager.removeModel(model.id)
            sceneStore.clearLoadStatus('borehole', model.id)
        }
        if (req.id === '__all__') sceneStore.clearLoadStatus('borehole', '__all__')
    } else {
        modelManager.removeModel(req.id)
        sceneStore.clearLoadStatus(req.type, req.id)
        if (req.type === 'stratum') {
            sceneStore.removeStratumLayersByModel(req.id)
            // 地层被移除后,沉陷位移场的绑定也要同步收缩(失效 mesh 会被自动修剪),
            // 但在那之前必须把基线位置写回去,否则再加载会以变形位置为基线。
            settlementManager?.restoreBase()
        }
    }
    sceneStore.selectObject(null)
    refreshSelectionPickTargets()
    boundingBoxTool?.refresh()
    if (toolState.value.clipEnabled) {
        syncToolRuntimeState()
    }
    syncSettlementBinding()
}

async function loadModelByRequest(req: ModelLoadRequest) {
    isLoading.value = true
    const typeLabel: Record<string, string> = {
        stratum: '地层',
        borehole: '钻孔',
        workingface: '工作面',
        roadway: '巷道',
    }
    loadingText.value = `正在加载${typeLabel[req.type] || req.type}模型...`
    try {
        let preferImmediateFocus = false
        let focusType: 'stratum' | 'borehole' | 'workingface' | 'roadway' | null = null

        if (req.type === 'stratum') {
            await loadStratumModel(req.model)
            focusType = 'stratum'
        }

        if (req.type === 'workingface') {
            await loadWorkingFaceModel(req.model)
            focusType = 'workingface'
        }

        if (req.type === 'roadway') {
            await loadWorkingFaceModel(req.model, 'roadway')
            focusType = 'roadway'
        }

        if (req.type === 'borehole') {
            boreholeStore.list = req.boreholeList
            await loadAllBoreholeModels(req.boreholeList)
            focusType = 'borehole'
            preferImmediateFocus = true
        }

        sceneManager.removeGrid()
        refreshSelectionPickTargets()
        sceneStore.setModelLoadStatus(req.type, req.id, { loaded: true, loading: false })
        // 新加载的模型同步套用所属图层的整体透明度
        applyGroupOpacityToModels()

        if (focusType) {
            fitCameraToType(focusType, preferImmediateFocus)
        } else {
            fitCameraToType(null, preferImmediateFocus)
        }

        // 钻孔加载后孔口平均高程更准确，重建贴地覆盖层
        if (focusType === 'borehole') rebuildBoundaryOverlay()

        if (toolState.value.clipEnabled) {
            syncToolRuntimeState()
        }
    } catch (err) {
        sceneStore.setModelLoadStatus(req.type, req.id, { loading: false })
        console.error(`[SceneCanvas] ${req.type} 模型加载失败`, err)
    } finally {
        isLoading.value = false
        loadingText.value = ''
    }
}

function addPlaceholderStratum(model: ModelItem) {
    const colors: Record<string, number> = { 'strata-001': 0x4a7a8a, 'strata-002': 0x6d9e73 }
    const color = colors[model.id] ?? 0x5a8a9a
    const geometry = new THREE.BoxGeometry(400, 20, 300)
    const material = new THREE.MeshLambertMaterial({ color, transparent: true, opacity: 0.7, clipShadows: true })
    material.clippingPlanes = []
    const mesh = new THREE.Mesh(geometry, material)
    mesh.position.z = Object.keys(colors).indexOf(model.id) * -25
    mesh.name = `stratum_${model.id}`
    mesh.userData = {
        id: `${model.id}::0`,
        name: `${model.name}_layer_1`,
        type: 'stratum',
        modelData: model,
        modelId: model.id,
        layerName: `${model.name}_layer_1`,
    }
    modelManager.addModel({ id: model.id, name: model.name, type: 'stratum', object: mesh })
    registerStratumLayersFromObject(mesh, model.id, model.name)
}

function addPlaceholderWorkingFace(model: ModelItem) {
    const geometry = new THREE.BoxGeometry(200, 15, 120)
    const material = new THREE.MeshLambertMaterial({ color: 0xf5a623, transparent: true, opacity: 0.8, clipShadows: true })
    material.clippingPlanes = []
    const mesh = new THREE.Mesh(geometry, material)
    mesh.position.set(Math.random() * 100 - 50, Math.random() * 100 - 50, -80)
    mesh.name = `workingface_${model.id}`
    mesh.userData = { id: model.id, name: model.name, type: 'workingface', modelData: model }
    modelManager.addModel({ id: model.id, name: model.name, type: 'workingface', object: mesh })
}

// ==================== Drag-and-Drop ====================

function onDragOver(e: DragEvent) {
    e.preventDefault()
    if (e.dataTransfer) {
        e.dataTransfer.dropEffect = 'copy'
    }
    isDragOver.value = true
}

function onDragLeave(e: DragEvent) {
    const container = containerRef.value
    if (!container || !e.relatedTarget || !container.contains(e.relatedTarget as Node)) {
        isDragOver.value = false
    }
}

function onDrop(e: DragEvent) {
    e.preventDefault()
    isDragOver.value = false
    const files = e.dataTransfer?.files
    if (!files || files.length === 0) return
    const file = files[0]
    if (!file.name.toLowerCase().endsWith('.glb')) {
        dropError.value = '仅支持 .glb 文件格式'
        setTimeout(() => { dropError.value = '' }, 3000)
        return
    }
    loadDroppedGLB(file)
}

function onFileSelected(e: Event) {
    const input = e.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.glb')) {
        dropError.value = '仅支持 .glb 文件格式'
        setTimeout(() => { dropError.value = '' }, 3000)
        return
    }
    loadDroppedGLB(file)
    input.value = ''
}

async function loadDroppedGLB(file: File) {
    isLoading.value = true
    loadingText.value = `正在加载 ${file.name}...`
    try {
        const { group, modelId, modelName, controls } = await dropLoader.loadFromFile(file)
        modelManager.addModel({ id: modelId, name: modelName, type: 'stratum', object: group })
        sceneManager.removeGrid()
        refreshSelectionPickTargets()
        if (controls.length) {
            sceneStore.registerStratumLayers(controls)
        }
        layerManager.setLayerEdgesVisible('stratum', showEdges.value)
        fitCameraToType(null, true)
        if (toolState.value.clipEnabled) {
            syncToolRuntimeState()
        }
    } catch (err) {
        console.error('[SceneCanvas] 模型加载失败', err)
        dropError.value = `模型加载失败: ${(err as Error).message}`
        setTimeout(() => { dropError.value = '' }, 5000)
    } finally {
        isLoading.value = false
        loadingText.value = ''
    }
}

// ==================== Camera ====================

function fitCameraToType(type: 'stratum' | 'borehole' | 'workingface' | 'roadway' | null, immediate = false) {
    const models = type !== null
        ? modelManager.getModelsByType(type)
        : modelManager.getAllModels()
    if (!models.length) return

    const box = new THREE.Box3()
    models.forEach((m) => box.expandByObject(m.object))

    const fitResult = cameraManager.fitToBox(box)
    if (!fitResult) return

    cameraManager.camera.near = fitResult.near
    cameraManager.camera.far = fitResult.far
    cameraManager.camera.updateProjectionMatrix()
    controlsManager.setDistanceLimits(fitResult.fitDistance * 0.1, fitResult.fitDistance * 8)

    if (immediate) {
        cameraManager.camera.position.copy(fitResult.position)
        controlsManager.controls.target.copy(fitResult.center)
        controlsManager.controls.update()
        return
    }

    const startTarget = controlsManager.controls.target.clone()
    cameraManager.animateTo(
        fitResult.position,
        fitResult.center,
        startTarget,
        (lookAt) => {
            controlsManager.controls.target.copy(lookAt)
            controlsManager.controls.update()
        }
    )
}

function resetCamera() {
    fitCameraToType(null, true)
}

function onRotateXAxisToggle(value: boolean | string | number) {
    const enabled = Boolean(value)
    rotateXAxisEnabled.value = enabled
    sceneManager?.setGeoRootRotationXEnabled(enabled)
    stratumExplodeTool?.sync()
    if (modelManager?.getAllModels().length) {
        fitCameraToType(null, true)
    }
}

// ==================== Selection & Hover ====================

// ==================== Settlement (沉陷对比) ====================

/**
 * 把位移场挂到当前已加载的地层几何上。
 *
 * 采用**几何变形**而不是双模型叠加 / shader 注入:
 * - 本数据 67~70% 顶点沉陷前后严格共面,双模型同屏必现 z-fighting;
 * - 本工程 HighlightManager/透明度面板会整块替换材质,shader 注入会丢;
 * 改几何则与剖切/炸开/拾取/高亮/透明度全部兼容。
 */
function syncSettlementBinding() {
    if (!settlementManager || !modelManager) return
    if (!settlementStore.enabled) {
        if (settlementManager.attachedCount) {
            settlementManager.restoreBase()
            settlementManager.detach()
            settlementStore.boundLayers = 0
            settlementStore.boundVertices = 0
            settlementStore.bindIssues = []
        }
        return
    }
    const count = settlementManager.attach(modelManager)
    settlementStore.boundLayers = count
    settlementStore.bindIssues = settlementManager.lastIssues.slice(0, 4).map(it => ({
        label: it.layerCode === '-' ? it.mesh : it.layerCode,
        detail: it.expected !== undefined && it.actual !== undefined
            ? `${it.reason}（位移 ${it.expected} / 顶点 ${it.actual}）`
            : it.reason,
    }))
    let verts = 0
    for (const model of modelManager.getModelsByType('stratum')) {
        model.object.traverse(child => {
            if ((child as THREE.Mesh).isMesh) {
                verts += (child as THREE.Mesh).geometry.getAttribute('position')?.count ?? 0
            }
        })
    }
    settlementStore.boundVertices = verts
}

/** 首次启用时才拉取位移场数据(约 4 MB);索引很早就会先拉一次,用于面板展示元信息 */
async function ensureSettlementField(): Promise<boolean> {
    if (!settlementManager) settlementManager = new SettlementManager()
    if (settlementManager.loaded) return true
    settlementStore.loading = true
    settlementStore.loadError = null
    try {
        const meta = await settlementManager.load()
        applySettlementMeta(meta)
        settlementStore.fieldLoaded = true
        return true
    } catch (err) {
        settlementStore.loadError = err instanceof Error ? err.message : String(err)
        settlementStore.enabled = false
        return false
    } finally {
        settlementStore.loading = false
    }
}

function applySettlementMeta(meta: SettlementIndex) {
    settlementStore.maxSubsidenceM = meta.maxSubsidenceM
    settlementStore.maxHorizontalM = meta.maxHorizontalM
    settlementStore.displayZScale = meta.displayZScale
    settlementStore.workingsFollow = meta.workingsFollowSettlement
    settlementStore.generatedUtc = meta.generatedUtc
}

/** 只拉 4 KB 的索引,让面板在未启用时就能显示“最大沉降”等真实值 */
async function prefetchSettlementMeta() {
    if (!settlementManager) settlementManager = new SettlementManager()
    try {
        applySettlementMeta(await settlementManager.loadIndex())
    } catch {
        // 预取失败不提示,用户启用时会得到完整错误
    }
}

function refreshSelectionPickTargets() {
    if (!selectionManager || !modelManager) return
    selectionManager.setPickTargets(modelManager.getAllModels().map((item) => item.object))
}

function hideHoverLabel() {
    hoverLabel.value.visible = false
}

function onControlStart() {
    selectionManager?.setHoverEnabled(false)
    hideHoverLabel()
}

function onControlEnd() {
    if (hoverEnabled.value) {
        selectionManager?.setHoverEnabled(true)
    }
}
function toggleHoverEffect() {
    hoverEnabled.value = !hoverEnabled.value
    selectionManager?.setHoverEnabled(hoverEnabled.value)
}

// ==================== 坐标读数 ====================

// 投影面在世界空间即 y=0 平面；用数学面求交读平面坐标，代价 O(1)
const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
const cursorRaycaster = new THREE.Raycaster()
const cursorPointer = new THREE.Vector2()
const cursorHitPoint = new THREE.Vector3()
let lastCursorUpdate = 0
// 悬停拾取到的模型表面点（世界坐标），作为高程读数来源；随鼠标离开模型失效
let surfacePoint: THREE.Vector3 | null = null
let surfacePointAt = 0

/** 世界坐标 → 真实投影坐标/高程（米）。 */
function worldPointToProject(point: THREE.Vector3) {
    const origin = coordinateOrigin.value
    if (!origin) {
        return { x: point.x, y: -point.z, z: point.y }
    }
    return {
        x: origin.x + point.x,
        y: origin.y - point.z,
        z: origin.z + point.y / verticalScale.value,
    }
}

function onCanvasPointerMove(event: PointerEvent) {
    if (!cameraManager || !canvasRef.value) return
    const now = performance.now()
    // 平面求交本身很便宜，节流只为避免高频写 store 触发状态栏抖动
    if (now - lastCursorUpdate < 100) return
    lastCursorUpdate = now

    const rect = canvasRef.value.getBoundingClientRect()
    cursorPointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
    )
    cursorRaycaster.setFromCamera(cursorPointer, cameraManager.camera)
    // 悬停命中的表面点(1s 内)优先：既有真实高程，平面坐标也更准
    if (surfacePoint && now - surfacePointAt < 1000) {
        workspaceStore.setCursorCoordinate(worldPointToProject(surfacePoint))
        return
    }
    if (cursorRaycaster.ray.intersectPlane(groundPlane, cursorHitPoint)) {
        const projected = worldPointToProject(cursorHitPoint)
        workspaceStore.setCursorCoordinate({ x: projected.x, y: projected.y, z: null })
    } else {
        workspaceStore.setCursorCoordinate(null)
    }
}

function onCanvasPointerLeave() {
    surfacePoint = null
    workspaceStore.setCursorCoordinate(null)
}

// ==================== 虚拟钻孔查询 ====================

function toggleVirtualBorehole() {
    virtualBoreholeActive.value = !virtualBoreholeActive.value
    if (virtualBoreholeActive.value) {
        // 查询模式与测量/标注一样，避免点击误选模型
        selectionManager?.setEnabled(false)
        canvasRef.value?.addEventListener('click', onVirtualBoreholeClick)
    } else {
        canvasRef.value?.removeEventListener('click', onVirtualBoreholeClick)
        selectionManager?.setEnabled(!(toolState.value.measureEnabled || toolState.value.annotationEnabled))
        closeVirtualBoreholeResult()
    }
}

/** 射线与投影面（y=0 平面）求交，取平面落点 */
function pickGroundPoint(event: MouseEvent): THREE.Vector3 | null {
    if (!cameraManager || !canvasRef.value) return null
    const rect = canvasRef.value.getBoundingClientRect()
    cursorPointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
    )
    cursorRaycaster.setFromCamera(cursorPointer, cameraManager.camera)
    const hit = new THREE.Vector3()
    return cursorRaycaster.ray.intersectPlane(groundPlane, hit) ? hit : null
}

const onVirtualBoreholeClick = async (event: MouseEvent) => {
    if (!cameraManager || !canvasRef.value || virtualBoreholeLoading.value) return
    if (!isProjectMode.value) return
    const world = pickGroundPoint(event)
    if (!world) return
    const projected = worldPointToProject(world)
    virtualBoreholeLoading.value = true
    try {
        const result = await workspaceApi.getVirtualBorehole(String(route.params.projectId), {
            x: projected.x,
            y: projected.y,
        })
        virtualBoreholeResult.value = result
        showVirtualMarker(world.clone())
    } catch {
        virtualBoreholeResult.value = null
        clearVirtualMarker()
    } finally {
        virtualBoreholeLoading.value = false
    }
}

function showVirtualMarker(worldPoint: THREE.Vector3) {
    clearVirtualMarker()
    if (!sceneManager) return
    const group = new THREE.Group()
    group.userData.overlayHelper = true

    const top = worldPoint.clone().add(new THREE.Vector3(0, 500, 0))
    const lineGeometry = new THREE.BufferGeometry().setFromPoints([worldPoint, top])
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0x67e0ff, transparent: true, opacity: 0.95 })
    const line = new THREE.Line(lineGeometry, lineMaterial)
    line.userData.overlayHelper = true
    group.add(line)

    const coneGeometry = new THREE.ConeGeometry(16, 46, 12)
    const coneMaterial = new THREE.MeshBasicMaterial({ color: 0x67e0ff, transparent: true, opacity: 0.9 })
    const cone = new THREE.Mesh(coneGeometry, coneMaterial)
    cone.position.copy(top)
    cone.rotation.x = Math.PI
    cone.userData.overlayHelper = true
    group.add(cone)

    sceneManager.scene.add(group)
    virtualMarker = group
    virtualMarkerResources.push(lineGeometry, lineMaterial, coneGeometry, coneMaterial)
}

function clearVirtualMarker() {
    if (virtualMarker) {
        sceneManager?.scene.remove(virtualMarker)
        virtualMarker = null
    }
    for (const resource of virtualMarkerResources) resource.dispose()
    virtualMarkerResources = []
}

function closeVirtualBoreholeResult() {
    virtualBoreholeResult.value = null
    clearVirtualMarker()
}

/** 把虚拟钻孔结果送入底部柱状图页签 */
function openVirtualChart() {
    const result = virtualBoreholeResult.value
    if (!result || !result.layers.length) return
    const totalDepth = Math.max(...result.layers.map(layer => layer.bottom_depth))
    boreholeStore.currentDetail = {
        id: `virtual_${result.x.toFixed(0)}_${result.y.toFixed(0)}`,
        name: `虚拟钻孔 (${result.x.toFixed(0)}, ${result.y.toFixed(0)})`,
        totalDepth,
        layerCount: result.layers.length,
        location: { x: result.x, y: result.y, z: coordinateOrigin.value?.z ?? 0 },
        layers: result.layers.map(layer => ({
            layerName: layer.layer_name,
            topDepth: layer.top_depth,
            bottomDepth: layer.bottom_depth,
            thickness: layer.thickness,
            color: layer.color,
        })),
    }
    workspaceStore.openDock('borehole')
}

// ==================== 场景快照（保存/恢复） ====================

function getSceneState(): SceneSnapshot {
    const camera = cameraManager.camera
    const target = controlsManager.controls.target
    const types = ['stratum', 'borehole', 'workingface', 'roadway'] as const
    return {
        camera: {
            position: [camera.position.x, camera.position.y, camera.position.z],
            target: [target.x, target.y, target.z],
        },
        layers: types.map(type => ({
            type,
            visible: layerVisible.value[type],
            opacity: groupOpacity.value[type],
        })),
        showEdges: showEdges.value,
        verticalScale: verticalScale.value,
        clip: {
            enabled: toolState.value.clipEnabled,
            axis: toolState.value.clipAxis,
            height: toolState.value.clipHeight,
            keepLower: toolState.value.clipKeepLower,
        },
        explode: { gap: toolState.value.explodeGap, active: stratumExploded.value },
    }
}

function applySceneState(state: SceneSnapshot) {
    if (state.layers) {
        for (const item of state.layers) {
            if (!item?.type) continue
            sceneStore.setLayerVisible(item.type, Boolean(item.visible))
            if (typeof item.opacity === 'number') sceneStore.setGroupOpacity(item.type, item.opacity)
        }
    }
    if (typeof state.showEdges === 'boolean') sceneStore.setShowEdges(state.showEdges)
    if (typeof state.verticalScale === 'number' && state.verticalScale >= 1) {
        sceneStore.setVerticalScale(state.verticalScale)
    }
    if (state.clip) {
        sceneStore.setClipAxis(state.clip.axis ?? 'y')
        sceneStore.setClipHeight(Number(state.clip.height) || 0)
        sceneStore.setClipKeepLower(Boolean(state.clip.keepLower))
        toolState.value.clipEnabled = Boolean(state.clip.enabled)
    }
    if (state.explode) {
        sceneStore.setExplodeGap(Number(state.explode.gap) || 0)
        if (Boolean(state.explode.active) !== stratumExploded.value) {
            toggleStratumExplode()
        }
    }
    if (state.camera?.position?.length === 3 && state.camera?.target?.length === 3) {
        const [px, py, pz] = state.camera.position
        const [tx, ty, tz] = state.camera.target
        cameraManager.camera.position.set(px, py, pz)
        controlsManager.controls.target.set(tx, ty, tz)
        controlsManager.controls.update()
    }
}

/** 把画布当前帧导出为 PNG dataURL（不含坐标轴小部件）。 */
function captureImage(): string | null {
    if (!rendererManager || !sceneManager || !cameraManager) return null
    rendererManager.render(sceneManager.scene, cameraManager.camera)
    return rendererManager.renderer.domElement.toDataURL('image/png')
}

// ==================== 地层聚焦（柱状图联动） ====================

let focusOutlineTimer: ReturnType<typeof setTimeout> | null = null

function focusStratum(layerName: string) {
    const layer = stratumLayers.value.find(item => item.layerName === layerName)
    if (!layer) return
    const model = modelManager?.getModel(layer.modelId)
    if (!model) return

    let target: THREE.Mesh | null = null
    model.object.traverse((child) => {
        if (target) return
        const mesh = child as THREE.Mesh
        if (mesh.isMesh && String(mesh.userData?.id || '') === layer.key) {
            target = mesh
        }
    })
    if (!target) return
    const mesh = target as THREE.Mesh

    const box = new THREE.Box3().setFromObject(mesh)
    const fit = cameraManager.fitToBox(box)
    if (fit) {
        cameraManager.camera.near = fit.near
        cameraManager.camera.far = fit.far
        cameraManager.camera.updateProjectionMatrix()
        controlsManager.setDistanceLimits(fit.fitDistance * 0.1, fit.fitDistance * 8)
        const startTarget = controlsManager.controls.target.clone()
        cameraManager.animateTo(
            fit.position,
            fit.center,
            startTarget,
            (lookAt) => {
                controlsManager.controls.target.copy(lookAt)
                controlsManager.controls.update()
            }
        )
    }

    // 用既有描边系统闪烁提示目标层；若描边原本关闭则结束后还原
    const outlineWasEnabled = outlineEnabled.value
    rendererManager.setOutlineEnabled(true)
    rendererManager.setOutlineSelectedObjects([mesh])
    if (focusOutlineTimer) clearTimeout(focusOutlineTimer)
    focusOutlineTimer = setTimeout(() => {
        rendererManager?.setOutlineSelectedObjects([])
        if (!outlineWasEnabled) rendererManager?.setOutlineEnabled(false)
        focusOutlineTimer = null
    }, 2600)
}

// ==================== 覆盖层（矿区边界/图例） ====================

/** 叠加层基准高程：取已加载钻孔孔口的世界平均高度（地表附近），无钻孔时落到基准面。 */
function overlayYLevel() {
    const boreholes = modelManager?.getModelsByType('borehole') ?? []
    if (!boreholes.length) return 0
    const sum = boreholes.reduce((total, item) => total + item.object.position.y, 0)
    return sum / boreholes.length
}

function rebuildBoundaryOverlay() {
    if (!boundaryOverlay || !sceneManager) return
    const origin = coordinateOrigin.value
    if (!origin || !boundariesData.value) return
    boundaryOverlay.build(boundariesData.value, { x: origin.x, y: origin.y }, overlayYLevel())
    boundaryOverlay.setVisible(boundaryEnabled.value)
}

async function ensureBoundaries() {
    if (!isProjectMode.value || boundariesData.value) return
    try {
        boundariesData.value = await workspaceApi.listBoundaries(String(route.params.projectId))
        rebuildBoundaryOverlay()
    } catch { /* 边界数据缺失时静默跳过 */ }
}

watch(boundaryEnabled, (visible) => {
    boundaryOverlay?.setVisible(visible)
})

// 地层图例数据：按层名去重，保留登记顺序（自下而上）
const legendItems = computed(() => {
    const seen = new Map<string, string>()
    for (const layer of stratumLayers.value) {
        if (!layer.layerName || seen.has(layer.layerName)) continue
        seen.set(layer.layerName, layer.color)
    }
    return [...seen.entries()].map(([name, color]) => ({ name, color }))
})

// ==================== Layer ====================

function toHexColor(color?: THREE.Color) {
    if (!color) return '#5a8a9a'
    return `#${color.getHexString()}`
}

function registerStratumLayersFromObject(object: THREE.Object3D, modelId: string, modelName: string) {
    const controls: StratumLayerControl[] = []
    object.traverse((child) => {
        if (!(child as THREE.Mesh).isMesh) return
        const mesh = child as THREE.Mesh
        const key = String(mesh.userData?.id || `${modelId}::${mesh.uuid}`)
        const layerName = String(mesh.userData?.layerName || mesh.name || `${modelName}_layer`)
        const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material
        const color = material && (material as any).color ? toHexColor((material as any).color) : '#5a8a9a'
        const opacity = typeof (material as any)?.opacity === 'number' ? (material as any).opacity : 1
        controls.push({ key, modelId, modelName, layerName, visible: mesh.visible, opacity, color })
    })
    if (controls.length) {
        sceneStore.registerStratumLayers(controls)
    }
}

function toggleStratumExplode() {
    if (!stratumExplodeTool) return
    stratumExploded.value = stratumExplodeTool.toggle()
}

function onExplodeGapChange(value: number | undefined) {
    sceneStore.setExplodeGap(typeof value === 'number' ? value : 0)
}


function applyStratumLayerControl(control: StratumLayerControl) {
    const model = modelManager.getModel(control.modelId)
    if (!model) return
    model.object.traverse((child) => {
        if (!(child as THREE.Mesh).isMesh) return
        const mesh = child as THREE.Mesh
        const key = String(mesh.userData?.id || '')
        if (key !== control.key) return

        mesh.visible = control.visible
        // 整体透明度作为系数叠在单元透明度之上,两级滑块互不覆盖
        const opacity = Math.min(1, Math.max(0.05, control.opacity * groupOpacity.value.stratum))
        const mats = highlightManager.getEditableMaterials(mesh)
        for (const mat of mats as any[]) {
            if (mat.color) {
                mat.color.set(control.color)
            }
            mat.transparent = opacity < 1
            mat.opacity = opacity
            mat.needsUpdate = true
        }
        const edgeLines = (mesh as any).userData?.edgeLines
        if (edgeLines) {
            edgeLines.visible = showEdges.value && control.visible
        }
    })
}

/** 对钻孔/工作面/巷道按图层整体透明度刷新材质(地层走 applyStratumLayerControl) */
function applyGroupOpacityToModels() {
    if (!layerManager) return
    layerManager.setLayerOpacity('borehole', groupOpacity.value.borehole)
    layerManager.setLayerOpacity('workingface', groupOpacity.value.workingface)
    layerManager.setLayerOpacity('roadway', groupOpacity.value.roadway)
}

// ==================== Tools ====================

function syncToolRuntimeState() {
    if (!clipTool || !measureTool || !annotationTool || !selectionManager) return

    if (toolState.value.clipEnabled) {
        clipTool.enable({
            axis: toolState.value.clipAxis,
            position: toolState.value.clipHeight,
            keepLower: toolState.value.clipKeepLower,
            showHelper: false,
        })
    } else {
        clipTool.disable()
    }

    if (toolState.value.measureEnabled) {
        measureTool.enable((result) => {
            sceneStore.addMeasurement({
                id: result.id,
                distance: result.distance,
                start: { x: result.start.x, y: result.start.y, z: result.start.z },
                end: { x: result.end.x, y: result.end.y, z: result.end.z },
            })
        })
    } else {
        measureTool.disable()
    }

    if (toolState.value.annotationEnabled) {
        annotationTool.enable({
            onPoint: (index, point) => {
                annotationDraft.value = {
                    visible: true,
                    index,
                    text: `标注 ${index}`,
                    x: point.x,
                    y: point.y,
                    z: point.z,
                }
                nextTick(() => annotationInputRef.value?.focus?.())
            },
            onCreate: (result) => {
                syncAnnotationsFromTool()
                void persistAnnotation(result)
            },
        })
    } else {
        annotationTool.disable()
        cancelAnnotation()
    }

    selectionManager.setEnabled(!(toolState.value.measureEnabled || toolState.value.annotationEnabled))
}

function toggleClipTool() {
    sceneStore.activateTool(toolState.value.clipEnabled ? null : 'clip')
}

function toggleMeasureTool() {
    sceneStore.activateTool(toolState.value.measureEnabled ? null : 'measure')
}

function toggleAnnotationTool() {
    sceneStore.activateTool(toolState.value.annotationEnabled ? null : 'annotation')
}

function toggleOutline() {
    outlineEnabled.value = !outlineEnabled.value
    rendererManager?.setOutlineEnabled(outlineEnabled.value)
}

function toggleBoundingBox() {
    if (!boundingBoxTool) return
    boundingBoxEnabled.value = boundingBoxTool.toggle()
}

function onClipHeightChange(value: number | undefined) {
    sceneStore.setClipHeight(typeof value === 'number' ? value : 0)
}

// ==================== 工具箱 ====================

/** 默认展开的工具分组;可用 ?toolbox=settlement 直接打开某组(便于演示/截图) */
const initialToolGroup = new URLSearchParams(location.search).get('toolbox') || 'strata'

/** 项目/catalog 建议的竖向夸张基准(通常 20),作为滑块“默认”与倍率分母 */
const baseVerticalScale = computed(
    () => coordinateOrigin.value?.verticalScale || BOREHOLE_VERTICAL_SCALE,
)

/**
 * 工具箱是纯展示组件,这里把所有视口操作的「状态 + 动作」汇总成一份描述。
 * 好处:控件增删只改这一处,SceneToolbox 不需要知道任何三维逻辑;
 * 也把原先贴在视口顶部的一长条按钮(会和其它浮层抢位置)收进一个竖向导航。
 */
const toolGroups = computed<ToolGroup[]>(() => [
    {
        key: 'model', label: '模型', icon: 'FolderOpened',
        controls: [
            {
                kind: 'action', label: '加载本地 .glb', icon: 'Plus', event: 'load-file',
                primary: true, disabled: isLoading.value
            },
            { kind: 'action', label: '重置视角', icon: 'RefreshRight', event: 'reset-camera' },
            { kind: 'note', text: '也可以把 <b>.glb</b> 直接拖进场景加载。' },
        ],
    },
    {
        key: 'view', label: '视角', icon: 'View', engaged: rotateXAxisEnabled.value,
        controls: [
            { kind: 'action', label: '重置视角 / 适配全场景', icon: 'RefreshRight', event: 'reset-camera' },
            { kind: 'switch', label: '旋转 X 轴（高程朝上）', value: rotateXAxisEnabled.value, event: 'rotate-x' },
            { kind: 'note', text: '关闭后 X 轴水平、Z 轴朝上（三维软件习惯）。' },
        ],
    },
    {
        key: 'scale', label: '竖向比例', icon: 'ScaleToOriginal',
        engaged: Math.abs(verticalScale.value - baseVerticalScale.value) > 1e-6,
        controls: [
            {
                kind: 'slider', label: '竖向夸张倍数', value: verticalScale.value,
                display: `${verticalScale.value}×`, min: 1, max: 120, step: 1,
                event: 'vertical-scale'
            },
            {
                kind: 'segment', label: '快速设定', value: String(verticalScale.value),
                options: [{ value: '1', label: '1×' }, { value: String(baseVerticalScale.value), label: '默认' },
                { value: '50', label: '50×' }, { value: '100', label: '100×' }],
                event: 'vertical-scale-preset'
            },
            {
                kind: 'stats', items: [
                    { label: '真实米制', value: '1 : 1' },
                    { label: '当前竖向', value: `${verticalScale.value}×` },
                    { label: '平面方向', value: '不变' },
                ]
            },
            {
                kind: 'note', text: '只拉高竖向，X/Y 不受影响。' +
                    '分层、钻孔、井巷与<b>沉陷位移</b>会同步缩放（位移作用在几何空间，' +
                    '跟随父节点比例）。设回 <b>' + baseVerticalScale.value + '×</b> 即为数据推荐值。'
            },
        ],
    },
    {
        key: 'strata', label: '地层', icon: 'Files', engaged: stratumExploded.value,
        controls: [
            {
                kind: 'switch', label: stratumExploded.value ? '炸开中（关闭则还原）' : '炸开层位',
                value: stratumExploded.value, event: 'explode'
            },
            {
                kind: 'slider', label: '炸开间距', value: toolState.value.explodeGap,
                display: String(toolState.value.explodeGap), min: 0, max: 5000, step: 50,
                event: 'explode-gap', disabled: !stratumExploded.value
            },
            { kind: 'switch', label: '显示地层边缘线', value: showEdges.value, event: 'show-edges' },
        ],
    },
    {
        key: 'clip', label: '剖切', icon: 'Scissor', engaged: toolState.value.clipEnabled,
        controls: [
            { kind: 'switch', label: '启用剖切', value: toolState.value.clipEnabled, event: 'clip' },
            {
                kind: 'segment', label: '剖切轴', value: toolState.value.clipAxis,
                options: [{ value: 'x', label: 'X' }, { value: 'y', label: 'Y' }, { value: 'z', label: 'Z' }],
                event: 'clip-axis', disabled: !toolState.value.clipEnabled
            },
            {
                kind: 'slider', label: '位置', value: toolState.value.clipHeight,
                display: formatClipPosition.value, min: clipRange.value.min, max: clipRange.value.max,
                step: clipStep.value, event: 'clip-height', disabled: !toolState.value.clipEnabled
            },
            {
                kind: 'segment', label: '保留', value: toolState.value.clipKeepLower ? 'lower' : 'upper',
                options: [{ value: 'lower', label: '下半' }, { value: 'upper', label: '上半' }],
                event: 'clip-keep', disabled: !toolState.value.clipEnabled
            },
        ],
    },
    {
        key: 'display', label: '显示', icon: 'MagicStick',
        engaged: hoverEnabled.value || outlineEnabled.value || boundingBoxEnabled.value || boundaryEnabled.value,
        controls: [
            { kind: 'switch', label: '悬停标签', value: hoverEnabled.value, event: 'hover' },
            { kind: 'switch', label: '描边', value: outlineEnabled.value, event: 'outline' },
            { kind: 'switch', label: '坐标盒', value: boundingBoxEnabled.value, event: 'bounding-box' },
            { kind: 'switch', label: '矿区边界', value: boundaryEnabled.value, event: 'boundary' },
            { kind: 'switch', label: '地层图例', value: legendEnabled.value, event: 'legend' },
            ...(boundaryEnabled.value && !boundariesData.value
                ? [{ kind: 'note' as const, text: '矿区边界数据尚未加载（仅项目模式可用）。', warn: true }]
                : []),
        ],
    },
    {
        key: 'measure', label: '测量', icon: 'Aim', engaged: toolState.value.measureEnabled,
        controls: [
            { kind: 'switch', label: '启用测量', value: toolState.value.measureEnabled, event: 'measure' },
            {
                kind: 'readout', label: '最近测量',
                value: lastMeasurementDistance.value === null
                    ? '—' : `${lastMeasurementDistance.value.toFixed(2)} m`
            },
            { kind: 'readout', label: '历史记录', value: `${measurements.value.length} 条` },
            {
                kind: 'action', label: '清空测量', icon: 'Delete', event: 'clear-measurements',
                disabled: !measurements.value.length
            },
            { kind: 'note', text: '开启后在场景中依次点击两点即可量距。' },
        ],
    },
    {
        key: 'annotation', label: '标注', icon: 'EditPen', engaged: toolState.value.annotationEnabled,
        controls: [
            { kind: 'switch', label: '启用标注', value: toolState.value.annotationEnabled, event: 'annotation' },
            { kind: 'action', label: '清空标注', icon: 'Delete', event: 'clear-annotations' },
            { kind: 'note', text: '开启后点击场景中的点位即可输入标注文字。' },
        ],
    },
    {
        key: 'analysis', label: '分析', icon: 'DataAnalysis',
        engaged: virtualBoreholeActive.value,
        controls: [
            {
                kind: 'action',
                label: virtualBoreholeActive.value ? '虚拟钻孔（点击场景取点）' : '虚拟钻孔查询',
                icon: 'Search', event: 'virtual-borehole', primary: true,
            },
            { kind: 'note', text: '单击场景平面位置，按邻近钻孔 <b>IDW 插值</b>生成虚拟钻孔柱状。' },
            ...(virtualBoreholeActive.value
                ? [{ kind: 'note' as const, text: '查询中：单击场景取点；再次点击上方按钮退出。' }]
                : []),
        ],
    },
    {
        key: 'settlement', label: '沉陷', icon: 'Odometer', toggleable: true, engaged: settlementStore.enabled,
        controls: [
            {
                kind: 'switch', label: '启用沉陷对比', value: settlementStore.enabled, event: 'settlement-toggle',
                disabled: settlementStore.loading
            },
            {
                kind: 'slider', label: '变形进程（0=沉陷前）', value: settlementStore.timePercent,
                display: `${settlementStore.timePercent}%`, min: 0, max: 100, step: 1,
                event: 'settlement-time', disabled: !settlementStore.enabled
            },
            {
                kind: 'slider', label: '沉陷夸大（纯显示）', value: settlementStore.exaggeration,
                display: `${settlementStore.exaggeration}×`, min: 1, max: 50, step: 1,
                event: 'settlement-exaggeration', disabled: !settlementStore.enabled
            },
            {
                kind: 'segment', label: '着色', value: settlementStore.colorMode,
                options: [{ value: 'original', label: '地层' }, { value: 'dz', label: '沉降' },
                { value: 'magnitude', label: '位移' }],
                event: 'settlement-color', disabled: !settlementStore.enabled
            },
            {
                kind: 'action', label: '沉陷前（t=0）', event: 'settlement-before',
                disabled: !settlementStore.enabled
            },
            {
                kind: 'action', label: '沉陷后（t=1）', event: 'settlement-after',
                disabled: !settlementStore.enabled
            },
            {
                kind: 'stats', items: [
                    { label: '最大沉降', value: `${settlementStore.maxSubsidenceM.toFixed(2)} m` },
                    { label: '最大水平', value: `${settlementStore.maxHorizontalM.toFixed(2)} m` },
                    { label: '绑定层数', value: String(settlementStore.boundLayers) },
                ]
            },
            {
                kind: 'note',
                text: '数据为真实米制。场景竖向 <b>' + verticalScale.value + '×</b>' +
                    '，再叠加沉陷夸大 <b>' + settlementStore.exaggeration + '×</b>' +
                    '，竖向上共放大约 <b>' + (verticalScale.value * settlementStore.exaggeration) + '×</b>。' +
                    (settlementStore.workingsFollow ? '' : ' 巷道与工作面<b>不随沉陷移动</b>。')
            },
            ...(settlementStore.enabled && !settlementStore.boundLayers
                ? [{
                    kind: 'note' as const,
                    text: settlementStore.bindIssues.length
                        ? '未绑定到地层：' + settlementStore.bindIssues
                            .map(i => `<b>${i.label}</b> ${i.detail}`).join('；')
                        : '尚未绑定到地层：请先加载地层模型。',
                    warn: true
                }]
                : []),
            ...(settlementStore.enabled && settlementStore.boundLayers && settlementStore.bindIssues.length
                ? [{
                    kind: 'note' as const,
                    text: '部分层未绑定：' + settlementStore.bindIssues
                        .map(i => `<b>${i.label}</b> ${i.detail}`).join('；'),
                    warn: true
                }]
                : []),
            ...(settlementStore.loadError
                ? [{ kind: 'note' as const, text: settlementStore.loadError, warn: true }]
                : []),
        ],
    },
])

function onToolEvent(event: string, payload?: any) {
    switch (event) {
        case 'rail-toggle':
            if (payload === 'settlement') {
                settlementStore.enabled = !settlementStore.enabled
                // 关闭时要清掉“未绑定”的旧原因,否则再次开启会闪现上一次的提示
                if (!settlementStore.enabled) settlementStore.bindIssues = []
            }
            break
        case 'load-file': fileInputRef.value?.click(); break
        case 'reset-camera': resetCamera(); break
        case 'rotate-x': onRotateXAxisToggle(payload); break
        case 'explode': toggleStratumExplode(); break
        case 'explode-gap': onExplodeGapChange(payload); break
        case 'show-edges': sceneStore.setShowEdges(Boolean(payload)); break
        case 'clip': toggleClipTool(); break
        case 'clip-axis': setClipAxis(payload); break
        case 'clip-height': onClipHeightChange(payload); break
        case 'clip-keep': setClipKeepLower(payload === 'lower'); break
        case 'hover': toggleHoverEffect(); break
        case 'outline': toggleOutline(); break
        case 'bounding-box': toggleBoundingBox(); break
        case 'boundary': boundaryEnabled.value = Boolean(payload); break
        case 'legend': legendEnabled.value = Boolean(payload); break
        case 'measure': toggleMeasureTool(); break
        case 'clear-measurements': clearMeasurements(); break
        case 'annotation': toggleAnnotationTool(); break
        case 'clear-annotations': clearAnnotations(); break
        case 'virtual-borehole': toggleVirtualBorehole(); break
        case 'settlement-toggle':
            settlementStore.enabled = Boolean(payload)
            // 关闭时要清掉“未绑定”的旧原因,否则再次开启会闪现上一次的提示
            if (!settlementStore.enabled) settlementStore.bindIssues = []
            break
        case 'settlement-time': settlementStore.timePercent = Number(payload); break
        case 'settlement-exaggeration': settlementStore.exaggeration = Number(payload); break
        case 'settlement-color': settlementStore.colorMode = payload; break
        case 'settlement-before': settlementStore.time = 0; break
        case 'settlement-after': settlementStore.time = 1; break
        case 'vertical-scale': sceneStore.setVerticalScale(Number(payload)); break
        case 'vertical-scale-preset': sceneStore.setVerticalScale(Number(payload)); break
    }
}

function setClipAxis(axis: 'x' | 'y' | 'z') {
    sceneStore.setClipAxis(axis)
}

function setClipKeepLower(value: boolean | string | number) {
    sceneStore.setClipKeepLower(Boolean(value))
}

function clearMeasurements() {
    sceneStore.clearMeasurements()
    measureTool?.clear()
}

function clearAnnotations() {
    const serverIds = [...annotationServerIds.values()]
    annotationTool?.clear()
    annotationServerIds.clear()
    syncAnnotationsFromTool()
    // 项目模式下同步删除服务端持久化记录
    if (isProjectMode.value) {
        for (const id of serverIds) {
            void workspaceApi.deleteAnnotation(id).catch(() => { /* 单条失败不阻塞 */ })
        }
    }
}

// ==================== 标注持久化与镜像同步 ====================

// 本地标注 id → 服务端记录 id
const annotationServerIds = new Map<string, string>()
let restoringAnnotations = false

function syncAnnotationsFromTool() {
    const records = (annotationTool?.getResults() ?? []).map(item => ({
        id: item.id,
        text: item.text,
        position: { x: item.position.x, y: item.position.y, z: item.position.z },
        createdAt: item.createdAt,
        serverId: annotationServerIds.get(item.id) ?? null,
    }))
    sceneStore.setAnnotations(records)
}

/** 投影坐标(米) → 场景世界坐标，用于恢复持久化标注 */
function projectPointToWorld(x: number, y: number, z: number) {
    const origin = coordinateOrigin.value
    if (!origin) return new THREE.Vector3(x, y, z)
    return new THREE.Vector3(x - origin.x, (z - origin.z) * verticalScale.value, -(y - origin.y))
}

async function persistAnnotation(result: AnnotationResult) {
    if (!isProjectMode.value || restoringAnnotations) return
    const projected = worldPointToProject(result.position)
    try {
        const created = await workspaceApi.createAnnotation(String(route.params.projectId), {
            title: result.text,
            position_x: projected.x,
            position_y: projected.y,
            position_z: projected.z,
        })
        if (created) {
            annotationServerIds.set(result.id, created.id)
            syncAnnotationsFromTool()
        }
    } catch { /* 持久化失败保留本地标注 */ }
}

async function loadPersistedAnnotations() {
    if (!isProjectMode.value || !annotationTool) return
    try {
        const records = await workspaceApi.listAnnotations(String(route.params.projectId))
        restoringAnnotations = true
        for (const record of records) {
            const world = projectPointToWorld(record.position_x, record.position_y, record.position_z)
            const local = annotationTool.addAnnotation(world, record.title)
            if (local) annotationServerIds.set(local.id, record.id)
        }
    } catch { /* 拉取失败按无标注处理 */ }
    finally {
        restoringAnnotations = false
        syncAnnotationsFromTool()
    }
}

function confirmAnnotation() {
    if (!annotationDraft.value.text.trim()) return
    annotationTool?.addAnnotation(
        new THREE.Vector3(annotationDraft.value.x, annotationDraft.value.y, annotationDraft.value.z),
        annotationDraft.value.text,
    )
    annotationDraft.value.visible = false
}

function cancelAnnotation() {
    annotationDraft.value.visible = false
    annotationDraft.value.text = ''
}

// ==================== Scene Initialization ====================

async function initScene() {
    if (!canvasRef.value || !containerRef.value) return

    const { width, height } = containerRef.value.getBoundingClientRect()

    sceneManager = new SceneManager()
    cameraManager = new CameraManager(width / height)
    rendererManager = new RendererManager(canvasRef.value)
    rendererManager.setOutlineEnabled(outlineEnabled.value)
    rendererManager.resize(width, height)
    controlsManager = new ControlsManager(cameraManager.camera, canvasRef.value)
    lightManager = new LightManager(sceneManager.scene)
    modelManager = new ModelManager(sceneManager)
    highlightManager = new HighlightManager()
    layerManager = new LayerManager(modelManager)
    clipTool = new ClipTool(
        rendererManager.renderer,
        sceneManager.scene,
        {
            onPositionChange: (position) => { sceneStore.setClipHeight(position) },
            onRangeChange: (min, max) => {
                clipRange.value = { min, max }
                const span = Math.max(1, max - min)
                clipStep.value = Math.max(0.1, Number((span / 200).toFixed(2)))
            },
        }
    )
    measureTool = new MeasureTool(sceneManager.scene, cameraManager.camera, canvasRef.value)
    annotationTool = new AnnotationTool(sceneManager.scene, cameraManager.camera, canvasRef.value)
    stratumExplodeTool = new StratumExplodeTool(modelManager, { gap: toolState.value.explodeGap })

    boundaryOverlay = new BoundaryOverlay()
    sceneManager.scene.add(boundaryOverlay.group)

    if (toolState.value.clipHeight !== 0) {
        clipTool.setHeight(toolState.value.clipHeight)
    }

    selectionManager = new SelectionManager(
        cameraManager.camera,
        sceneManager.scene,
        canvasRef.value,
        highlightManager,
        (obj) => {
            if (obj) {
                sceneStore.selectObject({
                    id: obj.userData.id,
                    name: obj.userData.name,
                    type: obj.userData.type,
                    data: obj.userData.boreholeData || obj.userData.modelData || {},
                })
                rendererManager?.setOutlineSelectedObjects([obj])
            } else {
                sceneStore.selectObject(null)
                rendererManager?.setOutlineSelectedObjects([])
            }
        },
        (obj, event, point) => {
            if (!containerRef.value || !obj || !event) {
                hoverLabel.value.visible = false
                surfacePoint = null
                return
            }
            // 记录表面交点作为坐标读数的高程来源
            if (point) {
                surfacePoint = point
                surfacePointAt = performance.now()
            }
            const name = String(obj.userData?.name || obj.name || '').trim()
            if (!name) {
                hoverLabel.value.visible = false
                return
            }
            const rect = containerRef.value.getBoundingClientRect()
            hoverLabel.value.visible = true
            hoverLabel.value.name = name
            hoverLabel.value.x = event.clientX - rect.left + 14
            hoverLabel.value.y = event.clientY - rect.top + 14
        }
    )
    selectionManager.setHoverEnabled(true)
    refreshSelectionPickTargets()

    controlsManager.controls.addEventListener('start', onControlStart)
    controlsManager.controls.addEventListener('end', onControlEnd)

    // 坐标读数：指针在画布内移动时更新状态栏 X/Y/Z
    canvasRef.value.addEventListener('pointermove', onCanvasPointerMove)
    canvasRef.value.addEventListener('pointerleave', onCanvasPointerLeave)

    resizeObserver = new ResizeObserver(() => {
        if (!containerRef.value) return
        const { width: w, height: h } = containerRef.value.getBoundingClientRect()
        rendererManager.resize(w, h)
        cameraManager.updateAspect(w, h)
    })
    resizeObserver.observe(containerRef.value)

    rotateXAxisEnabled.value = sceneManager.isGeoRootRotationXEnabled()
    axisGizmoTool = new AxisGizmoTool(rendererManager.renderer, cameraManager.camera, sceneManager.geoRoot, {
        size: 110,
        padding: 12,
    })

    boundingBoxTool = new BoundingBoxTool(sceneManager.scene, modelManager, cameraManager.camera, canvasRef.value,
        () => coordinateOrigin.value, () => verticalScale.value)

    syncToolRuntimeState()
    startAnimate()
    // 恢复项目持久化标注（项目模式）
    void loadPersistedAnnotations()
    // 预取沉陷元信息(仅 4 KB),使工具箱里未启用时也能显示真实的最大沉降等读数
    void prefetchSettlementMeta()

    // 远程控制桥:开发环境或 URL 带 ?remote=1 时,把场景引擎暴露给
    // 控制台/自动化脚本(相机球坐标定位、地层颜色、剖切/炸开、PNG 截图导出等),
    // 例:__geomine.setView({ azimuth: 45, elevation: 35 }) / __geomine.capture({ background: '#ffffff' })
    disposeRemoteBridge = installRemoteControl({
        sceneManager, cameraManager, rendererManager, controlsManager, modelManager,
        getClipTool: () => clipTool,
        getExplodeTool: () => stratumExplodeTool,
        getGizmoTool: () => axisGizmoTool,
        getSceneStore: () => sceneStore,
        getSettlementStore: () => settlementStore,
        getSettlementManager: () => settlementManager,
    })
}

// ==================== Watchers ====================

watch(layerVisible, (val) => {
    layerManager.setLayerVisible('stratum', val.stratum)
    layerManager.setLayerVisible('borehole', val.borehole)
    layerManager.setLayerVisible('workingface', val.workingface)
    layerManager.setLayerVisible('roadway', val.roadway)
}, { deep: true })

watch(showEdges, (visible) => {
    layerManager.setLayerEdgesVisible('stratum', visible)
})

watch(stratumLayers, (layers) => {
    for (const layer of layers) {
        applyStratumLayerControl(layer)
    }
}, { deep: true })

// 一级图层整体透明度:钻孔/工作面/巷道直接刷材质,地层复用单元控制逻辑
watch(groupOpacity, () => {
    applyGroupOpacityToModels()
    for (const layer of stratumLayers.value) {
        applyStratumLayerControl(layer)
    }
}, { deep: true })

watch(coordinateOrigin, (origin) => {
    if (!origin || !modelManager) return
    for (const model of modelManager.getModelsByType('stratum')) {
        if (model.object.userData.coordinateMode !== 'projected') {
            alignProjectedModel(model.object)
        }
    }
    boundingBoxTool?.refresh()
    rebuildBoundaryOverlay()
    void ensureBoundaries()
})

// 沉陷对比:启用 → 拉位移场并绑定;参数变化 → 同步到几何
watch(() => settlementStore.enabled, async (enabled) => {
    if (!enabled) {
        syncSettlementBinding()
        return
    }
    const ok = await ensureSettlementField()
    if (ok) syncSettlementBinding()
})

watch(
    () => [settlementStore.time, settlementStore.exaggeration, settlementStore.colorMode] as const,
    ([t, ex, mode]) => {
        if (!settlementManager || !settlementStore.enabled) return
        settlementManager.setExaggeration(ex)
        settlementManager.setColorMode(mode)
        settlementManager.setTime(t)
        settlementStore.appliedMaxDz = settlementManager.appliedMaxDz
        if (toolState.value.clipEnabled) syncToolRuntimeState()
    },
)

// 竖向夸张：全场景统一乘在 geoRoot 上。
// 各模型已自带基准倍数(metadata.vertical_scale, 通常 20),这里再乘一个倍率,
// 所以一次调整能同时作用于分层、钻孔、井巷与沉陷位移,不会双重缩放。
watch(verticalScale, (value) => {
    const base = coordinateOrigin.value?.verticalScale || BOREHOLE_VERTICAL_SCALE
    sceneManager?.setVerticalScaleMultiplier(value / base)
    // 世界空间的范围与位移随比例变化
    boundingBoxTool?.refresh()
    stratumExplodeTool?.sync()
    if (toolState.value.clipEnabled) syncToolRuntimeState()
    // 刻意**不**自动重新取景:若相机随比例一起退后,模型看上去大小不变,
    // 滑块就失去意义了。需要时用户点工具箱里的“重置视角”。
})

watch(() => toolState.value.clipHeight, (height) => {
    if (clipTool && Math.abs(clipTool.getHeight() - height) > 1e-6) {
        clipTool.setHeight(height)
    }
})

watch(() => toolState.value.explodeGap, (gap) => {
    stratumExplodeTool?.setGap(gap)
})

watch(
    () => ({
        clipEnabled: toolState.value.clipEnabled,
        measureEnabled: toolState.value.measureEnabled,
        annotationEnabled: toolState.value.annotationEnabled,
        clipHeight: toolState.value.clipHeight,
        clipAxis: toolState.value.clipAxis,
        clipKeepLower: toolState.value.clipKeepLower,
    }),
    () => { syncToolRuntimeState() },
    { deep: true }
)

watch(loadRequest, (req) => {
    if (req) {
        loadModelByRequest(req)
    }
})

watch(unloadRequest, (req) => {
    if (req) {
        unloadModelByRequest(req)
    }
})

// 面板（柱状图等）请求聚焦某个地层
watch(() => sceneStore.focusRequest, (req) => {
    if (req) {
        focusStratum(req.layerName)
    }
})

// 管理面板请求单条删除测量：移除图元 + 同步记录列表
watch(() => sceneStore.measurementRemoveRequest, (req) => {
    if (!req) return
    measureTool?.remove(req.id)
    sceneStore.removeMeasurement(req.id)
})

// 管理面板请求单条删除标注：移除图元 + 同步镜像 + 删除服务端记录
watch(() => sceneStore.annotationRemoveRequest, (req) => {
    if (!req) return
    const serverId = annotationServerIds.get(req.id)
        ?? sceneStore.annotations.find(item => item.id === req.id)?.serverId
        ?? null
    annotationTool?.remove(req.id)
    annotationServerIds.delete(req.id)
    syncAnnotationsFromTool()
    if (serverId && isProjectMode.value) {
        void workspaceApi.deleteAnnotation(serverId).catch(() => { /* 忽略单条失败 */ })
    }
})

// ==================== Lifecycle ====================

onMounted(() => { initScene() })

onActivated(() => {
    startAnimate()
    if (hoverEnabled.value) {
        selectionManager?.setHoverEnabled(true)
    }
    if (!containerRef.value) return
    const { width, height } = containerRef.value.getBoundingClientRect()
    rendererManager?.resize(width, height)
    cameraManager?.updateAspect(width, height)
})

onDeactivated(() => {
    stopAnimate()
    selectionManager?.setHoverEnabled(false)
    hideHoverLabel()
})

onUnmounted(() => {
    disposeRemoteBridge?.()
    disposeRemoteBridge = null
    canvasRef.value?.removeEventListener('pointermove', onCanvasPointerMove)
    canvasRef.value?.removeEventListener('pointerleave', onCanvasPointerLeave)
    canvasRef.value?.removeEventListener('click', onVirtualBoreholeClick)
    clearVirtualMarker()
    sceneStore.activateTool(null)
    sceneStore.resetSceneSession()
    boundaryOverlay?.dispose()
    boundaryOverlay = null
    // geoRoot 随画布销毁,竖向倍率也要回默认,否则下次进来状态不一致
    sceneStore.resetVerticalScale()
    settlementManager?.restoreBase()
    settlementManager?.detach()
    settlementManager = null
    settlementStore.resetSession()
    stopAnimate()
    resizeObserver?.disconnect()
    clipTool?.dispose()
    measureTool?.dispose()
    annotationTool?.dispose()
    stratumExplodeTool?.dispose()
    controlsManager?.controls.removeEventListener('start', onControlStart)
    controlsManager?.controls.removeEventListener('end', onControlEnd)
    selectionManager?.dispose()
    controlsManager?.dispose()
    rendererManager?.dispose()
    highlightManager?.dispose()
    axisGizmoTool?.dispose()
    axisGizmoTool = null
    boundingBoxTool?.dispose()
    boundingBoxTool = null
    modelManager?.clear()
    sceneManager?.dispose()
    hideHoverLabel()
})

// 供工作台外壳（GeoWorkspaceView）调用：截图、场景保存/恢复、地层聚焦
defineExpose({
    captureImage,
    getSceneState,
    applySceneState,
    focusStratum,
})
</script>

<style scoped>
.scene-canvas {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
}

.canvas {
    display: block;
    width: 100%;
    height: 100%;
}


.measure-chip {
    position: absolute;
    top: 64px;
    right: 12px;
    padding: 6px 10px;
    border: 1px solid rgba(0, 200, 255, 0.35);
    border-radius: 10px;
    background: rgba(15, 36, 71, 0.85);
    color: #dff8ff;
    font-size: 12px;
    backdrop-filter: blur(6px);
}

/* ── 地层颜色图例 ── */
.strata-legend {
    position: absolute;
    left: 12px;
    bottom: 44px;
    z-index: 9;
    min-width: 148px;
    max-width: 210px;
    max-height: 46%;
    display: flex;
    flex-direction: column;
    border: 1px solid #333c34;
    background: rgba(16, 21, 17, 0.92);
    backdrop-filter: blur(8px);
    color: #cfd6ce;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.3);
}

.strata-legend .lg-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    padding: 7px 10px;
    border: 0;
    background: transparent;
    color: inherit;
    cursor: pointer;
}

.strata-legend .lg-head span {
    font: 8px Bahnschrift, sans-serif;
    letter-spacing: 0.14em;
    color: #b98548;
}

.strata-legend .lg-head b {
    font-size: 10px;
    color: #aeb6ad;
    font-weight: 400;
}

.strata-legend .lg-body {
    overflow: auto;
    padding: 0 10px 8px;
}

.strata-legend .lg-row {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 2px 0;
    font-size: 10px;
    color: #b9c1b8;
    white-space: nowrap;
}

.strata-legend .lg-row i {
    width: 12px;
    height: 8px;
    flex-shrink: 0;
    border: 1px solid rgba(255, 255, 255, 0.25);
}

/* ── 虚拟钻孔结果卡 ── */
.virtual-card {
    position: absolute;
    right: 12px;
    top: 64px;
    z-index: 9;
    width: 230px;
    max-height: 56%;
    display: flex;
    flex-direction: column;
    padding: 9px 11px 10px;
    border: 1px solid #2f4a52;
    background: rgba(13, 22, 24, 0.94);
    backdrop-filter: blur(8px);
    color: #cfe2e4;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.35);
}

.virtual-card .vc-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
}

.virtual-card .vc-head span {
    font: 8px Bahnschrift, sans-serif;
    letter-spacing: 0.14em;
    color: #5fb7c4;
}

.virtual-card .vc-head button {
    border: 0;
    background: transparent;
    color: #7d8d90;
    cursor: pointer;
    font-size: 13px;
}

.virtual-card strong {
    margin: 4px 0 2px;
    font-size: 13px;
    color: #e4f0f1;
}

.virtual-card small {
    color: #77909a;
    font-size: 9px;
}

.virtual-card .vc-layers {
    flex: 1;
    min-height: 0;
    overflow: auto;
    margin-top: 7px;
}

.virtual-card .vc-layer {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 0;
    font-size: 10px;
}

.virtual-card .vc-layer i {
    width: 12px;
    height: 8px;
    flex-shrink: 0;
    border: 1px solid rgba(255, 255, 255, 0.25);
}

.virtual-card .vc-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #c3d4d6;
}

.virtual-card .vc-depth {
    color: #7d99a1;
    font-family: Consolas, monospace;
}

.virtual-card .vc-empty {
    padding: 12px 0;
    text-align: center;
    color: #77878a;
    font-size: 10px;
}

.virtual-card .vc-actions {
    display: flex;
    gap: 8px;
    margin-top: 9px;
}

.virtual-card .vc-actions button {
    flex: 1;
    padding: 5px 0;
    border: 1px solid #37525a;
    background: #16333a;
    color: #9fd4dd;
    font-size: 11px;
    cursor: pointer;
}

.virtual-card .vc-actions button:disabled {
    opacity: .4;
    cursor: not-allowed;
}

.virtual-card .vc-actions button:hover:not(:disabled) {
    background: #1d434c;
}

/* ── 沉陷对比图例 ── */
.settlement-legend {
    position: absolute;
    top: 12px;
    left: 12px;
    z-index: 9;
    width: 212px;
    padding: 9px 11px 10px;
    border: 1px solid #333c34;
    background: rgba(16, 21, 17, 0.92);
    backdrop-filter: blur(8px);
    color: #cfd6ce;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.3);
}

.settlement-legend .sl-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 7px;
}

.settlement-legend .sl-head span {
    font: 8px Bahnschrift, sans-serif;
    letter-spacing: 0.14em;
    color: #b98548;
}

.settlement-legend .sl-head b {
    font-size: 10px;
    color: #e2ddcf;
}

.settlement-legend .sl-bar {
    height: 10px;
    border: 1px solid #2b322c;
    background: linear-gradient(90deg, hsl(223, 72%, 30%), hsl(149, 72%, 41%), hsl(74, 72%, 51%), hsl(0, 72%, 62%));
}

.settlement-legend .sl-scale {
    display: flex;
    justify-content: space-between;
    margin-top: 3px;
    font-size: 9px;
    color: #9aa39b;
}

.settlement-legend .sl-note {
    margin-top: 6px;
    font-size: 9px;
    color: #69736b;
}

.entity-hover-label {
    position: absolute;
    z-index: 12;
    pointer-events: none;
    max-width: 320px;
    padding: 6px 10px;
    border: 1px solid rgba(0, 200, 255, 0.45);
    border-radius: 8px;
    background: rgba(6, 16, 30, 0.9);
    color: #eaf8ff;
    font-size: 12px;
    line-height: 1.25;
    white-space: nowrap;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.32);
}

@media (max-width: 900px) {

    .measure-chip {
        top: auto;
        bottom: 56px;
        right: 12px;
    }

    .entity-hover-label {
        font-size: 11px;
        max-width: 240px;
    }
}

/* ── 拖放加载遮罩 ── */
.drop-overlay {
    position: absolute;
    inset: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(6, 16, 30, 0.75);
    backdrop-filter: blur(4px);
    border: 2px dashed rgba(0, 200, 255, 0.6);
    border-radius: 8px;
}

.drop-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 32px 48px;
    border-radius: 12px;
    background: rgba(10, 22, 40, 0.85);
    border: 1px solid rgba(0, 200, 255, 0.35);
}

.drop-icon {
    font-size: 36px;
    color: rgba(0, 200, 255, 0.8);
    line-height: 1;
}

.drop-text {
    font-size: 15px;
    color: #d9f4ff;
    white-space: nowrap;
}

/* ── 模型加载中遮罩 ── */
.loading-overlay {
    position: absolute;
    inset: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(6, 16, 30, 0.7);
    backdrop-filter: blur(3px);
    border-radius: 8px;
}

.loading-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 32px 48px;
    border-radius: 12px;
    background: rgba(10, 22, 40, 0.9);
    border: 1px solid rgba(0, 200, 255, 0.3);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(0, 200, 255, 0.15);
    border-top-color: var(--color-accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.loading-text {
    font-size: 14px;
    color: #d9f4ff;
    white-space: nowrap;
}

.drop-error {
    position: absolute;
    bottom: 20px;
    left: 50%;
    z-index: 100;
    transform: translateX(-50%);
    padding: 8px 20px;
    border-radius: 8px;
    background: rgba(200, 40, 40, 0.9);
    color: #fff;
    font-size: 13px;
    white-space: nowrap;
    pointer-events: none;
    backdrop-filter: blur(4px);
}

.annotation-composer {
    position: absolute;
    z-index: 110;
    left: 22px;
    bottom: 24px;
    width: 310px;
    padding: 14px;
    border: 1px solid #7b5b33;
    background: rgba(18, 23, 20, .96);
    box-shadow: 0 18px 46px rgba(0, 0, 0, .46);
    color: #d9d7ce;
}

.annotation-composer__head,
.annotation-composer__actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.annotation-composer__head span {
    color: #b98548;
    font: 9px Bahnschrift, sans-serif;
    letter-spacing: .15em;
}

.annotation-composer__head button,
.annotation-composer__actions button {
    border: 0;
    background: transparent;
    color: #777f78;
    cursor: pointer;
}

.annotation-composer strong {
    display: block;
    margin-top: 10px;
    font-size: 13px;
}

.annotation-composer small {
    display: block;
    margin: 4px 0 12px;
    color: #687169;
    font: 9px Bahnschrift, sans-serif;
}

.annotation-composer__actions {
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
}

.annotation-composer__actions button {
    padding: 7px 11px;
    border: 1px solid #353d36;
}

.annotation-composer__actions .confirm {
    border-color: #8c6638;
    background: #714d29;
    color: #f0dfc7;
}

@media (max-width: 900px) {
    .drop-text {
        font-size: 13px;
    }

    .drop-icon {
        font-size: 28px;
    }

    .loading-card {
        padding: 24px 32px;
        gap: 12px;
    }

    .loading-spinner {
        width: 32px;
        height: 32px;
    }

    .loading-text {
        font-size: 12px;
    }
}
</style>
