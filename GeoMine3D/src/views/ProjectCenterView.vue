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
                <button class="primary-action ghost-action" type="button" @click="modelingDialogVisible = true">
                    <el-icon>
                        <Upload />
                    </el-icon> 上传钻孔建模
                </button>
                <button class="primary-action" type="button" @click="dialogVisible = true">
                    <el-icon>
                        <Plus />
                    </el-icon> 新建矿区项目
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
                <div class="card-topline"><span>LOCAL WORKSPACE</span><el-icon>
                        <Right />
                    </el-icon></div>
                <div class="local-orbit" aria-hidden="true"><i></i><i></i><i></i></div>
                <div class="card-content">
                    <h3>本地演示工作区</h3>
                    <p>仅用于拖放电脑中的 GLB；server 静态模型与钻孔请打开 DATABASE 项目。</p>
                </div>
                <div class="card-meta"><span>LOCAL</span><span>READY</span></div>
            </button>

            <button v-for="(project, index) in projects" :key="project.id" class="project-card" type="button"
                :style="{ '--delay': `${index * 70}ms` }" @click="openProject(project.id)">
                <div class="card-topline"><span>{{ project.coordinate_system }}</span>
                    <span class="card-state">
                        <span v-if="jobStateOf(project.id) === 'pending'" class="build-chip building">排队中</span>
                        <span v-else-if="jobStateOf(project.id) === 'running'" class="build-chip building">
                            <i class="pulse"></i>建模中
                        </span>
                        <span v-else-if="jobStateOf(project.id) === 'failed'" class="build-chip failed">建模失败</span>
                        <el-icon v-else>
                            <Right />
                        </el-icon>
                    </span>
                </div>
                <div class="strata-preview" aria-hidden="true">
                    <span v-for="n in 5" :key="n"></span>
                </div>
                <div class="card-content">
                    <h3>{{ project.name }}</h3>
                    <p v-if="activeJobOf(project.id)">{{ activeJobOf(project.id)!.message || '建模进行中…' }}</p>
                    <p v-else>{{ project.description || '尚未填写项目说明。' }}</p>
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
                <el-form-item label="项目说明"><el-input v-model="form.description" type="textarea"
                        :rows="3" /></el-form-item>
                <el-form-item label="坐标参考系"><el-input v-model="form.coordinate_system"
                        placeholder="例如 EPSG:2421" /></el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="creating" @click="createProject">创建并进入</el-button>
            </template>
        </el-dialog>

        <el-dialog v-model="modelingDialogVisible" title="上传钻孔数据建模" width="540px" class="project-dialog">
            <el-form label-position="top">
                <el-form-item label="项目名称"><el-input v-model="modelingForm.name"
                        placeholder="例如：西翼三盘区钻孔地质模型" /></el-form-item>
                <el-form-item label="项目说明"><el-input v-model="modelingForm.description" type="textarea"
                        :rows="2" placeholder="可选；留空将自动生成说明" /></el-form-item>
                <el-form-item label="分层汇总表(14层汇总长表)">
                    <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx"
                        :on-change="(file: any) => onModelingFile('strata', file)"
                        :on-remove="() => (modelingForm.strata = null)">
                        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                        <div class="el-upload__text">拖拽或<em>点击选择</em> .xlsx 文件</div>
                        <template #tip>
                            <div class="el-upload__tip">表头：钻孔名称 / 地层名称 / 深度 / 厚度（深度=层顶、厚度列=层底）</div>
                        </template>
                    </el-upload>
                </el-form-item>
                <el-form-item label="钻孔位置表">
                    <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx"
                        :on-change="(file: any) => onModelingFile('location', file)"
                        :on-remove="() => (modelingForm.location = null)">
                        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                        <div class="el-upload__text">拖拽或<em>点击选择</em> .xlsx 文件</div>
                        <template #tip>
                            <div class="el-upload__tip">表头：name(钻孔名称) / x / y / z（Gauss-Kruger 坐标与孔口高程）</div>
                        </template>
                    </el-upload>
                </el-form-item>
            </el-form>
            <p class="modeling-note">上传后将创建独立项目，并在后台自动完成界面插值、三维建模与交付包生成（约 1 分钟）。</p>
            <template #footer>
                <el-button @click="modelingDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="creating" @click="createModelingProject">创建并开始建模</el-button>
            </template>
        </el-dialog>
    </main>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { workspaceApi, type ModelingJobRecord, type ProjectRecord } from '@/api/workspace'

