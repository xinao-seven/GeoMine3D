<template>
    <div ref="containerRef" class="scene-canvas">
        <canvas ref="canvasRef" class="canvas" />

        <div class="tools-bar">
            <el-tooltip content="重置视角" placement="left">
                <el-button size="small" circle @click="resetCamera"><el-icon>
                        <RefreshRight />
                    </el-icon></el-button>
            </el-tooltip>
            <el-tooltip :content="clipEnabled ? '关闭剖切' : '开启剖切'" placement="left">
                <el-button size="small" circle :type="clipEnabled ? 'primary' : ''" @click="toggleClip">
                    <el-icon>
                        <Scissor />
                    </el-icon>
                </el-button>
            </el-tooltip>
            <el-tooltip content="测量（占位）" placement="left">
                <el-button size="small" circle disabled><el-icon>
                        <Aim />
                    </el-icon></el-button>
            </el-tooltip>
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
import { ModelManager } from '@/three/managers/ModelManager'
import { LayerManager } from '@/three/managers/LayerManager'
import { HighlightManager } from '@/three/managers/HighlightManager'
import { SelectionManager } from '@/three/managers/SelectionManager'
import { StratumModelLoader } from '@/three/loaders/StratumModelLoader'
import { BoreholeModelLoader } from '@/three/loaders/BoreholeModelLoader'
import { WorkingFaceModelLoader } from '@/three/loaders/WorkingFaceModelLoader'
import { ClipTool } from '@/three/tools/ClipTool'
import { modelApi, boreholeApi } from '@/api'
import { useSceneStore, useBoreholeStore } from '@/stores'
import { storeToRefs } from 'pinia'
import type { ModelItem, BoreholeItem } from '@/types'
import type { ModelLoadRequest } from '@/stores/sceneStore'

const sceneStore = useSceneStore()
const boreholeStore = useBoreholeStore()
const { layerVisible, opacity, locateTarget, loadRequest, showEdges } = storeToRefs(sceneStore)

const containerRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const clipEnabled = ref(false)

let sceneManager: SceneManager
let cameraManager: CameraManager
let rendererManager: RendererManager
let controlsManager: ControlsManager
let lightManager: LightManager
let modelManager: ModelManager
let layerManager: LayerManager
let highlightManager: HighlightManager
let selectionManager: SelectionManager
let clipTool: ClipTool
let animFrameId: number
let resizeObserver: ResizeObserver
let isAnimating = false

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
    clipTool = new ClipTool(rendererManager.renderer)

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
        }
    )

    resizeObserver = new ResizeObserver(() => {
        if (!containerRef.value) return
        const { width: w, height: h } = containerRef.value.getBoundingClientRect()
        rendererManager.resize(w, h)
        cameraManager.updateAspect(w, h)
    })
    resizeObserver.observe(containerRef.value)

    startAnimate()
}

function animate() {
    if (!isAnimating) return
    animFrameId = requestAnimationFrame(animate)
    controlsManager.update()
    rendererManager.render(sceneManager.scene, cameraManager.camera)
}

function startAnimate() {
    if (isAnimating) return
    isAnimating = true
    animate()
}

function stopAnimate() {
    if (!isAnimating) return
    isAnimating = false
    cancelAnimationFrame(animFrameId)
}

async function loadModelByRequest(req: ModelLoadRequest) {
    try {
        if (req.type === 'stratum') {
            const model = req.model || await findModelById('stratum', req.id)
            if (!model) throw new Error(`未找到地层模型: ${req.id}`)
            await loadStratumModel(model)
        }

        if (req.type === 'workingface') {
            const model = req.model || await findModelById('workingface', req.id)
            if (!model) throw new Error(`未找到工作面模型: ${req.id}`)
            await loadWorkingFaceModel(model)
        }

        if (req.type === 'borehole') {
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
        }

        sceneManager.removeGrid() // 模型加载后移除辅助网格
        sceneStore.setModelLoadStatus(req.type, req.id, { loaded: true, loading: false })
        fitCameraToLoadedModels()
    } catch (err) {
        sceneStore.setModelLoadStatus(req.type, req.id, { loading: false })
        console.error(`[SceneCanvas] ${req.type} 模型加载失败`, err)
    }
}

async function findModelById(type: 'stratum' | 'workingface', id: string) {
    const modelList = await modelApi.getModelList({ type })
    return modelList.find((item) => item.id === id)
}

