<template>
    <aside class="resource-explorer">
        <div class="panel-heading">
            <div><span class="panel-kicker">PROJECT DATA</span>
                <h2>资源与图层</h2>
            </div>
            <button class="icon-button" title="刷新" @click="loadResources"><el-icon>
                    <Refresh />
                </el-icon></button>
        </div>
        <div class="panel-tabs">
            <button :class="{ active: tab === 'scene' }" @click="tab = 'scene'">场景</button>
            <button :class="{ active: tab === 'assets' }" @click="tab = 'assets'">资源</button>
        </div>

        <!-- ==================== 场景树 ==================== -->
        <div v-if="tab === 'scene'" class="panel-body scene-tree">
            <div class="tree-root">
                <span class="tree-caret">⌄</span><strong>当前场景</strong>
                <small>{{ sceneTotal }} 个单元</small>
            </div>

            <template v-for="group in sceneGroups" :key="group.type">
                <div class="tree-layer">
                    <button class="eye-button" :class="{ visible: layerVisible[group.type] }"
                        @click="sceneStore.setLayerVisible(group.type, !layerVisible[group.type])"><el-icon>
                            <View />
                        </el-icon></button>
                    <span class="layer-dot" :class="group.type"></span>
                    <span>{{ group.label }}</span>
                    <b>{{ group.count }}</b>
                </div>

                <!-- 地层:逐层材质控制 -->
                <div v-if="group.type === 'stratum' && stratumLayers.length" class="strata-tree">
                    <div v-for="item in stratumLayers" :key="item.key" class="strata-row"
                        :class="{ active: selectedLayerKey === item.key }">
                        <button class="layer-eye" :title="item.visible ? '隐藏' : '显示'"
                            @click="sceneStore.updateStratumLayer(item.key, { visible: !item.visible })"><el-icon>
                                <View />
                            </el-icon></button>
                        <button class="layer-select" @click="selectedLayerKey = item.key">
                            <i :style="{ background: item.color }"></i><span>{{ item.layerName }}</span><small>{{
                                item.visible ? 'ON' : 'OFF' }}</small>
                        </button>
                    </div>
                    <div v-if="selectedLayer" class="layer-editor">
                        <div class="editor-heading"><span>{{ selectedLayer.layerName }}</span><small>单元材质</small></div>
                        <label><span>颜色</span><el-color-picker :model-value="selectedLayer.color" size="small"
                                @change="setSelectedLayerColor" /></label>
                        <label><span>透明度</span><b>{{ Math.round(selectedLayer.opacity * 100) }}%</b></label>
                        <el-slider :model-value="selectedLayer.opacity * 100" :show-tooltip="false"
                            @input="setSelectedLayerOpacity" />
                    </div>
                </div>

                <!-- 其余类型:列出已加载的模型 -->
                <div v-else-if="group.items.length" class="scene-children">
                    <div v-for="item in group.items" :key="item.key" class="scene-child">
                        <i :style="{ background: item.color }"></i>
                        <span :title="item.label">{{ item.label }}</span>
                        <button class="scene-child-remove" title="从场景移除" @click="item.remove()">移除</button>
                    </div>
                </div>
            </template>

            <div class="scene-options">
                <label><span>显示地层边缘</span><el-switch :model-value="showEdges" size="small"
                        @change="sceneStore.setShowEdges($event as boolean)" /></label>
            </div>
        </div>

        <!-- ==================== 资源树 ==================== -->
        <div v-else class="panel-body" v-loading="loading">
            <template v-if="localMode">
                <div class="local-note"><el-icon>
                        <UploadFilled />
                    </el-icon><strong>本地临时工作区</strong><span>这里只用于拖入电脑中的 GLB。要加载 server
                        静态模型和钻孔，请从项目中心进入数据库项目。</span><button @click="router.push('/projects')">返回项目中心</button></div>
            </template>
            <template v-else>
                <div class="source-note">
                    <b>MODEL PACKAGE / CATALOG</b>
                    <span>{{ models.length }} 个模型资产 · {{ boreholes.length }} 个钻孔</span>
                </div>

                <section v-for="group in modelGroups" :key="group.key" class="resource-group">
                    <button class="group-title" type="button" @click="toggleGroup(group.key)">
                        <span class="group-caret" :class="{ collapsed: collapsed[group.key] }">⌄</span>
                        <span class="group-dot" :class="group.key"></span>
                        <span class="group-label">{{ group.label }}</span>
                        <b>{{ group.items.length }}</b>
                    </button>
                    <div v-show="!collapsed[group.key]" class="group-body">
                        <div v-for="model in group.items" :key="model.id" class="resource-row"
                            :class="{ 'is-loaded': modelStatus(model).loaded }">
                            <button class="resource-main"
                                :disabled="modelStatus(model).loading || modelStatus(model).loaded"
                                @click="loadModel(model)">
                                <span class="resource-symbol" :class="group.key" :style="symbolStyle(model)">{{
                                    group.symbol }}</span>
                                <span class="resource-name"><strong>{{ model.name }}</strong><small>{{ subtitle(model)
                                        }}</small></span>
                                <span class="load-state">{{ modelStatus(model).loaded ? '已加载' :
                                    modelStatus(model).loading ? '加载中' : '加载' }}</span>
                            </button>
                            <button v-if="modelStatus(model).loaded" class="remove-state" title="从场景移除"
                                @click="removeModel(model)">移除</button>
                        </div>
                        <p v-if="!group.items.length" class="empty-copy">当前项目暂无{{ group.label }}</p>
                    </div>
                </section>

                <section class="resource-group">
                    <button class="group-title" type="button" @click="toggleGroup('borehole')">
                        <span class="group-caret" :class="{ collapsed: collapsed.borehole }">⌄</span>
                        <span class="group-dot borehole"></span>
                        <span class="group-label">钻孔模型</span>
                        <b>{{ boreholes.length }}</b>
                    </button>
                    <div v-show="!collapsed.borehole" class="group-body">
                        <div class="group-toolbar">
                            <input v-model="boreholeKeyword" class="group-search" placeholder="筛选孔号 / 名称" />
                            <button class="ghost-button" type="button" @click="showBoreholeList = !showBoreholeList">{{
                                showBoreholeList ? '收起' : '展开' }}</button>
                        </div>
                        <button class="resource-row" type="button" :disabled="!boreholes.length"
                            @click="boreholesLoaded ? removeAllBoreholes() : loadAllBoreholes()">
                            <span class="resource-symbol borehole">B</span>
                            <span class="resource-name"><strong>全部钻孔</strong><small>{{ loadedBoreholeCount }} / {{
                                    boreholes.length }} 个孔位已加载</small></span>
                            <span class="load-state">{{ boreholesLoaded ? '移除全部' : '加载全部' }}</span>
                        </button>
                        <template v-if="showBoreholeList || boreholeKeyword">
                            <div v-for="item in filteredBoreholes" :key="item.id" class="resource-row"
                                :class="{ 'is-loaded': isBoreholeLoaded(item.id) }">
                                <button class="resource-main" :disabled="isBoreholeLoaded(item.id)"
                                    @click="loadBorehole(item)">
                                    <span class="resource-symbol borehole">·</span>
                                    <span class="resource-name"><strong>{{ item.name || item.code }}</strong><small>{{
                                            item.code }} · 孔深 {{ item.total_depth }} m</small></span>
                                    <span class="load-state">{{ isBoreholeLoaded(item.id) ? '已加载' : '加载' }}</span>
                                </button>
                                <button v-if="isBoreholeLoaded(item.id)" class="remove-state" title="从场景移除"
                                    @click="removeBorehole(item.id)">移除</button>
                            </div>
                            <p v-if="!filteredBoreholes.length" class="empty-copy">没有匹配的钻孔</p>
                            <p v-else-if="boreholeKeyword" class="empty-copy">匹配 {{ filteredBoreholes.length }} 个钻孔</p>
                        </template>
                        <p v-else class="empty-copy">展开后可单独加载指定钻孔</p>
                    </div>
                </section>
            </template>
        </div>
    </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { toBoreholeDetail, workspaceApi, type BoreholeRecord, type ModelAssetRecord } from '@/api/workspace'
