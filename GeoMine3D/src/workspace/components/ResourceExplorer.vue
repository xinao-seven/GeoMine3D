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
                <button v-for="item in stratumLayers" :key="item.key" @click="sceneStore.updateStratumLayer(item.key,{visible:!item.visible})">
                    <i :style="{background:item.color}"></i><span>{{ item.layerName }}</span><small>{{ item.visible ? 'ON' : 'OFF' }}</small>
                </button>
            </div>
            <div class="scene-options">
                <label><span>显示地层边缘</span><el-switch :model-value="showEdges" size="small" @change="sceneStore.setShowEdges($event as boolean)" /></label>
                <label><span>地层透明度</span><b>{{ Math.round(opacity.stratum*100) }}%</b></label>
                <el-slider :model-value="opacity.stratum*100" :show-tooltip="false" @input="setStratumOpacity" />
            </div>
        </div>
        <div v-else class="panel-body" v-loading="loading">
            <template v-if="localMode">
                <div class="local-note"><el-icon><UploadFilled /></el-icon><strong>本地工作区</strong><span>将 GLB 文件拖入中央视口即可加载。</span></div>
            </template>
            <template v-else>
                <section class="resource-group">
                    <div class="group-title"><span>模型资产</span><b>{{ models.length }}</b></div>
                    <button v-for="model in models" :key="model.id" class="resource-row" @click="loadModel(model)">
                        <span class="resource-symbol strata">M</span>
                        <span class="resource-name"><strong>{{ model.name }}</strong><small>{{ model.model_type }}</small></span>
                        <el-icon><Download /></el-icon>
                    </button>
                    <p v-if="!models.length" class="empty-copy">当前项目暂无模型资产</p>
                </section>
                <section class="resource-group">
                    <div class="group-title"><span>钻孔数据</span><b>{{ boreholes.length }}</b></div>
                    <button class="resource-row" :disabled="!boreholes.length" @click="loadAllBoreholes">
                        <span class="resource-symbol borehole">B</span>
                        <span class="resource-name"><strong>全部钻孔</strong><small>{{ boreholes.length }} 个孔位</small></span>
                        <el-icon><Download /></el-icon>
                    </button>
                </section>
            </template>
        </div>
    </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import { workspaceApi, type BoreholeRecord, type ModelAssetRecord } from '@/api/workspace'
import { useSceneStore } from '@/stores'
import type { BoreholeItem, ModelItem } from '@/types'

const route = useRoute()
const sceneStore = useSceneStore()
const { layerVisible, opacity, showEdges, stratumLayers } = storeToRefs(sceneStore)
const layerGroups = [
    { type: 'stratum' as const, label: '地层模型' },
    { type: 'borehole' as const, label: '钻孔' },
    { type: 'workingface' as const, label: '工作面' },
]
const tab = ref<'scene' | 'assets'>('scene')
const loading = ref(false)
const models = ref<ModelAssetRecord[]>([])
const boreholes = ref<BoreholeRecord[]>([])
const projectId = computed(() => String(route.params.projectId))
const localMode = computed(() => projectId.value === 'local')

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

function loadAllBoreholes() {
    const items: BoreholeItem[] = boreholes.value.map(item => ({
        id: item.id, name: item.name || item.code, totalDepth: item.total_depth,
        layerCount: item.segments.length, location: { x: item.x, y: item.y, z: item.z },
    }))
    sceneStore.requestLoadModel({ type: 'borehole', id: '__all__', name: '全部钻孔', boreholeList: items })
}

function setStratumOpacity(value: number | number[]) {
    if (typeof value === 'number') sceneStore.setOpacity('stratum', value / 100)
}

onMounted(loadResources)
</script>

<style scoped>
.resource-explorer { height:100%; display:flex; flex-direction:column; background:#121714; border-right:1px solid var(--studio-border); }
.panel-heading { height:70px; padding:15px 16px 12px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--studio-border); }.panel-kicker{font:9px Bahnschrift,sans-serif;letter-spacing:.18em;color:var(--studio-copper)}.panel-heading h2{font-size:15px;margin-top:3px}.icon-button{width:30px;height:30px;border:1px solid var(--studio-border);background:#191f1b;color:#9da69e;cursor:pointer}.panel-tabs{height:38px;display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid var(--studio-border)}.panel-tabs button{border:0;background:transparent;color:#6f7971;font-size:12px;cursor:pointer;position:relative}.panel-tabs button.active{color:#e1ded2}.panel-tabs button.active::after{content:"";position:absolute;left:25%;right:25%;bottom:-1px;height:2px;background:var(--studio-copper)}.panel-body{flex:1;overflow:auto;padding:12px}.tree-root{height:34px;display:flex;align-items:center;gap:7px;color:#d4d4cc;border-bottom:1px solid #29302a}.tree-root small{margin-left:auto;color:#5f685f;font-size:9px}.tree-caret{color:#956b3d}.tree-layer{height:39px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #252b26;color:#aab1aa;font-size:11px}.tree-layer b{margin-left:auto;color:#59625b;font:9px Bahnschrift}.eye-button{width:24px;border:0;background:transparent;color:#485149;cursor:pointer}.eye-button.visible{color:#b98a52}.layer-dot{width:7px;height:7px;background:#8a6740}.layer-dot.borehole{background:#527b70}.layer-dot.workingface{background:#88614f}.strata-tree{margin:4px 0 12px 34px;border-left:1px solid #343b35}.strata-tree button{width:100%;height:29px;display:flex;align-items:center;gap:7px;border:0;background:transparent;color:#7d867e;font-size:10px;text-align:left;cursor:pointer}.strata-tree button:hover{color:#d5d4cc;background:#191f1a}.strata-tree i{width:7px;height:7px;margin-left:-4px;border:1px solid #111}.strata-tree span{flex:1}.strata-tree small{font:8px Bahnschrift;color:#525a53}.scene-options{padding-top:12px;border-top:1px solid #303731}.scene-options label{display:flex;align-items:center;justify-content:space-between;font-size:10px;color:#818a82;margin:7px 0}.scene-options label b{font:9px Bahnschrift;color:#bd8950}.resource-group{margin-bottom:22px}.group-title{display:flex;justify-content:space-between;align-items:center;padding:0 3px 8px;color:#879088;font-size:11px;text-transform:uppercase;letter-spacing:.08em}.group-title b{font:10px Bahnschrift,sans-serif;color:#655d4e}.resource-row{width:100%;display:flex;align-items:center;gap:10px;padding:9px 7px;border:0;border-top:1px solid #272d28;background:transparent;color:#bfc5bd;text-align:left;cursor:pointer}.resource-row:hover{background:#1b211d;color:#eee8db}.resource-symbol{width:25px;height:25px;display:grid;place-items:center;border:1px solid #765a36;color:#c49154;font:10px Bahnschrift,sans-serif}.resource-symbol.borehole{border-color:#47645d;color:#79a395}.resource-name{flex:1;min-width:0;display:flex;flex-direction:column}.resource-name strong{font-size:12px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.resource-name small{font-size:9px;color:#687169;text-transform:uppercase}.empty-copy{padding:16px 6px;color:#59625b;font-size:11px}.local-note{min-height:190px;border:1px dashed #3c453e;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:9px;color:#747e76}.local-note .el-icon{font-size:28px;color:#aa7a43}.local-note strong{color:#c5c7bf}.local-note span{font-size:11px;max-width:170px;line-height:1.6}
</style>
