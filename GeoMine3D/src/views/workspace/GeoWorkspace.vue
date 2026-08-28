<template>
    <main class="geo-workspace" @keydown.ctrl.k.prevent="workspace.commandPaletteVisible = true">
        <header class="workspace-header">
            <button class="brand-button" @click="router.push('/projects')"><span class="brand-glyph">G</span><b>GEOMINE</b></button>
            <div class="project-identity"><span>ACTIVE PROJECT</span><strong>{{ projectName }}</strong></div>
            <button class="command-trigger" @click="workspace.commandPaletteVisible = true"><el-icon><Search /></el-icon><span>搜索对象或执行命令</span><kbd>Ctrl K</kbd></button>
            <div class="header-tools">
                <button title="左侧面板" :class="{active:leftVisible}" @click="workspace.toggleLeft"><el-icon><Tickets /></el-icon></button>
                <button title="分析面板" :class="{active:bottomVisible}" @click="workspace.toggleBottom"><el-icon><DataAnalysis /></el-icon></button>
                <button title="属性面板" :class="{active:rightVisible}" @click="workspace.toggleRight"><el-icon><Operation /></el-icon></button>
                <span class="tool-divider"></span>
                <button title="保存场景"><el-icon><Collection /></el-icon></button>
                <button class="export-button"><el-icon><Camera /></el-icon> 快照</button>
            </div>
        </header>

        <section class="workspace-grid" :class="{ 'no-left':!leftVisible, 'no-right':!rightVisible, 'no-bottom':!bottomVisible }">
            <ResourceExplorer v-if="leftVisible" class="left-dock" />
            <div class="viewport-shell">
                <div class="viewport-ruler top-ruler"></div><div class="viewport-ruler left-ruler"></div>
                <SceneCanvas />
                <div class="viewport-badge"><i></i> WEBGL / PERSPECTIVE</div>
            </div>
            <InspectorPanel v-if="rightVisible" class="right-dock" />
            <AnalysisDock v-if="bottomVisible" class="bottom-dock" />
        </section>

        <footer class="status-bar">
            <span><i class="online"></i> ENGINE READY</span><span>CRS {{ project?.coordinate_system || 'LOCAL' }}</span>
            <span>X — &nbsp; Y — &nbsp; Z —</span><span class="status-spacer"></span><span>FPS {{ performance.fps }}</span><span>CALLS {{ performance.calls }}</span><span>TRI {{ compactNumber(performance.triangles) }}</span>
        </footer>

        <el-dialog v-model="workspace.commandPaletteVisible" width="560px" :show-close="false" class="command-dialog">
            <el-input v-model="command" size="large" placeholder="输入命令，例如“启用剖切”" @keyup.enter="executeCommand"><template #prefix><el-icon><Search /></el-icon></template></el-input>
            <div class="command-list">
                <button v-for="item in filteredCommands" :key="item.name" @click="runCommand(item)"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.name }}</span><kbd>{{ item.shortcut }}</kbd></button>
            </div>
        </el-dialog>
    </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import SceneCanvas from '@/components/three/SceneCanvas.vue'
import ResourceExplorer from '@/workspace/components/ResourceExplorer.vue'
import InspectorPanel from '@/workspace/components/InspectorPanel.vue'
import AnalysisDock from '@/workspace/components/AnalysisDock.vue'
import { workspaceApi, type ProjectRecord } from '@/api/workspace'
import { useSceneStore, useWorkspaceStore } from '@/stores'

