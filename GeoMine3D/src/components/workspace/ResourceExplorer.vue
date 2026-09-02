<template>
    <aside class="resource-explorer">
        <div class="panel-heading">
            <div><span class="panel-kicker">PROJECT DATA</span><h2>资源与图层</h2></div>
            <button class="icon-button" title="刷新" @click="loadResources"><el-icon><Refresh /></el-icon></button>
        </div>
        <div class="panel-tabs">
            <button :class="{ active: tab === 'scene' }" @click="tab = 'scene'">场景</button>
            <button :class="{ active: tab === 'assets' }" @click="tab = 'assets'">资源</button>
        </div>

        <div v-if="tab === 'scene'" class="panel-body scene-tree">
            <div class="tree-root"><span class="tree-caret">⌄</span><strong>当前场景</strong><small>{{ stratumLayers.length }} 单元</small></div>
            <div v-for="layer in layerGroups" :key="layer.type" class="tree-layer">
                <button class="eye-button" :class="{visible:layerVisible[layer.type]}" @click="sceneStore.setLayerVisible(layer.type, !layerVisible[layer.type])"><el-icon><View /></el-icon></button>
                <span class="layer-dot" :class="layer.type"></span>
                <span>{{ layer.label }}</span>
                <b>{{ layer.type === 'stratum' ? stratumLayers.length : '—' }}</b>
            </div>
            <div v-if="stratumLayers.length" class="strata-tree">
                <div v-for="item in stratumLayers" :key="item.key" class="strata-row" :class="{active:selectedLayerKey===item.key}">
                    <button class="layer-eye" :title="item.visible ? '隐藏' : '显示'" @click="sceneStore.updateStratumLayer(item.key,{visible:!item.visible})"><el-icon><View /></el-icon></button>
                    <button class="layer-select" @click="selectedLayerKey = item.key">
                        <i :style="{background:item.color}"></i><span>{{ item.layerName }}</span><small>{{ item.visible ? 'ON' : 'OFF' }}</small>
                    </button>
                </div>
                <div v-if="selectedLayer" class="layer-editor">
                    <div class="editor-heading"><span>{{ selectedLayer.layerName }}</span><small>单元材质</small></div>
                    <label><span>颜色</span><el-color-picker :model-value="selectedLayer.color" size="small" @change="setSelectedLayerColor" /></label>
                    <label><span>透明度</span><b>{{ Math.round(selectedLayer.opacity*100) }}%</b></label>
                    <el-slider :model-value="selectedLayer.opacity*100" :show-tooltip="false" @input="setSelectedLayerOpacity" />
                </div>
            </div>
            <div class="scene-options">
                <label><span>显示地层边缘</span><el-switch :model-value="showEdges" size="small" @change="sceneStore.setShowEdges($event as boolean)" /></label>
            </div>
        </div>
        <div v-else class="panel-body" v-loading="loading">
            <template v-if="localMode">
                <div class="local-note"><el-icon><UploadFilled /></el-icon><strong>本地临时工作区</strong><span>这里只用于拖入电脑中的 GLB。要加载 server 静态模型和钻孔，请从项目中心进入数据库项目。</span><button @click="router.push('/projects')">返回项目中心</button></div>
            </template>
            <template v-else>
                <section class="resource-group">
                    <div class="source-note"><b>SERVER / STATIC / MODELS</b><span>已同步到数据库资源目录</span></div>
                    <div class="group-title"><span>静态地质模型</span><b>{{ models.length }}</b></div>
                    <div v-for="model in models" :key="model.id" class="resource-row" :class="{ 'is-loaded': modelStatus(model).loaded }">
                        <button class="resource-main" :disabled="modelStatus(model).loading || modelStatus(model).loaded" @click="loadModel(model)">
                            <span class="resource-symbol strata">M</span>
                            <span class="resource-name"><strong>{{ model.name }}</strong><small>{{ model.model_type }}</small></span>
                            <span class="load-state">{{ modelStatus(model).loaded ? '已加载' : modelStatus(model).loading ? '加载中' : '加载' }}</span>
                        </button>
                        <button v-if="modelStatus(model).loaded" class="remove-state" title="从场景移除" @click="removeModel(model)">移除</button>
                    </div>
                    <p v-if="!models.length" class="empty-copy">当前项目暂无模型资产</p>
                </section>
                <section class="resource-group">
                    <div class="group-title"><span>钻孔数据</span><b>{{ boreholes.length }}</b></div>
                    <button class="resource-row" :disabled="!boreholes.length" @click="boreholesLoaded ? removeAllBoreholes() : loadAllBoreholes()">
                        <span class="resource-symbol borehole">B</span>
                        <span class="resource-name"><strong>全部钻孔</strong><small>{{ boreholes.length }} 个孔位</small></span>
                        <span class="load-state">{{ boreholesLoaded ? '移除全部' : '加载全部' }}</span>
                    </button>
                </section>
            </template>
        </div>
    </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { toBoreholeDetail, workspaceApi, type BoreholeRecord, type ModelAssetRecord } from '@/api/workspace'
