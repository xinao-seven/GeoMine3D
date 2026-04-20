<template>
    <div ref="containerRef" class="scene-canvas">
        <canvas ref="canvasRef" class="canvas" />

        <div class="tools-bar">
            <div class="tools-group">
                <el-tooltip content="重置视角" placement="bottom">
                    <el-button class="tool-btn" @click="resetCamera">
                        <el-icon>
                            <RefreshRight />
                        </el-icon>
                        <span>重置视角</span>
                    </el-button>
                </el-tooltip>

                <el-tooltip :content="stratumExploded ? '还原地层位置' : '炸开地层层位'" placement="bottom">
                    <el-button class="tool-btn" :class="{ active: stratumExploded }" @click="toggleStratumExplode">
                        {{ stratumExploded ? '还原' : '炸开' }}
                    </el-button>
                </el-tooltip>
            </div>

            <div class="tools-divider" />

            <div class="tools-group">
                <el-tooltip :content="toolState.clipEnabled ? '关闭剖切' : '开启剖切'" placement="bottom">
                    <el-button class="tool-btn" :class="{ active: toolState.clipEnabled }" @click="toggleClipTool">
                        <el-icon>
                            <Scissor />
                        </el-icon>
                        <span>剖切</span>
                    </el-button>
                </el-tooltip>

                <div v-if="toolState.clipEnabled" class="clip-control">
                    <div class="clip-axis-row">
                        <el-button
                            class="axis-btn"
                            :class="{ active: toolState.clipAxis === 'x' }"
                            @click="setClipAxis('x')"
                        >X</el-button>
                        <el-button
                            class="axis-btn"
                            :class="{ active: toolState.clipAxis === 'y' }"
                            @click="setClipAxis('y')"
                        >Y</el-button>
                        <el-button
                            class="axis-btn"
                            :class="{ active: toolState.clipAxis === 'z' }"
                            @click="setClipAxis('z')"
                        >Z</el-button>
                    </div>
                    <span class="clip-label">位置 {{ toolState.clipHeight.toFixed(2) }}</span>
                    <el-slider
                        :model-value="toolState.clipHeight"
                        :min="clipRange.min"
                        :max="clipRange.max"
                        :step="clipStep"
                        size="small"
                        @update:model-value="onClipHeightChange"
                    />
                    <div class="clip-flags">
                        <el-switch
                            :model-value="toolState.clipKeepLower"
                            inline-prompt
                            active-text="留低"
                            inactive-text="留高"
                            @update:model-value="setClipKeepLower"
                        />
                        <el-switch
                            :model-value="toolState.clipHelperVisible"
                            inline-prompt
                            active-text="辅助面"
                            inactive-text="隐藏"
                            @update:model-value="setClipHelperVisible"
                        />
                    </div>
                </div>
            </div>

            <div class="tools-divider" />

            <div class="tools-group axis-toggle-group">
                <span class="axis-toggle-label">旋转X</span>
                <el-switch
                    :model-value="rotateXAxisEnabled"
                    inline-prompt
                    active-text="开"
                    inactive-text="关"
                    @update:model-value="onRotateXAxisToggle"
                />
            </div>

            <div class="tools-group">
                <el-tooltip :content="toolState.measureEnabled ? '关闭测量' : '开启测量'" placement="bottom">
                    <el-button class="tool-btn" :class="{ active: toolState.measureEnabled }" @click="toggleMeasureTool">
                        <el-icon>
                            <Aim />
                        </el-icon>
                        <span>测量</span>
                    </el-button>
                </el-tooltip>

                <el-button class="tool-btn ghost" :disabled="!measurements.length" @click="clearMeasurements">
                    清空
                </el-button>
            </div>

            <div class="tools-group">
                <el-tooltip :content="toolState.annotationEnabled ? '关闭标注' : '开启标注'" placement="bottom">
                    <el-button
                        class="tool-btn"
                        :class="{ active: toolState.annotationEnabled }"
                        @click="toggleAnnotationTool"
                    >
                        <el-icon>
                            <EditPen />
                        </el-icon>
                        <span>标注</span>
                    </el-button>
                </el-tooltip>

                <el-button class="tool-btn ghost" @click="clearAnnotations">
                    清空
                </el-button>
            </div>
        </div>

        <div v-if="lastMeasurementDistance !== null" class="measure-chip">
            最近测量 {{ lastMeasurementDistance.toFixed(2) }} m
        </div>

        <div
            v-if="hoverLabel.visible"
            class="entity-hover-label"
            :style="{ left: `${hoverLabel.x}px`, top: `${hoverLabel.y}px` }"
        >
            {{ hoverLabel.name }}
        </div>

    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, onActivated, onDeactivated, watch } from 'vue'