import { useSceneStore } from '@/stores'
import type { BoreholeItem, ModelItem } from '@/types'

type RenderType = 'stratum' | 'workingface' | 'roadway'
type SceneType = RenderType | 'borehole'
/** 资源树中的模型分组:巷道 / 工作面 / 合并地层 / 分层地层 */
type AssetGroupKey = 'roadway' | 'workingface' | 'combined' | 'strata'

interface AssetGroupDef {
    key: AssetGroupKey
    label: string
    symbol: string
}

const ASSET_GROUPS: AssetGroupDef[] = [
    { key: 'roadway', label: '巷道模型', symbol: 'R' },
    { key: 'workingface', label: '工作面模型', symbol: 'W' },
    { key: 'combined', label: '合并地层模型', symbol: 'C' },
    { key: 'strata', label: '分层地层模型', symbol: 'M' },
]

const route = useRoute()
const router = useRouter()
const sceneStore = useSceneStore()
const { layerVisible, showEdges, stratumLayers } = storeToRefs(sceneStore)

const tab = ref<'scene' | 'assets'>(route.params.projectId === 'local' ? 'scene' : 'assets')
const selectedLayerKey = ref<string | null>(null)
const loading = ref(false)
const models = ref<ModelAssetRecord[]>([])
const boreholes = ref<BoreholeRecord[]>([])
const boreholeKeyword = ref('')
const showBoreholeList = ref(false)
const collapsed = reactive<Record<string, boolean>>({})
const projectId = computed(() => String(route.params.projectId))
const localMode = computed(() => projectId.value === 'local')
const selectedLayer = computed(() => stratumLayers.value.find(item => item.key === selectedLayerKey.value) || null)