const router = useRouter()
const projects = ref<ProjectRecord[]>([])
const loading = ref(true)
const online = ref(false)
const dialogVisible = ref(false)
const creating = ref(false)
const form = reactive({ name: '', description: '', coordinate_system: 'EPSG:2421' })

const modelingDialogVisible = ref(false)
const modelingForm = reactive<{ name: string; description: string; strata: File | null; location: File | null }>({
    name: '',
    description: '',
    strata: null,
    location: null,
})

// projectId → 该项目最近一次建模任务;轮询期间实时刷新,驱动卡片状态条。
const jobsByProject = ref<Record<string, ModelingJobRecord>>({})
let pollTimer: number | null = null

function openProject(projectId: string) {
    const job = jobsByProject.value[projectId]
    if (job && (job.status === 'pending' || job.status === 'running')) {
        ElMessage.info(`「${projectNameOf(projectId)}」正在建模中（${job.message || job.stage || '进行中'}），完成后即可进入`)
        return
    }
    router.push(`/workspace/${projectId}`)
}

function formatDate(value: string) {
    return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', year: 'numeric' }).format(new Date(value))
}

function projectNameOf(projectId: string) {
    return projects.value.find(item => item.id === projectId)?.name || '新项目'
}

function jobStateOf(projectId: string) {
    return jobsByProject.value[projectId]?.status || 'none'
}

function activeJobOf(projectId: string) {
    const job = jobsByProject.value[projectId]
    if (!job || (job.status !== 'pending' && job.status !== 'running')) return null
    return job
}

function onModelingFile(kind: 'strata' | 'location', uploadFile: any) {
    if (!uploadFile?.raw) return
    if (!String(uploadFile.name || '').toLowerCase().endsWith('.xlsx')) {
        ElMessage.warning('只支持 .xlsx 文件')
        return
    }
    modelingForm[kind] = uploadFile.raw as File
}

async function loadProjects() {
    loading.value = true
    try {
        const response = await workspaceApi.listProjects()
        projects.value = response.data
        online.value = true
        await loadLatestJobs()
    } catch {
        online.value = false
    } finally {
        loading.value = false
    }
}

async function loadLatestJobs() {
    // 每个项目取最近一次建模任务,让“建模中/失败”状态在刷新页面后依然可见。
    const results = await Promise.allSettled(
        projects.value.map(project => workspaceApi.listModelingJobs(project.id)),
    )
    results.forEach((result, index) => {
        if (result.status === 'fulfilled' && result.value.length) {
            jobsByProject.value[projects.value[index].id] = result.value[0]
        }
    })
}

function ensurePolling() {
    if (pollTimer !== null) return
    pollTimer = window.setInterval(pollActiveJobs, 2500)
    void pollActiveJobs()
}

async function pollActiveJobs() {
    const active = Object.values(jobsByProject.value).filter(
        job => job.status === 'pending' || job.status === 'running',
    )
    if (!active.length) {
        stopPolling()
        return
    }
    for (const job of active) {
        try {
            const fresh = await workspaceApi.getModelingJob(job.id)
            jobsByProject.value[fresh.project_id] = fresh
            if (fresh.status === 'completed') {
                ElMessage.success(`「${projectNameOf(fresh.project_id)}」建模完成，可进入工作台查看`)
                await loadProjects()
            } else if (fresh.status === 'failed') {
                ElMessage.error(`「${projectNameOf(fresh.project_id)}」建模失败：${(fresh.error_message || '未知错误').slice(0, 160)}`)
            }
        } catch {
            // 服务瞬时不可达时静默,下一轮重试
        }
    }
}

