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

const sceneStore = useSceneStore()
const boreholeStore = useBoreholeStore()
const { layerVisible, opacity, locateTarget, loadRequestTick, showEdges } = storeToRefs(sceneStore)

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

async function loadModelByType(type: 'stratum' | 'borehole' | 'workingface') {
    const status = sceneStore.modelStatus[type]
    if (status.loaded || status.loading) return

    sceneStore.setModelStatus(type, { loading: true })
    try {
        if (type === 'stratum') {
            await loadStratumModels()
        }

        if (type === 'workingface') {
            await loadWorkingFaceModels()
        }

        if (type === 'borehole') {
            await loadBoreholeModels()
        }
        sceneManager.removeGrid() // 模型加载后移除辅助网格
        sceneStore.setModelStatus(type, { loaded: true, loading: false })
        fitCameraToLoadedModels()
    } catch (err) {
        sceneStore.setModelStatus(type, { loading: false })
        console.error(`[SceneCanvas] ${type} 模型加载失败`, err)
    }
}

async function loadStratumModels() {
    const stratumModels = await modelApi.getModelList({ type: 'stratum' })
    const stratumLoader = new StratumModelLoader()
    for (const m of stratumModels) {
        try {
            const obj = await stratumLoader.load(m)
            modelManager.addModel({ id: m.id, name: m.name, type: 'stratum', object: obj })
        } catch {
            // .glb 文件不存在时跳过，用占位几何体代替
            addPlaceholderStratum(m)
        }
    }

    layerManager.setLayerEdgesVisible('stratum', showEdges.value)
}

async function loadWorkingFaceModels() {
    const workingfaceModels = await modelApi.getModelList({ type: 'workingface' })
    const wfLoader = new WorkingFaceModelLoader()
    for (const m of workingfaceModels) {
        try {
            const obj = await wfLoader.load(m)
            modelManager.addModel({ id: m.id, name: m.name, type: 'workingface', object: obj })
        } catch {
            addPlaceholderWorkingFace(m)
        }
    }
}

async function loadBoreholeModels() {
    const boreholes = await boreholeApi.getBoreholeList()
    const bhLoader = new BoreholeModelLoader()

    boreholes.forEach((b, i) => {
        let pos: { x: number; z: number }
        if (b.location) {
            pos = { x: b.location.x, z: b.location.z }
        } else {
            // 无位置数据：均匀网格排列
            const cols = Math.ceil(Math.sqrt(boreholes.length))
            const spacing = 500
            pos = {
                x: (i % cols) * spacing - (cols * spacing) / 2,
                z: Math.floor(i / cols) * spacing - (cols * spacing) / 2,
            }
        }

        const obj = bhLoader.createBoreholeObject(b, pos)
        if (b.location) {
            obj.position.y = b.location.y
        }
        modelManager.addModel({ id: b.id, name: b.name, type: 'borehole', object: obj })
    })

    // 存入钻孔 Store，供图表/详情使用
    boreholeStore.list = boreholes
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

watch(() => loadRequestTick.value.stratum, (tick) => {
    if (tick > 0) {
        loadModelByType('stratum')
    }
})

watch(() => loadRequestTick.value.borehole, (tick) => {
    if (tick > 0) {
        loadModelByType('borehole')
    }
})

watch(() => loadRequestTick.value.workingface, (tick) => {
    if (tick > 0) {
        loadModelByType('workingface')
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
