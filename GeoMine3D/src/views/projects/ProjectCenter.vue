<template>
    <main class="project-center">
        <div class="terrain-lines" aria-hidden="true"></div>
        <header class="project-header">
            <div class="brand-lockup">
                <div class="brand-mark"><span></span><span></span><span></span></div>
                <div>
                    <p class="eyebrow">GEOLOGICAL MODELING SYSTEM</p>
                    <h1>GeoMine <em>Studio</em></h1>
                </div>
            </div>
            <div class="header-actions">
                <div class="service-state" :class="{ offline: !online }">
                    <i></i>{{ online ? '数据服务已连接' : '本地工作模式' }}
                </div>
                <button class="primary-action" type="button" @click="dialogVisible = true">
                    <el-icon><Plus /></el-icon> 新建矿区项目
                </button>
            </div>
        </header>

        <section class="hero-copy">
            <p class="section-index">01 / PROJECTS</p>
            <h2>从矿区数据<br><span>进入地下空间。</span></h2>
            <p class="hero-description">组织地层模型、钻孔与工作面，在统一的三维工作台中完成查看、剖切、测量和分析。</p>
        </section>

        <section class="project-grid" v-loading="loading">
            <button class="project-card local-card" type="button" @click="openProject('local')">
                <div class="card-topline"><span>LOCAL WORKSPACE</span><el-icon><Right /></el-icon></div>
                <div class="local-orbit" aria-hidden="true"><i></i><i></i><i></i></div>
                <div class="card-content">
                    <h3>本地演示工作区</h3>
                    <p>仅用于拖放电脑中的 GLB；server 静态模型与钻孔请打开 DATABASE 项目。</p>
                </div>
                <div class="card-meta"><span>LOCAL</span><span>READY</span></div>
            </button>

            <button v-for="(project, index) in projects" :key="project.id" class="project-card"
                type="button" :style="{ '--delay': `${index * 70}ms` }" @click="openProject(project.id)">
                <div class="card-topline"><span>{{ project.coordinate_system }}</span><el-icon><Right /></el-icon></div>
                <div class="strata-preview" aria-hidden="true">
                    <span v-for="n in 5" :key="n"></span>
                </div>
                <div class="card-content">
                    <h3>{{ project.name }}</h3>
                    <p>{{ project.description || '尚未填写项目说明。' }}</p>
                </div>
                <div class="card-meta"><span>{{ formatDate(project.updated_at) }}</span><span>DATABASE</span></div>
            </button>
        </section>

        <footer class="project-footer">
            <span>GEOMINE / WORKSPACE EDITION</span>
            <span>{{ projects.length + 1 }} 个可用工作区</span>
        </footer>

        <el-dialog v-model="dialogVisible" title="建立矿区项目" width="480px" class="project-dialog">
            <el-form label-position="top">
                <el-form-item label="项目名称"><el-input v-model="form.name" placeholder="例如：北翼采区三维地质模型" /></el-form-item>
                <el-form-item label="项目说明"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
                <el-form-item label="坐标参考系"><el-input v-model="form.coordinate_system" placeholder="例如 EPSG:2421" /></el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="creating" @click="createProject">创建并进入</el-button>
            </template>
        </el-dialog>
    </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { workspaceApi, type ProjectRecord } from '@/api/workspace'

const router = useRouter()
const projects = ref<ProjectRecord[]>([])
const loading = ref(true)
const online = ref(false)
const dialogVisible = ref(false)
const creating = ref(false)
const form = reactive({ name: '', description: '', coordinate_system: 'EPSG:2421' })

function openProject(projectId: string) {
    router.push(`/workspace/${projectId}`)
}

function formatDate(value: string) {
    return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', year: 'numeric' }).format(new Date(value))
}

async function loadProjects() {
    loading.value = true
    try {
        const response = await workspaceApi.listProjects()
        projects.value = response.data
        online.value = true
    } catch {
        online.value = false
    } finally {
        loading.value = false
    }
}

async function createProject() {
    if (!form.name.trim()) return ElMessage.warning('请输入项目名称')
    creating.value = true
    try {
        const project = await workspaceApi.createProject(form)
        dialogVisible.value = false
        openProject(project.id)
    } catch {
        ElMessage.error('数据服务不可用，请启动 FastAPI 与 MySQL 后重试')
    } finally {
        creating.value = false
    }
}

onMounted(loadProjects)
</script>