// ==================== 资源分组 ====================

/** 把后端 model_type + metadata 归一化到资源树分组 */
function groupOf(asset: ModelAssetRecord): AssetGroupKey {
    if (asset.model_type === 'roadway') return 'roadway'
    if (asset.model_type === 'working_face') return 'workingface'
    return asset.metadata_json?.combined ? 'combined' : 'strata'
}

/** 三维场景中的渲染类型 */
function renderType(asset: ModelAssetRecord): RenderType {
    const group = groupOf(asset)
    return group === 'workingface' || group === 'roadway' ? group : 'stratum'
}

const modelGroups = computed(() => ASSET_GROUPS.map(def => ({
    ...def,
    items: models.value
        .filter(asset => groupOf(asset) === def.key)
        // 分层按 catalog 层序自浅至深排列,其余按名称稳定排序
        .sort(def.key === 'strata' ? byLayerIndex : byName),
})))

function byLayerIndex(a: ModelAssetRecord, b: ModelAssetRecord) {
    return (a.metadata_json?.layer_index ?? 0) - (b.metadata_json?.layer_index ?? 0)
}

function byName(a: ModelAssetRecord, b: ModelAssetRecord) {
    return a.name.localeCompare(b.name, 'zh-Hans-CN')
}

function toggleGroup(key: string) {
    collapsed[key] = !collapsed[key]
}

function subtitle(asset: ModelAssetRecord) {
    const meta = asset.metadata_json || {}
    const file = String(meta.source_file || '').split('/').pop()
    if (meta.combined) return `全层位合并${file ? ` · ${file}` : ''}`
    if (meta.layer_index != null) return `层序 ${meta.layer_index}${file ? ` · ${file}` : ''}`
    return file || asset.model_type
}

/** 分层模型用 catalog 配色作为符号色,便于与三维地层对应 */
function symbolStyle(asset: ModelAssetRecord) {
    const color = asset.metadata_json?.color_hex
    if (!color) return {}
    const readable = readableOnDark(color)
    return { borderColor: readable, color: readable }
}

/** catalog 中煤层的近黑配色在深色面板上不可见,按亮度抬升一档 */
function readableOnDark(hex: string) {
    const match = /^#?([0-9a-f]{6})$/i.exec(hex)
    if (!match) return hex
    const value = parseInt(match[1], 16)
    const channels = [(value >> 16) & 255, (value >> 8) & 255, value & 255]
    const luminance = (0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]) / 255
    if (luminance >= 0.35) return hex
    const lift = (channel: number) => Math.round(channel + (255 - channel) * 0.45)
    return `#${channels.map(c => lift(c).toString(16).padStart(2, '0')).join('')}`
}

// ==================== 模型加载 ====================

async function loadResources() {
    if (localMode.value) return
    loading.value = true
    try {
        [models.value, boreholes.value] = await Promise.all([
            workspaceApi.listModels(projectId.value),
            workspaceApi.listBoreholes(projectId.value),
        ])
    } finally { loading.value = false }
}

function loadModel(asset: ModelAssetRecord) {
    const type = renderType(asset)
    const model: ModelItem = {
        id: asset.id, name: asset.name, type, version: 'current', format: 'glb', description: '',
        fileName: `${asset.name}.glb`, fileUrl: workspaceApi.modelFileUrl(asset.id),
        metadata: asset.metadata_json,
    }
    sceneStore.requestLoadModel({ type, id: model.id, name: model.name, model })
}