import * as THREE from 'three'
import { SceneManager } from '@/three/core/SceneManager'
import { CameraManager } from '@/three/core/CameraManager'
import { RendererManager } from '@/three/core/RendererManager'
import { ControlsManager } from '@/three/core/ControlsManager'
import { LightManager } from '@/three/core/LightManager'
import { ModelManager, type ManagedModel } from '@/three/managers/ModelManager'
import { LayerManager } from '@/three/managers/LayerManager'
import { HighlightManager } from '@/three/managers/HighlightManager'
import { SelectionManager } from '@/three/managers/SelectionManager'
import { StratumModelLoader } from '@/three/loaders/StratumModelLoader'
import { BoreholeModelLoader } from '@/three/loaders/BoreholeModelLoader'
import { WorkingFaceModelLoader } from '@/three/loaders/WorkingFaceModelLoader'
import { ClipTool } from '@/three/tools/ClipTool'
import { MeasureTool } from '@/three/tools/MeasureTool'
import { AnnotationTool } from '@/three/tools/AnnotationTool'
import { StratumExplodeTool } from '@/three/tools/StratumExplodeTool'
import { AxisGizmoTool } from '@/three/tools/AxisGizmoTool'
import { modelApi, boreholeApi } from '@/api'
import { useSceneStore, useBoreholeStore } from '@/stores'
import { storeToRefs } from 'pinia'
import type { ModelItem, BoreholeItem, StratumLayerControl } from '@/types'
import type { ModelLoadRequest } from '@/stores/sceneStore'

const sceneStore = useSceneStore()
const boreholeStore = useBoreholeStore()
const {
    layerVisible,
    opacity,
    locateTarget,
    loadRequest,
    showEdges,
    stratumLayers,
    toolState,
    measurements,
    lastMeasurementDistance,
} = storeToRefs(sceneStore)
const BOREHOLE_VERTICAL_SCALE = 20

const containerRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const clipRange = ref({ min: -1000, max: 1000 })
const clipStep = ref(1)
const rotateXAxisEnabled = ref(true)
const stratumExploded = ref(false)
const hoverLabel = ref({
    visible: false,
    name: '',
    x: 0,
    y: 0,
})
const STRATUM_EXPLODE_GAP = 1000

let sceneManager: SceneManager
let cameraManager: CameraManager
let rendererManager: RendererManager
let controlsManager: ControlsManager
let lightManager: LightManager
let modelManager: ModelManager
let layerManager: LayerManager
let highlightManager: HighlightManager
let axisGizmoTool: AxisGizmoTool | null = null
let selectionManager: SelectionManager
let clipTool: ClipTool
let measureTool: MeasureTool
let annotationTool: AnnotationTool
let stratumExplodeTool: StratumExplodeTool | null = null
let animFrameId: number
let resizeObserver: ResizeObserver
let isAnimating = false