function stopPolling() {
    if (pollTimer !== null) {
        clearInterval(pollTimer)
        pollTimer = null
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

async function createModelingProject() {
    if (!modelingForm.name.trim()) return ElMessage.warning('请输入项目名称')
    if (!modelingForm.strata) return ElMessage.warning('请选择分层汇总表(.xlsx)')
    if (!modelingForm.location) return ElMessage.warning('请选择钻孔位置表(.xlsx)')
    creating.value = true
    try {
        const payload = new FormData()
        payload.append('name', modelingForm.name.trim())
        payload.append('description', modelingForm.description)
        payload.append('strata_file', modelingForm.strata)
        payload.append('location_file', modelingForm.location)
        const job = await workspaceApi.createModelingJob(payload)
        modelingDialogVisible.value = false
        modelingForm.name = ''
        modelingForm.description = ''
        modelingForm.strata = null
        modelingForm.location = null
        jobsByProject.value[job.project_id] = job
        ElMessage.success('项目已创建，建模任务已启动')
        ensurePolling()
        await loadProjects()
    } catch (error: any) {
        const message = error?.response?.data?.message
        ElMessage.error(message || '上传失败，请检查数据服务与文件格式')
    } finally {
        creating.value = false
    }
}

onMounted(loadProjects)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.project-center {
    min-height: 100%;
    overflow-y: auto;
    position: relative;
    padding: 34px 5vw 24px;
    background: #0b0e0d;
    color: #e8e4d8;
}

.terrain-lines {
    position: fixed;
    inset: 0;
    pointer-events: none;
    opacity: .18;
    background: radial-gradient(circle at 72% 12%, rgba(184, 135, 64, .22), transparent 28%), repeating-radial-gradient(ellipse at 80% 12%, transparent 0 34px, rgba(199, 172, 115, .18) 36px 37px, transparent 39px 53px);
    mask-image: linear-gradient(to bottom, #000, transparent 65%);
}

.project-header {
    position: relative;
    z-index: 1;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 28px;
    border-bottom: 1px solid #353a35;
}

.brand-lockup,
.header-actions,
.card-topline,
.card-meta {
    display: flex;
    align-items: center;
}

.brand-lockup {
    gap: 15px;
}

.brand-mark {
    width: 42px;
    height: 42px;
    display: grid;
    gap: 4px;
    transform: skewY(-12deg);
}

.brand-mark span {
    display: block;
    background: #ba8845;
}

.brand-mark span:nth-child(2) {
    width: 75%;
}

.brand-mark span:nth-child(3) {
    width: 48%;
}

.eyebrow,
.section-index,
.card-topline,
.card-meta,
.service-state {
    font: 600 10px/1.2 Bahnschrift, sans-serif;
    letter-spacing: .18em;
    text-transform: uppercase;
}

.eyebrow {
    color: #7e877f;
    margin-bottom: 4px;
}

.brand-lockup h1 {
    font: 500 22px/1 Bahnschrift, sans-serif;
    letter-spacing: .04em;
}

.brand-lockup em {
    color: #ba8845;
    font-style: normal;
}

.header-actions {
    gap: 18px;
}

.service-state {
    color: #93ad97;
}

.service-state i {
    display: inline-block;
    width: 7px;
    height: 7px;
    margin-right: 8px;
    border-radius: 50%;
    background: #6f9b75;
    box-shadow: 0 0 12px #6f9b75;
}

.service-state.offline {
    color: #9a8d78;
}

.service-state.offline i {
    background: #8b7356;
    box-shadow: none;
}

.primary-action {
    height: 40px;
    padding: 0 17px;
    border: 1px solid #ba8845;
    color: #f2e5cf;
    background: #8d6030;
    cursor: pointer;
    display: flex;
    gap: 8px;
    align-items: center;
    font-weight: 600;
}

.ghost-action {
    background: transparent;
    border-color: #4a4f49;
    color: #b9b4a4;
    font-weight: 500;
}

.ghost-action:hover {
    border-color: #ba8845;
    color: #f2e5cf;
}

.card-state {
    display: inline-flex;
}

.build-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 9px;
    border-radius: 999px;
    font: 600 10px/1.2 Bahnschrift, 'Noto Sans SC', sans-serif;
    letter-spacing: .12em;
}

.build-chip.building {
    color: #f2e5cf;
    background: rgba(186, 136, 69, .28);
    border: 1px solid #ba8845;
}

.build-chip.failed {
    color: #ffb9a8;
    background: rgba(178, 60, 40, .22);
    border: 1px solid #b23c28;
}

.build-chip .pulse {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #e8b25f;
    animation: chip-pulse 1.1s ease-in-out infinite;
}

@keyframes chip-pulse {

    0%,
    100% {
        opacity: .25;
        transform: scale(.8);
    }

    50% {
        opacity: 1;
        transform: scale(1.15);
    }
}

.modeling-note {
    margin: 4px 0 0;
    font-size: 12px;
    line-height: 1.6;
    color: #8f968e;
}

.hero-copy {
    position: relative;
    z-index: 1;
    padding: 62px 0 44px;
    display: grid;
    grid-template-columns: 150px minmax(420px, 680px) minmax(260px, 420px);
    align-items: end;
    gap: 30px;
}

.section-index {
    color: #ba8845;
    align-self: start;
    padding-top: 10px;
}

.hero-copy h2 {
    font: 400 clamp(42px, 5vw, 74px)/.96 Georgia, 'Noto Serif SC', serif;
    letter-spacing: -.04em;
}

.hero-copy h2 span {
    color: #999b91;
}

.hero-description {
    color: #979e96;
    line-height: 1.8;
    max-width: 390px;
    padding-bottom: 4px;
}

.project-grid {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
    gap: 14px;
    min-height: 280px;
}

.project-card {
    min-height: 340px;
    padding: 20px;
    border: 1px solid #333833;
    background: linear-gradient(145deg, #151917, #101311);
    color: inherit;
    text-align: left;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: .25s ease;
    animation: card-in .45s ease both;
    animation-delay: var(--delay, 0ms);
}

.project-card:hover {
    transform: translateY(-5px);
    border-color: #8e693d;
    box-shadow: 0 24px 50px rgba(0, 0, 0, .3);
}

.local-card {
    background: #b17c3e;
    color: #17130e;
    border-color: #ce9c5e;
}

.card-topline {
    justify-content: space-between;
    opacity: .72;
}

.strata-preview {
    height: 130px;
    margin: 28px -20px 24px;
    transform: skewY(-7deg);
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.strata-preview span {
    flex: 1;
    background: #343b35;
}

.strata-preview span:nth-child(2) {
    margin-left: 8%;
    background: #6e664e;
}

.strata-preview span:nth-child(3) {
    margin-left: 3%;
    background: #48584d;
}

.strata-preview span:nth-child(4) {
    margin-left: 12%;
    background: #755b3d;
}

.strata-preview span:nth-child(5) {
    background: #242b27;
}

.local-orbit {
    position: relative;
    height: 130px;
    margin: 18px 0;
}

.local-orbit i {
    position: absolute;
    border: 1px solid rgba(20, 16, 11, .45);
    border-radius: 50%;
    inset: 15px 38px;
    transform: rotate(-15deg);
}

.local-orbit i:nth-child(2) {
    inset: 30px 60px;
    transform: rotate(22deg);
}

.local-orbit i:nth-child(3) {
    inset: 49px 86px;
    background: #1c211e;
    border: 0;
}

.card-content {
    margin-top: auto;
}

.card-content h3 {
    font: 500 24px/1.2 Bahnschrift, 'Noto Sans SC', sans-serif;
    margin-bottom: 10px;
}

.card-content p {
    font-size: 13px;
    line-height: 1.65;
    opacity: .62;
    min-height: 42px;
}

.card-meta {
    justify-content: space-between;
    margin-top: 22px;
    padding-top: 14px;
    border-top: 1px solid currentColor;
    opacity: .42;
}

.project-footer {
    position: relative;
    z-index: 1;
    display: flex;
    justify-content: space-between;
    margin-top: 36px;
    padding-top: 18px;
    border-top: 1px solid #353a35;
    color: #666e68;
    font: 10px Bahnschrift, sans-serif;
    letter-spacing: .16em;
}

@keyframes card-in {
    from {
        opacity: 0;
        transform: translateY(14px);
    }
}

@media (max-width:900px) {
    .project-header {
        align-items: flex-start
    }

    .service-state {
        display: none
    }

    .hero-copy {
        grid-template-columns: 1fr;
        padding-top: 42px
    }

    .section-index {
        display: none
    }

    .hero-copy h2 {
        font-size: 48px
    }

    .project-center {
        padding-inline: 20px
    }
}
</style>