function modelStatus(asset: ModelAssetRecord) {
    return sceneStore.getModelLoadStatus(renderType(asset), asset.id)
}

function removeModel(asset: ModelAssetRecord) {
    sceneStore.requestUnloadModel({ type: renderType(asset), id: asset.id })
}

// ==================== 钻孔 ====================

const filteredBoreholes = computed(() => {
    const keyword = boreholeKeyword.value.trim().toLowerCase()
    if (!keyword) return boreholes.value
    return boreholes.value.filter(item => `${item.name} ${item.code}`.toLowerCase().includes(keyword))
})

const loadedBoreholeCount = computed(() => boreholes.value.filter(item => isBoreholeLoaded(item.id)).length)

// 任一钻孔在场景中即视为"已加载"，此时整组按钮切换为移除全部
const boreholesLoaded = computed(() => loadedBoreholeCount.value > 0)

function isBoreholeLoaded(id: string) {
    return sceneStore.getModelLoadStatus('borehole', id).loaded
}

function loadBorehole(item: BoreholeRecord) {
    // 单孔操作后整组标记失效,否则再次点击"加载全部"会被去重拦截
    sceneStore.clearLoadStatus('borehole', '__all__')
    sceneStore.requestLoadModel({ type: 'borehole', id: item.id, name: item.name || item.code, boreholeList: [toBoreholeDetail(item)] })
}

function removeBorehole(id: string) {
    sceneStore.clearLoadStatus('borehole', '__all__')
    sceneStore.requestUnloadModel({ type: 'borehole', id })
}

function removeAllBoreholes() {
    sceneStore.requestUnloadModel({ type: 'borehole', id: '__all__' })
}

function loadAllBoreholes() {
    const items: BoreholeItem[] = boreholes.value.map(toBoreholeDetail)
    sceneStore.requestLoadModel({ type: 'borehole', id: '__all__', name: '全部钻孔', boreholeList: items })
}

// ==================== 场景树 ====================

interface SceneChild {
    key: string
    label: string
    color: string
    remove: () => void
}

const DEFAULT_CHILD_COLOR: Record<RenderType, string> = {
    stratum: '#8a6740',
    workingface: '#88614f',
    roadway: '#6b7f8c',
}

/** 已加载到场景中的非地层模型(含钻孔),按类型归组 */
function loadedChildren(type: SceneType): SceneChild[] {
    if (type === 'borehole') {
        return boreholes.value
            .filter(item => isBoreholeLoaded(item.id))
            .map(item => ({
                key: item.id,
                label: item.name || item.code,
                color: '#527b70',
                remove: () => removeBorehole(item.id),
            }))
    }
    return models.value
        .filter(asset => renderType(asset) === type && modelStatus(asset).loaded)
        .map(asset => ({
            key: asset.id,
            label: asset.name,
            color: asset.metadata_json?.color_hex || DEFAULT_CHILD_COLOR[type],
            remove: () => removeModel(asset),
        }))
}

const SCENE_GROUPS: { type: SceneType; label: string }[] = [
    { type: 'stratum', label: '地层模型' },
    { type: 'borehole', label: '钻孔' },
    { type: 'workingface', label: '工作面' },
    { type: 'roadway', label: '巷道' },
]

const sceneGroups = computed(() => SCENE_GROUPS.map(group => {
    const items = group.type === 'stratum' ? [] : loadedChildren(group.type)
    return {
        ...group,
        items,
        count: group.type === 'stratum' ? stratumLayers.value.length : items.length,
    }
}))

const sceneTotal = computed(() => sceneGroups.value.reduce((sum, group) => sum + group.count, 0))

// ==================== 地层单元材质 ====================

function setSelectedLayerColor(value: string | null) {
    if (selectedLayer.value && value) sceneStore.updateStratumLayer(selectedLayer.value.key, { color: value })
}

function setSelectedLayerOpacity(value: number | number[]) {
    if (selectedLayer.value && typeof value === 'number') {
        sceneStore.updateStratumLayer(selectedLayer.value.key, { opacity: value / 100 })
    }
}

onMounted(loadResources)
</script>

<style scoped>
.resource-explorer {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #121714;
    border-right: 1px solid var(--studio-border);
}

.panel-heading {
    height: 70px;
    padding: 15px 16px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--studio-border);
}

.panel-kicker {
    font: 9px Bahnschrift, sans-serif;
    letter-spacing: .18em;
    color: var(--studio-copper);
}