<style scoped>
.project-center { min-height: 100%; overflow-y: auto; position: relative; padding: 34px 5vw 24px; background: #0b0e0d; color: #e8e4d8; }
.terrain-lines { position: fixed; inset: 0; pointer-events: none; opacity: .18; background: radial-gradient(circle at 72% 12%, rgba(184, 135, 64, .22), transparent 28%), repeating-radial-gradient(ellipse at 80% 12%, transparent 0 34px, rgba(199, 172, 115, .18) 36px 37px, transparent 39px 53px); mask-image: linear-gradient(to bottom, #000, transparent 65%); }
.project-header { position: relative; z-index: 1; display: flex; justify-content: space-between; align-items: center; padding-bottom: 28px; border-bottom: 1px solid #353a35; }
.brand-lockup,.header-actions,.card-topline,.card-meta { display: flex; align-items: center; }
.brand-lockup { gap: 15px; }.brand-mark { width: 42px; height: 42px; display: grid; gap: 4px; transform: skewY(-12deg); }.brand-mark span { display: block; background: #ba8845; }.brand-mark span:nth-child(2){ width:75%; }.brand-mark span:nth-child(3){ width:48%; }
.eyebrow,.section-index,.card-topline,.card-meta,.service-state { font: 600 10px/1.2 Bahnschrift, sans-serif; letter-spacing: .18em; text-transform: uppercase; }
.eyebrow { color: #7e877f; margin-bottom: 4px; }.brand-lockup h1 { font: 500 22px/1 Bahnschrift, sans-serif; letter-spacing: .04em; }.brand-lockup em { color: #ba8845; font-style: normal; }
.header-actions { gap: 18px; }.service-state { color: #93ad97; }.service-state i { display:inline-block; width:7px; height:7px; margin-right:8px; border-radius:50%; background:#6f9b75; box-shadow:0 0 12px #6f9b75; }.service-state.offline { color:#9a8d78; }.service-state.offline i { background:#8b7356; box-shadow:none; }
.primary-action { height: 40px; padding: 0 17px; border: 1px solid #ba8845; color:#f2e5cf; background:#8d6030; cursor:pointer; display:flex; gap:8px; align-items:center; font-weight:600; }
.hero-copy { position:relative; z-index:1; padding: 62px 0 44px; display:grid; grid-template-columns: 150px minmax(420px, 680px) minmax(260px, 420px); align-items:end; gap:30px; }.section-index { color:#ba8845; align-self:start; padding-top:10px; }.hero-copy h2 { font: 400 clamp(42px, 5vw, 74px)/.96 Georgia, 'Noto Serif SC', serif; letter-spacing:-.04em; }.hero-copy h2 span { color:#999b91; }.hero-description { color:#979e96; line-height:1.8; max-width:390px; padding-bottom:4px; }
.project-grid { position:relative; z-index:1; display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:14px; min-height:280px; }.project-card { min-height:340px; padding:20px; border:1px solid #333833; background:linear-gradient(145deg,#151917,#101311); color:inherit; text-align:left; cursor:pointer; display:flex; flex-direction:column; overflow:hidden; transition:.25s ease; animation:card-in .45s ease both; animation-delay:var(--delay,0ms); }.project-card:hover { transform:translateY(-5px); border-color:#8e693d; box-shadow:0 24px 50px rgba(0,0,0,.3); }.local-card { background:#b17c3e; color:#17130e; border-color:#ce9c5e; }.card-topline { justify-content:space-between; opacity:.72; }.strata-preview { height:130px; margin:28px -20px 24px; transform:skewY(-7deg); display:flex; flex-direction:column; gap:5px; }.strata-preview span { flex:1; background:#343b35; }.strata-preview span:nth-child(2){ margin-left:8%; background:#6e664e; }.strata-preview span:nth-child(3){ margin-left:3%; background:#48584d; }.strata-preview span:nth-child(4){ margin-left:12%; background:#755b3d; }.strata-preview span:nth-child(5){ background:#242b27; }
.local-orbit { position:relative; height:130px; margin:18px 0; }.local-orbit i { position:absolute; border:1px solid rgba(20,16,11,.45); border-radius:50%; inset:15px 38px; transform:rotate(-15deg); }.local-orbit i:nth-child(2){ inset:30px 60px; transform:rotate(22deg); }.local-orbit i:nth-child(3){ inset:49px 86px; background:#1c211e; border:0; }
.card-content { margin-top:auto; }.card-content h3 { font:500 24px/1.2 Bahnschrift,'Noto Sans SC',sans-serif; margin-bottom:10px; }.card-content p { font-size:13px; line-height:1.65; opacity:.62; min-height:42px; }.card-meta { justify-content:space-between; margin-top:22px; padding-top:14px; border-top:1px solid currentColor; opacity:.42; }
.project-footer { position:relative; z-index:1; display:flex; justify-content:space-between; margin-top:36px; padding-top:18px; border-top:1px solid #353a35; color:#666e68; font:10px Bahnschrift,sans-serif; letter-spacing:.16em; }
@keyframes card-in { from { opacity:0; transform:translateY(14px); } }
@media (max-width:900px){ .project-header{align-items:flex-start}.service-state{display:none}.hero-copy{grid-template-columns:1fr;padding-top:42px}.section-index{display:none}.hero-copy h2{font-size:48px}.project-center{padding-inline:20px} }
</style>
