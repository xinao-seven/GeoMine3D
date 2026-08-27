<template>
    <section class="analysis-dock">
        <nav class="dock-tabs">
            <button v-for="item in tabs" :key="item.id" :class="{ active: activeDock === item.id }" @click="store.openDock(item.id)">
                <el-icon><component :is="item.icon" /></el-icon>{{ item.label }}
            </button>
            <button class="dock-close" title="收起" @click="store.toggleBottom"><el-icon><ArrowDown /></el-icon></button>
        </nav>
        <div class="dock-content">
            <template v-if="activeDock === 'overview'">
                <div class="metric"><span>SCENE OBJECTS</span><strong>{{ objectCount }}</strong><small>已登记对象</small></div>
                <div class="metric"><span>ACTIVE LAYERS</span><strong>{{ activeLayerCount }}</strong><small>可见图层</small></div>
                <div class="metric"><span>MEASUREMENTS</span><strong>{{ measurements.length }}</strong><small>测量记录</small></div>
                <div class="activity-graph"><i v-for="n in 28" :key="n" :style="{height:`${18 + ((n * 19) % 62)}%`}"></i></div>
            </template>
            <template v-else-if="activeDock === 'borehole'">
                <BoreholeChart v-if="currentDetail" :borehole="currentDetail" class="borehole-chart" />
                <div v-else class="dock-empty">选择一个钻孔后显示地层柱状图</div>
            </template>
            <template v-else-if="activeDock === 'table'">
                <div class="data-table-head"><span>对象名称</span><span>类型</span><span>状态</span></div>
                <div class="data-row" v-if="selectedObject"><span>{{ selectedObject.name }}</span><span>{{ selectedObject.type }}</span><span>SELECTED</span></div>
                <div class="dock-empty" v-else>场景对象属性表将在加载数据后显示</div>
            </template>
            <template v-else>
                <div class="metric"><span>FPS</span><strong>--</strong><small>等待渲染器采样</small></div>
                <div class="metric"><span>DRAW CALLS</span><strong>--</strong><small>renderer.info</small></div>
                <div class="metric"><span>TRIANGLES</span><strong>--</strong><small>当前帧</small></div>
                <div class="performance-note">性能采样器将在 GeoEngine 重构阶段接入。</div>
            </template>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import BoreholeChart from '@/components/charts/BoreholeChart.vue'
import { useBoreholeStore, useSceneStore, useWorkspaceStore } from '@/stores'
import type { WorkspaceDock } from '@/stores/workspaceStore'
const store = useWorkspaceStore(); const sceneStore = useSceneStore(); const boreholeStore = useBoreholeStore()
const { activeDock } = storeToRefs(store); const { selectedObject, layerVisible, measurements, modelLoadStatus } = storeToRefs(sceneStore); const { currentDetail } = storeToRefs(boreholeStore)
const tabs: Array<{id:WorkspaceDock;label:string;icon:string}> = [{id:'overview',label:'场景概览',icon:'DataAnalysis'},{id:'borehole',label:'钻孔柱状图',icon:'Histogram'},{id:'table',label:'属性表',icon:'Grid'},{id:'performance',label:'性能',icon:'Odometer'}]
const activeLayerCount = computed(() => Object.values(layerVisible.value).filter(Boolean).length)
const objectCount = computed(() => Object.values(modelLoadStatus.value).filter(item => item.loaded).length)
</script>

<style scoped>
.analysis-dock{height:100%;display:flex;flex-direction:column;background:#101411;border-top:1px solid var(--studio-border)}.dock-tabs{height:36px;display:flex;border-bottom:1px solid var(--studio-border);padding-left:8px}.dock-tabs button{height:36px;padding:0 14px;border:0;border-right:1px solid #282e29;background:transparent;color:#707970;font-size:10px;display:flex;gap:7px;align-items:center;cursor:pointer}.dock-tabs button.active{color:#dfd9ca;background:#1a201b;box-shadow:inset 0 2px var(--studio-copper)}.dock-tabs .dock-close{margin-left:auto;border-left:1px solid #282e29}.dock-content{flex:1;min-height:0;display:flex;align-items:stretch;padding:12px 16px;gap:12px}.metric{width:180px;padding:13px 15px;border-left:2px solid #735431;background:#151a16;display:flex;flex-direction:column}.metric span{font:9px Bahnschrift;letter-spacing:.12em;color:#667068}.metric strong{font:28px Bahnschrift;color:#d8d6cc;margin:4px 0}.metric small{color:#5e665f;font-size:9px}.activity-graph{flex:1;display:flex;align-items:end;gap:4px;padding:18px;background:repeating-linear-gradient(to bottom,transparent 0 24px,#232824 25px)}.activity-graph i{flex:1;background:#4f6658;opacity:.7}.borehole-chart{width:100%;height:100%}.dock-empty,.performance-note{margin:auto;color:#677068;font-size:11px}.data-table-head,.data-row{display:grid;grid-template-columns:2fr 1fr 1fr;width:100%;padding:8px 12px;font-size:10px}.data-table-head{color:#646d65;border-bottom:1px solid #2b312c}.data-row{color:#b9beb7;background:#151a16}.performance-note{margin:0;flex:1;display:grid;place-items:center;border:1px dashed #313832}
</style>