.panel-heading h2 {
    font-size: 15px;
    margin-top: 3px;
}

.icon-button {
    width: 30px;
    height: 30px;
    border: 1px solid var(--studio-border);
    background: #191f1b;
    color: #9da69e;
    cursor: pointer;
}

.panel-tabs {
    height: 38px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    border-bottom: 1px solid var(--studio-border);
}

.panel-tabs button {
    border: 0;
    background: transparent;
    color: #6f7971;
    font-size: 12px;
    cursor: pointer;
    position: relative;
}

.panel-tabs button.active {
    color: #e1ded2;
}

.panel-tabs button.active::after {
    content: "";
    position: absolute;
    left: 25%;
    right: 25%;
    bottom: -1px;
    height: 2px;
    background: var(--studio-copper);
}

.panel-body {
    flex: 1;
    overflow: auto;
    padding: 12px;
}

/* ---------- 场景树 ---------- */
.tree-root {
    height: 34px;
    display: flex;
    align-items: center;
    gap: 7px;
    color: #d4d4cc;
    border-bottom: 1px solid #29302a;
}

.tree-root small {
    margin-left: auto;
    color: #5f685f;
    font-size: 9px;
}

.tree-caret {
    color: #956b3d;
}

.tree-layer {
    height: 39px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 1px solid #252b26;
    color: #aab1aa;
    font-size: 11px;
}

.tree-layer b {
    margin-left: auto;
    color: #59625b;
    font: 9px Bahnschrift;
}

.eye-button {
    width: 24px;
    border: 0;
    background: transparent;
    color: #485149;
    cursor: pointer;
}

.eye-button.visible {
    color: #b98a52;
}

.layer-dot {
    width: 7px;
    height: 7px;
    background: #8a6740;
    flex: none;
}

.layer-dot.borehole {
    background: #527b70;
}

.layer-dot.workingface {
    background: #88614f;
}

.layer-dot.roadway {
    background: #6b7f8c;
}

.scene-children {
    margin: 2px 0 8px 34px;
    border-left: 1px solid #343b35;
}

.scene-child {
    height: 29px;
    display: flex;
    align-items: center;
    gap: 7px;
    padding-right: 6px;
    border-bottom: 1px solid #232923;
    color: #8d958e;
    font-size: 10px;
}

.scene-child i {
    width: 7px;
    height: 7px;
    margin-left: -4px;
    border: 1px solid #111;
    flex: none;
}

.scene-child span {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.scene-child-remove {
    flex: none;
    border: 0;
    background: transparent;
    color: #7d5743;
    font-size: 10px;
    cursor: pointer;
}

.scene-child-remove:hover {
    color: #ff8a5c;
}

.strata-tree {
    margin: 4px 0 12px 34px;
    border-left: 1px solid #343b35;
}

.strata-row {
    display: flex;
    border-bottom: 1px solid #252b26;
}

.strata-row.active {
    background: #1b211c;
}

.strata-row button {
    height: 31px;
    display: flex;
    align-items: center;
    border: 0;
    background: transparent;
    color: #7d867e;
    font-size: 10px;
    cursor: pointer;
}

.strata-row button:hover {
    color: #d5d4cc;
}

.layer-eye {
    width: 28px;
    justify-content: center;
}

.layer-select {
    min-width: 0;
    flex: 1;
    gap: 7px;
    text-align: left;
}

.layer-select i {
    width: 7px;
    height: 7px;
    margin-left: -4px;
    border: 1px solid #111;
    flex: none;
}

.layer-select span {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.layer-select small {
    padding-right: 7px;
    font: 8px Bahnschrift;
    color: #525a53;
}

.layer-editor {
    margin: 8px 0 12px;
    padding: 10px;
    border: 1px solid #3a413b;
    background: #171c18;
}

.editor-heading {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 9px;
    color: #c6c9c1;
    font-size: 10px;
}

.editor-heading span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.editor-heading small {
    color: #6c756d;
    white-space: nowrap;
}

.layer-editor label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 7px 0;
    color: #858e86;
    font-size: 10px;
}

.layer-editor label b {
    font: 9px Bahnschrift;
    color: #bd8950;
}

.scene-options {
    padding-top: 12px;
    border-top: 1px solid #303731;
}

.scene-options label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 10px;
    color: #818a82;
    margin: 7px 0;
}

