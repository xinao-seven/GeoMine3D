<template>
    <div class="cesium-page">
        <div class="toolbar">
            <div class="toolbar-left">
                <el-tag type="success" effect="dark">Cesium 空间场景</el-tag>
                <span class="projection" v-if="projectionText">{{ projectionText }}</span>
            </div>
            <div class="toolbar-right">
                <el-select v-model="selectedModelId" placeholder="选择地层模型" style="width: 220px" filterable clearable>
                    <el-option v-for="item in stratumModels" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
                <el-button type="primary" :loading="loadingModel" @click="loadStratumModel">
                    加载地层模型
                </el-button>
                <el-select v-model="selectedTiffId" placeholder="选择 TIFF 影像" style="width: 220px" filterable clearable>
                    <el-option v-for="item in tiffLayers" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
                <el-button type="warning" :loading="loadingTiff" @click="loadSelectedTiffLayer">
                    导入TIFF
                </el-button>
                <el-button :disabled="!currentTiffLayerName" @click="removeTiffLayer">移除TIFF</el-button>
                <el-button :loading="loadingBaseData" @click="reloadBaseLayers">加载边界与钻孔</el-button>
            </div>
        </div>

        <div ref="containerRef" class="viewer-container"></div>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
    BoundingSphere,
    Cartesian2,
    Cartesian3,
    Color,
    ColorBlendMode,
    GeoJsonDataSource,
    HeadingPitchRange,
    HeightReference,
    ImageryLayer,
    JulianDate,
    LabelStyle,
    Math as CesiumMath,
    Matrix4,
    Model,
    Rectangle,
    ShadowMode,
    SingleTileImageryProvider,
    Transforms,
    Viewer,
    Axis
} from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import { cesiumApi, modelApi } from '@/api'
import type { ModelItem } from '@/types'
import type {
    BoreholeWGS84Point,
    BoundaryFeature,
    BoundaryFeatureCollection,
    CesiumTiffLayerItem,
    CesiumTiffLayerResponse,
} from '@/types/cesium'


defineOptions({
    name: 'CesiumView',
})

const containerRef = ref<HTMLDivElement>()
const viewerRef = ref<Viewer | null>(null)
const loadingBaseData = ref(false)
const loadingModel = ref(false)
const loadingTiff = ref(false)
const stratumModels = ref<ModelItem[]>([])
const selectedModelId = ref('')
const tiffLayers = ref<CesiumTiffLayerItem[]>([])
const selectedTiffId = ref('')
const currentTiffLayerName = ref('')
const projectionText = ref('')

let mineCenter: { lon: number; lat: number; alt: number } | null = null
let currentStratumModel: Model | null = null
let currentTiffImageryLayer: ImageryLayer | null = null

const hasSelectedModel = computed(() => Boolean(selectedModelId.value))

// 创建 Cesium Viewer，并关闭非必要控件以突出业务图层。
function createViewer() {
    if (!containerRef.value) return
    const viewer = new Viewer(containerRef.value, {
        animation: false,
        timeline: false,
        baseLayerPicker: true,
        geocoder: false,
        homeButton: true,
        sceneModePicker: true,
        navigationHelpButton: false,
        infoBox: false,
        selectionIndicator: true,
        shouldAnimate: true,
    })
    viewer.scene.globe.depthTestAgainstTerrain = false
    viewer.scene.globe.enableLighting = false
    viewer.scene.fog.enabled = false
    viewerRef.value = viewer
}

// 计算 GeoJSON FeatureCollection 的经纬度包围盒中心点。
function calcGeoJSONCenter(collection: BoundaryFeatureCollection) {
    let lonMin = Infinity
    let lonMax = -Infinity
    let latMin = Infinity
    let latMax = -Infinity

    const walk = (node: any) => {
        if (!Array.isArray(node)) return
        if (typeof node[0] === 'number' && typeof node[1] === 'number') {
            lonMin = Math.min(lonMin, node[0])
            lonMax = Math.max(lonMax, node[0])
            latMin = Math.min(latMin, node[1])
            latMax = Math.max(latMax, node[1])
            return
        }
        node.forEach(walk)
    }

    collection.features.forEach((feature: BoundaryFeature) => walk(feature.geometry.coordinates))
    if (!Number.isFinite(lonMin) || !Number.isFinite(latMin)) return null

    return {
        lon: (lonMin + lonMax) / 2,
        lat: (latMin + latMax) / 2,
    }
}

// 加载边界类 GeoJSON 图层并应用统一样式。
async function loadBoundaryLayer(
    name: string,
    collection: BoundaryFeatureCollection,
    color: Color,
    width: number,
) {
    const viewer = viewerRef.value
    if (!viewer) return

    const dataSource = await GeoJsonDataSource.load(collection as any, {
        clampToGround: false,
        stroke: color,
        strokeWidth: width,
        fill: color.withAlpha(0.12),
    })

    dataSource.name = name
    viewer.dataSources.add(dataSource)
}