import { useSceneStore } from '@/stores'
import type { BoreholeItem, ModelItem } from '@/types'

const route = useRoute()
const router = useRouter()
const sceneStore = useSceneStore()
const { layerVisible, showEdges, stratumLayers } = storeToRefs(sceneStore)
const layerGroups = [
    { type: 'stratum' as const, label: '地层模型' },
    { type: 'borehole' as const, label: '钻孔' },
    { type: 'workingface' as const, label: '工作面' },
]
const tab = ref<'scene' | 'assets'>(route.params.projectId === 'local' ? 'scene' : 'assets')
const selectedLayerKey = ref<string | null>(null)
const loading = ref(false)
const models = ref<ModelAssetRecord[]>([])
const boreholes = ref<BoreholeRecord[]>([])
const projectId = computed(() => String(route.params.projectId))
const localMode = computed(() => projectId.value === 'local')
const selectedLayer = computed(() => stratumLayers.value.find(item => item.key === selectedLayerKey.value) || null)

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
    const type = asset.model_type === 'working_face' ? 'workingface' : 'stratum'
    const model: ModelItem = {
        id: asset.id, name: asset.name, type, version: 'current', format: 'glb', description: '',
        fileName: `${asset.name}.glb`, fileUrl: workspaceApi.modelFileUrl(asset.id),
    }
    sceneStore.requestLoadModel({ type, id: model.id, name: model.name, model })
}

function modelStatus(asset: ModelAssetRecord) {
    const type = asset.model_type === 'working_face' ? 'workingface' : 'stratum'
    return sceneStore.getModelLoadStatus(type, asset.id)
}

function unloadType(asset: ModelAssetRecord): 'stratum' | 'workingface' {
    return asset.model_type === 'working_face' ? 'workingface' : 'stratum'
}

function removeModel(asset: ModelAssetRecord) {
    sceneStore.requestUnloadModel({ type: unloadType(asset), id: asset.id })
}

// 任一钻孔在场景中即视为"已加载"，此时按钮切换为移除全部
const boreholesLoaded = computed(() => boreholes.value.some(item => sceneStore.getModelLoadStatus('borehole', item.id).loaded))

function removeAllBoreholes() {
    sceneStore.requestUnloadModel({ type: 'borehole', id: '__all__' })
}