/* ---------- 资源树 ---------- */
.source-note {
    margin-bottom: 14px;
    padding: 10px;
    border-left: 2px solid #8b6337;
    background: #181d19;
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.source-note b {
    font: 9px Bahnschrift;
    color: #bc8950;
    letter-spacing: .09em;
}

.source-note span {
    font-size: 9px;
    color: #687169;
}

.resource-group {
    margin-bottom: 18px;
}

.group-title {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 7px 3px;
    border: 0;
    border-bottom: 1px solid #2b322c;
    background: transparent;
    color: #879088;
    font-size: 11px;
    letter-spacing: .08em;
    text-align: left;
    cursor: pointer;
}

.group-title:hover {
    color: #c3c8c1;
}

.group-title b {
    margin-left: auto;
    color: #655d4e;
    font: 10px Bahnschrift, sans-serif;
}

.group-caret {
    width: 10px;
    color: #956b3d;
    transition: transform .15s ease;
}

.group-caret.collapsed {
    transform: rotate(-90deg);
}

.group-dot {
    width: 7px;
    height: 7px;
    flex: none;
}

.group-dot.roadway {
    background: #6b7f8c;
}

.group-dot.workingface {
    background: #88614f;
}

.group-dot.combined {
    background: #c49154;
}

.group-dot.strata {
    background: #8a6740;
}

.group-dot.borehole {
    background: #527b70;
}

.group-label {
    flex: 1;
}

.group-body {
    padding-top: 2px;
}

.group-toolbar {
    display: flex;
    gap: 6px;
    padding: 8px 0 6px;
}

.group-search {
    flex: 1;
    min-width: 0;
    height: 26px;
    padding: 0 8px;
    border: 1px solid #303832;
    background: #171c18;
    color: #c3c8c1;
    font-size: 10px;
}

.group-search::placeholder {
    color: #586158;
}

.ghost-button {
    flex: none;
    padding: 0 9px;
    height: 26px;
    border: 1px solid #3a413b;
    background: #191f1b;
    color: #9aa29a;
    font-size: 10px;
    cursor: pointer;
}

.ghost-button:hover {
    color: #d7d4ca;
    border-color: #4d564d;
}

.resource-row {
    width: 100%;
    display: flex;
    align-items: center;
    border-top: 1px solid #272d28;
    color: #bfc5bd;
}

.resource-row:hover {
    background: #1b211d;
    color: #eee8db;
}

.resource-row:disabled {
    cursor: default;
    opacity: .62;
}

.resource-main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 7px;
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
    cursor: pointer;
}

.resource-main:disabled {
    cursor: default;
}

.resource-row.is-loaded .resource-main {
    cursor: default;
    opacity: .62;
}

.remove-state {
    flex: none;
    padding: 9px 10px;
    border: 0;
    background: transparent;
    color: #b06a4a;
    font: 10px Bahnschrift, sans-serif;
    cursor: pointer;
}

.remove-state:hover {
    color: #ff8a5c;
}

.resource-symbol {
    width: 25px;
    height: 25px;
    flex: none;
    display: grid;
    place-items: center;
    border: 1px solid #765a36;
    color: #c49154;
    font: 10px Bahnschrift, sans-serif;
}

.resource-symbol.borehole {
    border-color: #47645d;
    color: #79a395;
}

.resource-symbol.roadway {
    border-color: #51636e;
    color: #8aa6b5;
}

.resource-symbol.workingface {
    border-color: #6d4f41;
    color: #b08a76;
}

.resource-symbol.combined {
    border-color: #8b6a3c;
    color: #d3a462;
}

.resource-name {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
}

.resource-name strong {
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.resource-name small {
    font-size: 9px;
    color: #687169;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.load-state {
    font: 9px Bahnschrift;
    color: #9a7549;
    white-space: nowrap;
}

.empty-copy {
    padding: 12px 6px;
    color: #59625b;
    font-size: 11px;
}

.local-note {
    min-height: 210px;
    padding: 18px;
    border: 1px dashed #3c453e;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 9px;
    color: #747e76;
}

.local-note .el-icon {
    font-size: 28px;
    color: #aa7a43;
}

.local-note strong {
    color: #c5c7bf;
}

.local-note span {
    font-size: 11px;
    max-width: 200px;
    line-height: 1.6;
}

.local-note button {
    margin-top: 4px;
    padding: 7px 11px;
    border: 1px solid #725534;
    background: #1b201c;
    color: #c6965c;
    cursor: pointer;
}
</style>