// 加载钻孔点并校验经纬度与高程有效性。
async function loadBoreholes() {
    const viewer = viewerRef.value
    if (!viewer) return
    const data = await cesiumApi.getBoreholeWGS84Points()
    let skipped = 0

    data.items.forEach((item: BoreholeWGS84Point) => {
        if (!Number.isFinite(item.longitude) || !Number.isFinite(item.latitude) || !Number.isFinite(item.altitude)) {
            skipped += 1
            return
        }
        if (Math.abs(item.longitude) > 180 || Math.abs(item.latitude) > 90) {
            skipped += 1
            return
        }

        viewer.entities.add({
            name: item.name,
            position: Cartesian3.fromDegrees(item.longitude, item.latitude, item.altitude),
            point: {
                pixelSize: 8,
                color: Color.fromCssColorString('#00c8ff'),
                outlineColor: Color.fromCssColorString('#ffffff'),
                outlineWidth: 1.2,
                heightReference: HeightReference.NONE,
            },
            label: {
                text: item.name,
                font: '12px Microsoft YaHei',
                showBackground: true,
                backgroundColor: Color.fromCssColorString('#0a1628').withAlpha(0.68),
                fillColor: Color.fromCssColorString('#dff5ff'),
                outlineColor: Color.BLACK,
                outlineWidth: 1,
                style: LabelStyle.FILL_AND_OUTLINE,
                pixelOffset: new Cartesian2(0, -16),
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            properties: {
                type: 'borehole',
                id: item.id,
                sourceX: item.source.x,
                sourceY: item.source.y,
                sourceZ: item.source.z,
            },
        })
    })

    if (skipped > 0) {
        ElMessage.warning(`已跳过 ${skipped} 个异常钻孔点`) 
    }
}

// 类型守卫：判断数据是否符合 FeatureCollection 基本结构。
function isFeatureCollectionLike(value: any): value is BoundaryFeatureCollection {
    return Boolean(value && value.type === 'FeatureCollection' && Array.isArray(value.features))
}

// 统一处理资源地址，补全相对路径前缀。
function normalizeDataUrl(url: string) {
    if (!url) return url
    if (/^https?:\/\//i.test(url)) return url
    return url.startsWith('/') ? url : `/${url}`
}

// 从场景中移除当前 TIFF 影像图层。
function removeTiffLayer() {
    const viewer = viewerRef.value
    if (!viewer || !currentTiffImageryLayer) return
    viewer.imageryLayers.remove(currentTiffImageryLayer, true)
    currentTiffImageryLayer = null
    currentTiffLayerName.value = ''
    ElMessage.success('TIFF 图层已移除')
}

// 根据当前选择加载 TIFF 影像，并飞行到其覆盖范围。
async function loadSelectedTiffLayer() {
    const viewer = viewerRef.value
    if (!viewer) return
    if (!selectedTiffId.value) {
        ElMessage.warning('请先选择 TIFF 影像')
        return
    }

    const selected = tiffLayers.value.find((item) => item.id === selectedTiffId.value)
    if (!selected) {
        ElMessage.error('未找到对应 TIFF 图层')
        return
    }

    loadingTiff.value = true
    try {
        if (currentTiffImageryLayer) {
            viewer.imageryLayers.remove(currentTiffImageryLayer, true)
            currentTiffImageryLayer = null
        }

        const rectangle = Rectangle.fromDegrees(
            selected.bounds.west,
            selected.bounds.south,
            selected.bounds.east,
            selected.bounds.north,
        )

        const imageryProvider = await SingleTileImageryProvider.fromUrl(normalizeDataUrl(selected.previewUrl), {
            rectangle,
        })
        currentTiffImageryLayer = viewer.imageryLayers.addImageryProvider(imageryProvider)
        currentTiffImageryLayer.alpha = 0.82
        currentTiffLayerName.value = selected.name

        viewer.camera.flyTo({
            destination: rectangle,
            duration: 1.2,
        })

        ElMessage.success(`TIFF 已导入: ${selected.name}`)
    } catch (err: any) {
        ElMessage.error(err?.message || 'TIFF 导入失败')
    } finally {
        loadingTiff.value = false
    }
}

// 拉取 TIFF 图层列表并处理默认选中项。
async function loadTiffLayerList() {
    let response: CesiumTiffLayerResponse
    try {
        response = await cesiumApi.getTiffLayers()
    } catch {
        ElMessage.warning('TIFF 列表加载失败，可稍后重试')
        return
    }

    tiffLayers.value = response.items || []
    if (!selectedTiffId.value && tiffLayers.value.length > 0) {
        selectedTiffId.value = tiffLayers.value[0].id
    }

    if (response.skipped?.length) {
        ElMessage.warning(`发现 ${response.skipped.length} 个 TIFF 数据文件不完整，已自动跳过`)
    }
}

// 重载 Cesium 基础图层：投影信息、矿区边界、工作面边界和钻孔点。
async function reloadBaseLayers() {
    const viewer = viewerRef.value
    if (!viewer) return

    loadingBaseData.value = true
    try {
        viewer.dataSources.removeAll()
        viewer.entities.removeAll()

        let mineArea: BoundaryFeatureCollection | null = null
        let workingFaces: BoundaryFeatureCollection | null = null
        let loadedAnyLayer = false
        const failedSteps: string[] = []

        try {
            const projection = await cesiumApi.getProjectionMetadata()
            projectionText.value = `${projection.sourceCrs} -> ${projection.targetCrs}`
        } catch {
            projectionText.value = ''
            failedSteps.push('投影信息')
        }

        try {
            const response = await cesiumApi.getMineAreaBoundary()
            if (!isFeatureCollectionLike(response)) {
                throw new Error('矿区边界返回结构不是 FeatureCollection')
            }
            mineArea = response
            await loadBoundaryLayer('mine-area', response, Color.fromCssColorString('#34d399'), 2.4)
            loadedAnyLayer = true
        } catch {
            failedSteps.push('矿区边界')
        }

        try {
            const response = await cesiumApi.getWorkingFaceBoundaries()
            if (!isFeatureCollectionLike(response)) {
                throw new Error('工作面边界返回结构不是 FeatureCollection')
            }
            workingFaces = response
            await loadBoundaryLayer('working-faces', response, Color.fromCssColorString('#f59e0b'), 1.8)
            loadedAnyLayer = true
        } catch {
            failedSteps.push('工作面边界')
        }

        try {
            await loadBoreholes()
            loadedAnyLayer = true
        } catch {
            failedSteps.push('钻孔点位')
        }

        const centerSource = mineArea ?? workingFaces
        const center = centerSource ? calcGeoJSONCenter(centerSource) : null
        if (center) {
            mineCenter = { lon: center.lon, lat: center.lat, alt: 1800 }
            const focus = Cartesian3.fromDegrees(center.lon, center.lat, 2800)
            viewer.camera.flyTo({
                destination: focus,
                orientation: {
                    heading: CesiumMath.toRadians(0),
                    pitch: CesiumMath.toRadians(-35),
                    roll: 0,
                },
                duration: 1.4,
            })
        }

        if (!loadedAnyLayer) {
            ElMessage.error('Cesium 数据加载失败：未成功加载任何图层')
            return
        }

        if (failedSteps.length > 0) {
            ElMessage.warning(`部分数据加载失败：${failedSteps.join('、')}`)
        } else {
            ElMessage.success('矿区边界、工作面边界与钻孔点已加载')
        }
    } catch (err: any) {
        ElMessage.error(err?.message || '基础图层加载失败')
    } finally {
        loadingBaseData.value = false
    }
}

// 统一地层模型的渲染风格，优化可读性与层次感。
function optimizeStratumModelMaterial(model: Model) {
    model.color = Color.fromCssColorString('#c5cdb6').withAlpha(1.0)
    model.colorBlendMode = ColorBlendMode.MIX
    model.colorBlendAmount = 0.08
    model.silhouetteSize = 0
    model.backFaceCulling = false
    model.shadows = ShadowMode.ENABLED
    model.imageBasedLighting.imageBasedLightingFactor = new Cartesian2(0.72, 0.68)
}

// 按模型包围球尺度动态调整相机近远裁剪面。
function tuneCameraFrustumByModelSphere(viewer: Viewer, sphere: BoundingSphere) {
    const frustum = viewer.camera.frustum as { near?: number; far?: number }
    if (typeof frustum.near !== 'number' || typeof frustum.far !== 'number') {
        return
    }

    const radius = Math.max(1, sphere.radius)
    frustum.near = Math.max(0.5, radius / 4000)
    frustum.far = Math.max(2_000_000, radius * 120)
}

// 将模型平移到锚点位置，修正导入后中心偏移。
function recenterModelToAnchor(model: Model, anchor: Cartesian3) {
    const currentCenter = model.boundingSphere?.center
    if (!currentCenter) return

    const delta = Cartesian3.subtract(anchor, currentCenter, new Cartesian3())
    const distance = Cartesian3.magnitude(delta)
    if (!Number.isFinite(distance) || distance < 1) {
        return
    }

    const translation = Matrix4.fromTranslation(delta)
    model.modelMatrix = Matrix4.multiply(translation, model.modelMatrix, new Matrix4())
}

// 等待 Cesium 模型就绪，结合 readyEvent 与轮询避免漏判。
function waitForModelReady(model: Model, timeoutMs = 20000): Promise<void> {
    if (model.ready) {
        return Promise.resolve()
    }

    return new Promise((resolve, reject) => {
        let settled = false
        const removeListener = model.readyEvent.addEventListener(() => {
            if (settled) return
            settled = true
            clearInterval(pollTimer)
            clearTimeout(timeout)
            removeListener()
            resolve()
        })

        // Some Cesium builds may set ready before event callback scheduling, so poll as a fallback.
        const pollTimer = setInterval(() => {
            if (settled) return
            if (model.ready) {
                settled = true
                clearInterval(pollTimer)
                clearTimeout(timeout)
                removeListener()
                resolve()
            }
        }, 50)

        const timeout = setTimeout(() => {
            if (settled) return
            settled = true
            clearInterval(pollTimer)
            removeListener()
            reject(new Error('模型加载超时，请稍后重试'))
        }, timeoutMs)
    })
}

// 加载当前选中的地层模型并执行视角与材质初始化。
async function loadStratumModel() {
    const viewer = viewerRef.value
    if (!viewer) return
    if (!hasSelectedModel.value) {
        ElMessage.warning('请先选择一个地层模型')
        return
    }

    const modelInfo = stratumModels.value.find((item) => item.id === selectedModelId.value)
    if (!modelInfo) {
        ElMessage.error('未找到对应地层模型')
        return
    }

    loadingModel.value = true
    try {
        if (currentStratumModel) {
            viewer.scene.primitives.remove(currentStratumModel)
            currentStratumModel = null
        }

        const anchor = mineCenter ?? { lon: 109.0, lat: 38.0, alt: 0 }
        const origin = Cartesian3.fromDegrees(anchor.lon, anchor.lat, anchor.alt)
        const modelMatrix = Transforms.eastNorthUpToFixedFrame(origin)

        const model = await Model.fromGltfAsync({
            upAxis: Axis.X,
            url: modelInfo.fileUrl,
            modelMatrix,
            scale: 1,
            minimumPixelSize: 0,
            backFaceCulling: false,
            cull: false,
            allowPicking: true,
            incrementallyLoadTextures: true,
        })

        viewer.scene.primitives.add(model)
        currentStratumModel = model

        await waitForModelReady(model)
        recenterModelToAnchor(model, origin)
        optimizeStratumModelMaterial(model)

        const now = JulianDate.now()
        const sphere = model.boundingSphere
        if (sphere && sphere.radius > 0) {
            tuneCameraFrustumByModelSphere(viewer, sphere)
            viewer.camera.flyToBoundingSphere(sphere, {
                offset: new HeadingPitchRange(0, CesiumMath.toRadians(-35), sphere.radius * 2.2),
                duration: 1.6,
            })
        } else {
            const fallback = new BoundingSphere(Matrix4.getTranslation(modelMatrix, new Cartesian3()), 1200)
            viewer.camera.flyToBoundingSphere(fallback, {
                offset: new HeadingPitchRange(0, CesiumMath.toRadians(-30), 2600),
                duration: 1.2,
            })
        }

        model.activeAnimations.addAll({
            loop: 0,
            multiplier: 1,
            startTime: now,
        })

        ElMessage.success(`地层模型已加载: ${modelInfo.name}`)
    } catch (err: any) {
        ElMessage.error(err?.message || '地层模型加载失败')
    } finally {
        loadingModel.value = false
    }
}

// 拉取地层模型列表并设置默认模型。
async function loadStratumList() {
    stratumModels.value = await modelApi.getModelList({ type: 'stratum' })
    if (stratumModels.value.length > 0) {
        selectedModelId.value = stratumModels.value[0].id
    }
}

onMounted(async () => {
    createViewer()
    await loadTiffLayerList()
    await loadStratumList().catch(() => {
        ElMessage.warning('地层模型列表加载失败，可稍后重试')
    })
    // await reloadBaseLayers()
})

onUnmounted(() => {
    currentStratumModel = null
    currentTiffImageryLayer = null
    if (viewerRef.value) {
        viewerRef.value.destroy()
        viewerRef.value = null
    }
})
</script>

<style scoped>
.cesium-page {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #050d1a;
}

.toolbar {
    height: 56px;
    flex-shrink: 0;
    border-bottom: 1px solid rgba(110, 185, 255, 0.18);
    background: linear-gradient(90deg, rgba(6, 26, 48, 0.95), rgba(12, 45, 77, 0.82));
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
}

.toolbar-left {
    display: flex;
    align-items: center;
    gap: 10px;
}

.projection {
    color: #9fd8ff;
    font-size: 12px;
    letter-spacing: 0.2px;
}

.toolbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
}

.viewer-container {
    flex: 1;
    min-height: 0;
}
</style>