async function loadStratumModel(m: ModelItem) {
    const stratumLoader = new StratumModelLoader()
    try {
        const obj = await stratumLoader.load(m)
        modelManager.addModel({ id: m.id, name: m.name, type: 'stratum', object: obj })
    } catch {
        // .glb 文件不存在时跳过，用占位几何体代替
        addPlaceholderStratum(m)
    }

    layerManager.setLayerEdgesVisible('stratum', showEdges.value)
}

async function loadWorkingFaceModel(m: ModelItem) {
    const wfLoader = new WorkingFaceModelLoader()
    try {
        const obj = await wfLoader.load(m)
        modelManager.addModel({ id: m.id, name: m.name, type: 'workingface', object: obj })
    } catch {
        addPlaceholderWorkingFace(m)
    }
}

async function loadBoreholeModel(b: BoreholeItem, index: number) {
    const bhLoader = new BoreholeModelLoader()

    let pos: { x: number; z: number }
    if (b.location) {
        pos = { x: b.location.x, z: b.location.z }
    } else {
        const spacing = 500
        const cols = 10
        pos = {
            x: (index % cols) * spacing - (cols * spacing) / 2,
            z: Math.floor(index / cols) * spacing - (cols * spacing) / 2,
        }
    }

    const obj = bhLoader.createBoreholeObject(b, pos)
    if (b.location) {
        obj.position.y = b.location.y
    }
    modelManager.addModel({ id: b.id, name: b.name, type: 'borehole', object: obj })
}

function fitCameraToLoadedModels() {
    const models = modelManager.getAllModels()
    if (!models.length) return

    const box = new THREE.Box3()
    models.forEach((m) => box.expandByObject(m.object))

    const fitResult = cameraManager.fitToBox(box)
    if (!fitResult) return

    cameraManager.camera.near = fitResult.near
    cameraManager.camera.far = fitResult.far
    cameraManager.camera.updateProjectionMatrix()

    controlsManager.setDistanceLimits(fitResult.fitDistance * 0.1, fitResult.fitDistance * 5)

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

function addPlaceholderStratum(model: ModelItem) {
    const colors: Record<string, number> = { 'strata-001': 0x4a7a8a, 'strata-002': 0x6d9e73 }
    const color = colors[model.id] ?? 0x5a8a9a
    const geom = new THREE.BoxGeometry(400, 20, 300)
    const mat = new THREE.MeshLambertMaterial({ color, transparent: true, opacity: 0.7 })
    const mesh = new THREE.Mesh(geom, mat)
    mesh.position.y = Object.keys(colors).indexOf(model.id) * -25
    mesh.name = `stratum_${model.id}`
    mesh.userData = { id: model.id, name: model.name, type: 'stratum', modelData: model }
    modelManager.addModel({ id: model.id, name: model.name, type: 'stratum', object: mesh })
}

function addPlaceholderWorkingFace(model: ModelItem) {
    const geom = new THREE.BoxGeometry(200, 15, 120)
    const mat = new THREE.MeshLambertMaterial({ color: 0xf5a623, transparent: true, opacity: 0.8 })
    const mesh = new THREE.Mesh(geom, mat)
    mesh.position.set(Math.random() * 100 - 50, -80, Math.random() * 100 - 50)
    mesh.name = `workingface_${model.id}`
    mesh.userData = { id: model.id, name: model.name, type: 'workingface', modelData: model }
    modelManager.addModel({ id: model.id, name: model.name, type: 'workingface', object: mesh })
}

function resetCamera() {
    cameraManager.resetPosition()
    controlsManager.controls.target.set(0, 0, 0)
    controlsManager.controls.update()
}

function toggleClip() {
    if (clipEnabled.value) {
        clipTool.disable()
        clipEnabled.value = false
    } else {
        clipTool.enable()
        clipEnabled.value = true
    }
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
    if (!containerRef.value) return
    const { width, height } = containerRef.value.getBoundingClientRect()
    rendererManager?.resize(width, height)
    cameraManager?.updateAspect(width, height)
})

onDeactivated(() => {
    stopAnimate()
})

onUnmounted(() => {
    stopAnimate()
    resizeObserver?.disconnect()
    selectionManager?.dispose()
    controlsManager?.dispose()
    rendererManager?.dispose()
    highlightManager?.dispose()
    modelManager?.clear()
    sceneManager?.dispose()
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
    flex-direction: column;
    gap: 6px;
}
</style>