// 初始化 three 场景、管理器、工具与交互绑定。
async function initScene() {
    if (!canvasRef.value || !containerRef.value) return

    const { width, height } = containerRef.value.getBoundingClientRect()

    sceneManager = new SceneManager()
    cameraManager = new CameraManager(width / height)
    rendererManager = new RendererManager(canvasRef.value)
    rendererManager.resize(width, height)
    controlsManager = new ControlsManager(cameraManager.camera, canvasRef.value)
    lightManager = new LightManager(sceneManager.scene)
    modelManager = new ModelManager(sceneManager)
    layerManager = new LayerManager(modelManager)
    highlightManager = new HighlightManager()
    clipTool = new ClipTool(
        rendererManager.renderer,
        sceneManager.scene,
        {
            //滑块位置的回调
            onPositionChange: (position) => {
                sceneStore.setClipHeight(position)
            },
            //滑块范围回调
            onRangeChange: (min, max) => {
                clipRange.value = { min, max }
                const span = Math.max(1, max - min)
                clipStep.value = Math.max(0.1, Number((span / 200).toFixed(2)))
            },
        }
    )
    measureTool = new MeasureTool(sceneManager.scene, cameraManager.camera, canvasRef.value)
    annotationTool = new AnnotationTool(sceneManager.scene, cameraManager.camera, canvasRef.value)
    stratumExplodeTool = new StratumExplodeTool(modelManager, { gap: STRATUM_EXPLODE_GAP })

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
            } else {
                sceneStore.selectObject(null)
            }
        },
        (obj, event) => {
            if (!containerRef.value || !obj || !event) {
                hoverLabel.value.visible = false
                return
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

    syncToolRuntimeState()
    startAnimate()
}

// 动画主循环：更新控制器、灯光与渲染。
function animate() {
    if (!isAnimating) return
    animFrameId = requestAnimationFrame(animate)
    controlsManager.update()
    annotationTool?.update()
    lightManager.updateFromCamera(cameraManager.camera)
    rendererManager.render(sceneManager.scene, cameraManager.camera)
    axisGizmoTool?.render()
}

// 启动动画循环。
function startAnimate() {
    if (isAnimating) return
    isAnimating = true
    animate()
}

// 停止动画循环。
function stopAnimate() {
    if (!isAnimating) return
    isAnimating = false
    cancelAnimationFrame(animFrameId)
}

// 使用模型管理器维护可拾取对象白名单，避免全场景递归拾取。
function refreshSelectionPickTargets() {
    if (!selectionManager || !modelManager) return
    selectionManager.setPickTargets(modelManager.getAllModels().map((item) => item.object))
}

// 按请求类型加载对应模型并更新相机与状态。
async function loadModelByRequest(req: ModelLoadRequest) {
    try {
        let preferImmediateFocus = false
        let focusType: 'stratum' | 'borehole' | 'workingface' | null = null

        if (req.type === 'stratum') {
            const model = req.model || await findModelById('stratum', req.id)
            if (!model) throw new Error(`未找到地层模型: ${req.id}`)
            await loadStratumModel(model)
            focusType = 'stratum'
        }

        if (req.type === 'workingface') {
            const model = req.model || await findModelById('workingface', req.id)
            if (!model) throw new Error(`未找到工作面模型: ${req.id}`)
            await loadWorkingFaceModel(model)
            focusType = 'workingface'
        }

        if (req.type === 'borehole') {
            if (req.id === '__all__') {
                const boreholes = req.boreholeList && req.boreholeList.length
                    ? req.boreholeList
                    : await boreholeApi.getBoreholeList()
                boreholeStore.list = boreholes
                await loadAllBoreholeModels(boreholes)
                focusType = 'borehole'
                preferImmediateFocus = true
            } else {
                let borehole = req.borehole
                let index = req.index ?? 0
                if (!borehole) {
                    const boreholes = await boreholeApi.getBoreholeList()
                    const foundIndex = boreholes.findIndex((item) => item.id === req.id)
                    if (foundIndex === -1) throw new Error(`未找到钻孔: ${req.id}`)
                    borehole = boreholes[foundIndex]
                    index = foundIndex
                    boreholeStore.list = boreholes
                }
                await loadBoreholeModel(borehole, index)
                focusType = 'borehole'
                preferImmediateFocus = true
            }
        }

        sceneManager.removeGrid()
        refreshSelectionPickTargets()
        sceneStore.setModelLoadStatus(req.type, req.id, { loaded: true, loading: false })

        if (focusType) {
            fitCameraToType(focusType, preferImmediateFocus)
        } else {
            fitCameraToType(null, preferImmediateFocus)
        }

        if (toolState.value.clipEnabled) {
            syncToolRuntimeState()
        }
    } catch (err) {
        sceneStore.setModelLoadStatus(req.type, req.id, { loading: false })
        console.error(`[SceneCanvas] ${req.type} 模型加载失败`, err)
    }
}

// 按模型类型聚焦相机。
function fitCameraToType(type: 'stratum' | 'borehole' | 'workingface' | null, immediate = false) {
    let models: ManagedModel[] = []
    if (type !== null) {
        models = modelManager.getModelsByType(type)
    } else {
        models = modelManager.getAllModels()
    }
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

// 通过 id 从后端模型列表中查找模型。
async function findModelById(type: 'stratum' | 'workingface', id: string) {
    const modelList = await modelApi.getModelList({ type })
    return modelList.find((item) => item.id === id)
}

// 加载地层模型，失败时回退到占位体。
async function loadStratumModel(model: ModelItem) {
    const stratumLoader = new StratumModelLoader()
    try {
        const object = await stratumLoader.load(model)
        modelManager.addModel({ id: model.id, name: model.name, type: 'stratum', object })
        registerStratumLayersFromObject(object, model.id, model.name)
    } catch {
        addPlaceholderStratum(model)
    }

    layerManager.setLayerEdgesVisible('stratum', showEdges.value)
}

// 加载工作面模型，失败时回退到占位体。
async function loadWorkingFaceModel(model: ModelItem) {
    const workingFaceLoader = new WorkingFaceModelLoader()
    try {
        const object = await workingFaceLoader.load(model)
        modelManager.addModel({ id: model.id, name: model.name, type: 'workingface', object })
    } catch {
        addPlaceholderWorkingFace(model)
    }
}

// 加载单个钻孔模型并计算其摆放位置。
async function loadBoreholeModel(borehole: BoreholeItem, index: number) {
    const boreholeLoader = new BoreholeModelLoader()

    let position: { x: number; y: number; z: number }
    if (borehole.location) {
        position = {
            x: borehole.location.x,
            y: borehole.location.y,
            z: borehole.location.z * BOREHOLE_VERTICAL_SCALE,
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

    const object = boreholeLoader.createBoreholeObject(borehole, position, BOREHOLE_VERTICAL_SCALE)
    modelManager.addModel({ id: borehole.id, name: borehole.name, type: 'borehole', object })
}

// 批量加载钻孔模型并同步加载状态。
async function loadAllBoreholeModels(boreholes: BoreholeItem[]) {
    for (let i = 0; i < boreholes.length; i += 1) {
        const borehole = boreholes[i]
        if (modelManager.getModel(borehole.id)) {
            sceneStore.setModelLoadStatus('borehole', borehole.id, { loaded: true, loading: false })
            continue
        }
        await loadBoreholeModel(borehole, i)
        sceneStore.setModelLoadStatus('borehole', borehole.id, { loaded: true, loading: false })
    }
}

// 构建地层占位模型（用于文件缺失时兜底显示）。
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

// 构建工作面占位模型（用于加载失败回退）。
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

// 将 three 颜色对象转为十六进制字符串。
function toHexColor(color?: THREE.Color) {
    if (!color) return '#5a8a9a'
    return `#${color.getHexString()}`
}

// 从地层对象中提取分层控制数据并注册到 store。
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
        controls.push({
            key,
            modelId,
            modelName,
            layerName,
            visible: mesh.visible,
            opacity,
            color,
        })
    })

    if (controls.length) {
        sceneStore.registerStratumLayers(controls)
    }

}

// 切换地层炸开状态。
function toggleStratumExplode() {
    if (!stratumExplodeTool) return
    stratumExploded.value = stratumExplodeTool.toggle()
}

// 将分层可见性、颜色和透明度控制应用到对应网格。
function applyStratumLayerControl(control: StratumLayerControl) {
    const model = modelManager.getModel(control.modelId)
    if (!model) return
    model.object.traverse((child) => {
        if (!(child as THREE.Mesh).isMesh) return
        const mesh = child as THREE.Mesh
        const key = String(mesh.userData?.id || '')
        if (key !== control.key) return

        mesh.visible = control.visible
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
        for (const mat of mats as any[]) {
            if (mat.color) {
                mat.color.set(control.color)
            }
            mat.transparent = control.opacity < 1
            mat.opacity = control.opacity
            mat.needsUpdate = true
        }

        const edgeLines = (mesh as any).userData?.edgeLines
        if (edgeLines) {
            edgeLines.visible = showEdges.value && control.visible
        }
    })
}

// 重置相机到默认观察位姿。
function resetCamera() {
    fitCameraToType(null, true)
}

// 将 store 中工具状态同步到运行时实例。
function syncToolRuntimeState() {
    if (!clipTool || !measureTool || !annotationTool || !selectionManager) return

    if (toolState.value.clipEnabled) {
        clipTool.enable({
            axis: toolState.value.clipAxis,
            position: toolState.value.clipHeight,
            keepLower: toolState.value.clipKeepLower,
            showHelper: toolState.value.clipHelperVisible,
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
        annotationTool.enable()
    } else {
        annotationTool.disable()
    }

    selectionManager.setEnabled(!(toolState.value.measureEnabled || toolState.value.annotationEnabled))
}

// 开关剖切工具。
function toggleClipTool() {
    sceneStore.activateTool(toolState.value.clipEnabled ? null : 'clip')
}

// 开关测量工具。
function toggleMeasureTool() {
    sceneStore.activateTool(toolState.value.measureEnabled ? null : 'measure')
}

// 开关标注工具。
function toggleAnnotationTool() {
    sceneStore.activateTool(toolState.value.annotationEnabled ? null : 'annotation')
}

// 响应剖切滑块数值变化。
function onClipHeightChange(value: number | undefined) {
    sceneStore.setClipHeight(typeof value === 'number' ? value : 0)
}

// 设置剖切轴。
function setClipAxis(axis: 'x' | 'y' | 'z') {
    sceneStore.setClipAxis(axis)
}

// 设置剖切保留方向（低侧/高侧）。
function setClipKeepLower(value: boolean | string | number) {
    sceneStore.setClipKeepLower(Boolean(value))
}

// 设置剖切辅助面显示状态。
function setClipHelperVisible(value: boolean | string | number) {
    sceneStore.setClipHelperVisible(Boolean(value))
}

// 清空测量结果与场景测量图元。
function clearMeasurements() {
    sceneStore.clearMeasurements()
    measureTool?.clear()
}

// 清空场景中的全部标注。
function clearAnnotations() {
    annotationTool?.clear()
}

// 切换 geoRoot 的 X 轴旋转映射并重置观察。
function onRotateXAxisToggle(value: boolean | string | number) {
    const enabled = Boolean(value)
    rotateXAxisEnabled.value = enabled
    sceneManager?.setGeoRootRotationXEnabled(enabled)
    stratumExplodeTool?.sync()

    if (modelManager?.getAllModels().length) {
        fitCameraToType(null, true)
    }
}

function hideHoverLabel() {
    hoverLabel.value.visible = false
}

function onControlStart() {
    selectionManager?.setHoverEnabled(false)
    hideHoverLabel()
}

function onControlEnd() {
    selectionManager?.setHoverEnabled(true)
}

// 监听图层显隐
watch(layerVisible, (val) => {
    layerManager.setLayerVisible('stratum', val.stratum)
    layerManager.setLayerVisible('borehole', val.borehole)
    layerManager.setLayerVisible('workingface', val.workingface)
}, { deep: true })

// 监听透明度
watch(opacity, (val) => {
    layerManager.setLayerOpacity('stratum', val.stratum)
    layerManager.setLayerOpacity('borehole', val.borehole)
    layerManager.setLayerOpacity('workingface', val.workingface)
}, { deep: true })

watch(showEdges, (visible) => {
    layerManager.setLayerEdgesVisible('stratum', visible)
})

watch(stratumLayers, (layers) => {
    for (const layer of layers) {
        applyStratumLayerControl(layer)
    }
}, { deep: true })

watch(() => toolState.value.clipHeight, (height) => {
    if (clipTool && Math.abs(clipTool.getHeight() - height) > 1e-6) {
        clipTool.setHeight(height)
    }
})

watch(
    () => ({
        clipEnabled: toolState.value.clipEnabled,
        measureEnabled: toolState.value.measureEnabled,
        annotationEnabled: toolState.value.annotationEnabled,
        clipHeight: toolState.value.clipHeight,
        clipAxis: toolState.value.clipAxis,
        clipKeepLower: toolState.value.clipKeepLower,
        clipHelperVisible: toolState.value.clipHelperVisible,
    }),
    () => {
        syncToolRuntimeState()
    },
    { deep: true }
)

// 监听定位目标
watch(locateTarget, (target) => {
    if (!target) return
    const model = modelManager.getModel(target.id)
    if (model) {
        const box = new THREE.Box3().setFromObject(model.object)
        const center = box.getCenter(new THREE.Vector3())
        cameraManager.flyTo(center, 2000)
        controlsManager.controls.target.copy(center)
        highlightManager.select(model.object)
    }
})

watch(loadRequest, (req) => {
    if (req) {
        loadModelByRequest(req)
    }
})

onMounted(() => {
    initScene()
})

onActivated(() => {
    startAnimate()
    selectionManager?.setHoverEnabled(true)
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
    sceneStore.activateTool(null)
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
    modelManager?.clear()
    sceneManager?.dispose()
    hideHoverLabel()
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

.tools-bar {
    position: absolute;
    top: 12px;
    right: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    border: 1px solid rgba(0, 200, 255, 0.28);
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(10, 22, 40, 0.92), rgba(15, 36, 71, 0.8));
    backdrop-filter: blur(8px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.32);
}

.tools-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.tools-divider {
    width: 1px;
    height: 28px;
    background: rgba(138, 180, 212, 0.35);
}

.tool-btn {
    min-width: 72px;
    height: 34px;
    border: 1px solid rgba(138, 180, 212, 0.35);
    color: var(--color-text-primary);
    background: rgba(19, 45, 85, 0.45);
}

.tool-btn span {
    margin-left: 6px;
    font-size: 12px;
}

.tool-btn.active {
    border-color: rgba(0, 200, 255, 0.8);
    color: #dff8ff;
    background: linear-gradient(135deg, rgba(0, 200, 255, 0.25), rgba(16, 54, 102, 0.8));
}

.tool-btn.ghost {
    min-width: 60px;
}

.axis-toggle-group {
    gap: 6px;
}

.axis-toggle-label {
    color: var(--color-text-secondary);
    font-size: 12px;
}

.clip-control {
    width: 180px;
    padding: 0 2px;
}

.clip-axis-row {
    display: flex;
    gap: 6px;
    margin-bottom: 6px;
}

.axis-btn {
    min-width: 34px;
    height: 24px;
    border: 1px solid rgba(138, 180, 212, 0.35);
    color: var(--color-text-secondary);
    background: rgba(19, 45, 85, 0.35);
    padding: 0;
}

.axis-btn.active {
    color: #dff8ff;
    border-color: rgba(0, 200, 255, 0.8);
    background: rgba(0, 200, 255, 0.2);
}

.clip-label {
    display: block;
    margin-bottom: 4px;
    color: var(--color-text-secondary);
    font-size: 12px;
}

.clip-flags {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 8px;
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
    .tools-bar {
        top: auto;
        bottom: 12px;
        right: 12px;
        left: auto;
        max-width: calc(100% - 24px);
        padding: 6px;
        gap: 6px;
        flex-wrap: nowrap;
        justify-content: flex-start;
        overflow-x: auto;
        overflow-y: hidden;
        scrollbar-width: thin;
        -webkit-overflow-scrolling: touch;
    }

    .tools-group {
        width: auto;
        justify-content: flex-start;
        flex-shrink: 0;
    }

    .tools-divider {
        display: block;
        flex-shrink: 0;
        height: 24px;
    }

    .tool-btn {
        min-width: 58px;
        height: 30px;
        padding: 0 8px;
    }

    .tool-btn span {
        margin-left: 4px;
        font-size: 11px;
    }

    .axis-toggle-label {
        white-space: nowrap;
        font-size: 11px;
    }

    .clip-control {
        width: 156px;
    }

    .clip-label {
        margin-bottom: 2px;
        font-size: 11px;
    }

    .clip-flags {
        margin-top: 6px;
    }

    .tools-bar::-webkit-scrollbar {
        height: 4px;
    }

    .tools-bar::-webkit-scrollbar-thumb {
        background: rgba(138, 180, 212, 0.45);
        border-radius: 999px;
    }

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
</style>