const route=useRoute(); const router=useRouter(); const workspace=useWorkspaceStore(); const sceneStore=useSceneStore()
const {leftVisible,rightVisible,bottomVisible,performance}=storeToRefs(workspace); const project=ref<ProjectRecord|null>(null); const command=ref('')
const projectName=computed(()=>project.value?.name || (route.params.projectId==='local'?'本地演示工作区':'三维地质项目'))
const commands=[
    {name:'启用三轴剖切',icon:'Crop',shortcut:'C',run:()=>sceneStore.activateTool('clip')},
    {name:'开始距离测量',icon:'ScaleToOriginal',shortcut:'M',run:()=>sceneStore.activateTool('measure')},
    {name:'创建空间标注',icon:'Location',shortcut:'A',run:()=>sceneStore.activateTool('annotation')},
    {name:'退出当前工具',icon:'Close',shortcut:'Esc',run:()=>sceneStore.activateTool(null)},
    {name:'打开性能面板',icon:'Odometer',shortcut:'',run:()=>workspace.openDock('performance')},
]
const filteredCommands=computed(()=>commands.filter(item=>item.name.includes(command.value.trim())))
function runCommand(item:typeof commands[number]){item.run();workspace.commandPaletteVisible=false;command.value=''}
function executeCommand(){if(filteredCommands.value[0])runCommand(filteredCommands.value[0])}
function compactNumber(value:number){return new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(value)}
function onGlobalKeydown(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        workspace.commandPaletteVisible = true
    }
    if (event.key === 'Escape') workspace.commandPaletteVisible = false
}
onMounted(async()=>{
    window.addEventListener('keydown', onGlobalKeydown)
    if(route.params.projectId!=='local'){
        try{
            project.value=await workspaceApi.getProject(String(route.params.projectId))
            sceneStore.setCoordinateOrigin({x:project.value.origin_x,y:project.value.origin_y,z:project.value.origin_z,verticalScale:project.value.vertical_scale})
        }catch{}
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
.geo-workspace{width:100vw;height:100vh;display:grid;grid-template-rows:52px minmax(0,1fr) 24px;background:#0b0f0c;color:#d8d9d2;--studio-border:#29302a;--studio-copper:#b57d3d}.workspace-header{display:flex;align-items:center;border-bottom:1px solid var(--studio-border);background:#101411;z-index:5}.brand-button{height:100%;width:150px;border:0;border-right:1px solid var(--studio-border);background:#151a16;color:#e2ddd0;display:flex;align-items:center;gap:10px;padding:0 14px;cursor:pointer;font:12px Bahnschrift;letter-spacing:.12em}.brand-glyph{width:24px;height:24px;display:grid;place-items:center;background:#a66f34;color:#16120d;font-weight:800}.project-identity{height:100%;min-width:220px;padding:9px 18px;display:flex;flex-direction:column;border-right:1px solid var(--studio-border)}.project-identity span{font:8px Bahnschrift;letter-spacing:.16em;color:#5f685f}.project-identity strong{font-size:12px;margin-top:2px}.command-trigger{width:min(390px,30vw);height:32px;margin-left:18px;padding:0 10px;border:1px solid #303831;background:#171c18;color:#687168;display:flex;align-items:center;gap:9px;cursor:pointer;text-align:left}.command-trigger span{flex:1;font-size:11px}.command-trigger kbd,.command-list kbd{font:9px Bahnschrift;color:#596159;border:1px solid #313832;padding:2px 5px}.header-tools{margin-left:auto;height:100%;display:flex;align-items:center;padding-right:8px}.header-tools button{height:32px;min-width:34px;margin:0 2px;border:1px solid transparent;background:transparent;color:#788178;cursor:pointer}.header-tools button:hover,.header-tools button.active{color:#d7d4ca;background:#1d241e;border-color:#333c34}.header-tools .export-button{padding:0 11px;display:flex;align-items:center;gap:6px;border-color:#604927;color:#d0a168}.tool-divider{height:22px;width:1px;background:#2b322c;margin:0 5px}.workspace-grid{min-height:0;display:grid;grid-template-columns:270px minmax(0,1fr) 300px;grid-template-rows:minmax(0,1fr) 205px;grid-template-areas:"left viewport right" "left bottom right"}.workspace-grid.no-left{grid-template-columns:minmax(0,1fr) 300px;grid-template-areas:"viewport right" "bottom right"}.workspace-grid.no-right{grid-template-columns:270px minmax(0,1fr);grid-template-areas:"left viewport" "left bottom"}.workspace-grid.no-left.no-right{grid-template-columns:minmax(0,1fr);grid-template-areas:"viewport" "bottom"}.workspace-grid.no-bottom{grid-template-rows:minmax(0,1fr);grid-template-areas:"left viewport right"}.workspace-grid.no-left.no-bottom{grid-template-areas:"viewport right"}.workspace-grid.no-right.no-bottom{grid-template-areas:"left viewport"}.workspace-grid.no-left.no-right.no-bottom{grid-template-areas:"viewport"}.left-dock{grid-area:left}.right-dock{grid-area:right}.bottom-dock{grid-area:bottom}.viewport-shell{grid-area:viewport;position:relative;min-width:0;min-height:0;overflow:hidden;background:#090d0b}.viewport-shell::after{content:"";position:absolute;inset:0;pointer-events:none;box-shadow:inset 0 0 80px rgba(0,0,0,.35)}.viewport-shell :deep(.tools-bar){top:14px!important;bottom:auto!important;right:16px;max-width:calc(100% - 32px);overflow-x:auto;overflow-y:hidden;border-radius:2px;background:rgba(16,21,17,.9);border-color:#3b443c;box-shadow:0 12px 32px rgba(0,0,0,.35)}.viewport-shell :deep(.tools-group){flex-shrink:0}.viewport-shell :deep(.tool-btn){border-radius:1px;background:#1a211b;border-color:#374038}.viewport-ruler{position:absolute;z-index:3;pointer-events:none;opacity:.45}.top-ruler{left:25px;right:0;top:0;height:7px;background:repeating-linear-gradient(90deg,#687068 0 1px,transparent 1px 25px)}.left-ruler{top:25px;bottom:0;left:0;width:7px;background:repeating-linear-gradient(#687068 0 1px,transparent 1px 25px)}.viewport-badge{position:absolute;z-index:4;left:15px;bottom:14px;font:8px Bahnschrift;letter-spacing:.14em;color:#778078;background:rgba(12,16,13,.78);padding:6px 8px}.viewport-badge i{display:inline-block;width:5px;height:5px;border-radius:50%;background:#6d9873;margin-right:6px}.status-bar{display:flex;align-items:center;gap:22px;padding:0 10px;background:#151a16;border-top:1px solid #303731;color:#697169;font:8px Bahnschrift;letter-spacing:.1em}.status-bar i{display:inline-block;width:5px;height:5px;border-radius:50%;margin-right:5px}.status-bar i.online{background:#6c9672}.status-spacer{flex:1}.command-list{display:flex;flex-direction:column;margin-top:10px}.command-list button{height:42px;border:0;border-bottom:1px solid #2a302b;background:transparent;color:#adb4ad;display:flex;align-items:center;gap:10px;padding:0 10px;text-align:left;cursor:pointer}.command-list button:hover{background:#1b211c;color:#e5e1d6}.command-list button span{flex:1}
@media(max-width:1000px){.workspace-grid{grid-template-columns:220px minmax(0,1fr);grid-template-areas:"left viewport" "left bottom"}.right-dock{display:none}.project-identity{min-width:160px}.command-trigger{display:none}}
</style>