function loadAllBoreholes() {
    const items: BoreholeItem[] = boreholes.value.map(toBoreholeDetail)
    sceneStore.requestLoadModel({ type: 'borehole', id: '__all__', name: '全部钻孔', boreholeList: items })
}

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
.resource-explorer { height:100%; display:flex; flex-direction:column; background:#121714; border-right:1px solid var(--studio-border); }
.panel-heading { height:70px; padding:15px 16px 12px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--studio-border); }.panel-kicker{font:9px Bahnschrift,sans-serif;letter-spacing:.18em;color:var(--studio-copper)}.panel-heading h2{font-size:15px;margin-top:3px}.icon-button{width:30px;height:30px;border:1px solid var(--studio-border);background:#191f1b;color:#9da69e;cursor:pointer}.panel-tabs{height:38px;display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid var(--studio-border)}.panel-tabs button{border:0;background:transparent;color:#6f7971;font-size:12px;cursor:pointer;position:relative}.panel-tabs button.active{color:#e1ded2}.panel-tabs button.active::after{content:"";position:absolute;left:25%;right:25%;bottom:-1px;height:2px;background:var(--studio-copper)}.panel-body{flex:1;overflow:auto;padding:12px}.tree-root{height:34px;display:flex;align-items:center;gap:7px;color:#d4d4cc;border-bottom:1px solid #29302a}.tree-root small{margin-left:auto;color:#5f685f;font-size:9px}.tree-caret{color:#956b3d}.tree-layer{height:39px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #252b26;color:#aab1aa;font-size:11px}.tree-layer b{margin-left:auto;color:#59625b;font:9px Bahnschrift}.eye-button{width:24px;border:0;background:transparent;color:#485149;cursor:pointer}.eye-button.visible{color:#b98a52}.layer-dot{width:7px;height:7px;background:#8a6740}.layer-dot.borehole{background:#527b70}.layer-dot.workingface{background:#88614f}.strata-tree{margin:4px 0 12px 34px;border-left:1px solid #343b35}.strata-row{display:flex;border-bottom:1px solid #252b26}.strata-row.active{background:#1b211c}.strata-row button{height:31px;display:flex;align-items:center;border:0;background:transparent;color:#7d867e;font-size:10px;cursor:pointer}.strata-row button:hover{color:#d5d4cc}.layer-eye{width:28px;justify-content:center}.layer-select{min-width:0;flex:1;gap:7px;text-align:left}.layer-select i{width:7px;height:7px;margin-left:-4px;border:1px solid #111;flex:none}.layer-select span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.layer-select small{padding-right:7px;font:8px Bahnschrift;color:#525a53}.layer-editor{margin:8px 0 12px;padding:10px;border:1px solid #3a413b;background:#171c18}.editor-heading{display:flex;justify-content:space-between;gap:8px;margin-bottom:9px;color:#c6c9c1;font-size:10px}.editor-heading span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.editor-heading small{color:#6c756d;white-space:nowrap}.layer-editor label{display:flex;align-items:center;justify-content:space-between;margin:7px 0;color:#858e86;font-size:10px}.layer-editor label b{font:9px Bahnschrift;color:#bd8950}.scene-options{padding-top:12px;border-top:1px solid #303731}.scene-options label{display:flex;align-items:center;justify-content:space-between;font-size:10px;color:#818a82;margin:7px 0}.scene-options label b{font:9px Bahnschrift;color:#bd8950}.resource-group{margin-bottom:22px}.source-note{margin-bottom:14px;padding:10px;border-left:2px solid #8b6337;background:#181d19;display:flex;flex-direction:column;gap:3px}.source-note b{font:9px Bahnschrift;color:#bc8950;letter-spacing:.09em}.source-note span{font-size:9px;color:#687169}.group-title{display:flex;justify-content:space-between;align-items:center;padding:0 3px 8px;color:#879088;font-size:11px;text-transform:uppercase;letter-spacing:.08em}.group-title b{font:10px Bahnschrift,sans-serif;color:#655d4e}.resource-row{width:100%;display:flex;align-items:center;border-top:1px solid #272d28;color:#bfc5bd}.resource-row:hover{background:#1b211d;color:#eee8db}.resource-row:disabled{cursor:default;opacity:.62}.resource-main{flex:1;min-width:0;display:flex;align-items:center;gap:10px;padding:9px 7px;border:0;background:transparent;color:inherit;text-align:left;cursor:pointer}.resource-row.is-loaded .resource-main{cursor:default;opacity:.62}.remove-state{flex:none;padding:9px 10px;border:0;background:transparent;color:#b06a4a;font:10px Bahnschrift,sans-serif;cursor:pointer}.remove-state:hover{color:#ff8a5c}.resource-symbol{width:25px;height:25px;display:grid;place-items:center;border:1px solid #765a36;color:#c49154;font:10px Bahnschrift,sans-serif}.resource-symbol.borehole{border-color:#47645d;color:#79a395}.resource-name{flex:1;min-width:0;display:flex;flex-direction:column}.resource-name strong{font-size:12px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.resource-name small{font-size:9px;color:#687169;text-transform:uppercase}.load-state{font:9px Bahnschrift;color:#9a7549;white-space:nowrap}.empty-copy{padding:16px 6px;color:#59625b;font-size:11px}.local-note{min-height:210px;padding:18px;border:1px dashed #3c453e;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:9px;color:#747e76}.local-note .el-icon{font-size:28px;color:#aa7a43}.local-note strong{color:#c5c7bf}.local-note span{font-size:11px;max-width:200px;line-height:1.6}.local-note button{margin-top:4px;padding:7px 11px;border:1px solid #725534;background:#1b201c;color:#c6965c;cursor:pointer}
</style>
