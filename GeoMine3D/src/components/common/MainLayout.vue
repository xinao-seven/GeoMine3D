<template>
  <div class="layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="logo">
        <img src="/favicon.svg" alt="logo" class="logo-icon" />
        <span class="logo-text">GeoMine3D</span>
      </div>
      <el-menu
        :default-active="activeRoute"
        class="side-menu"
        :collapse="false"
        background-color="transparent"
        text-color="#8ab4d4"
        active-text-color="#00c8ff"
        @select="handleMenuSelect"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>

      <!-- 底部统计 -->
      <div class="sidebar-stats" v-if="summary">
        <div class="stat-item">
          <span class="stat-value">{{ summary.modelCount }}</span>
          <span class="stat-label">模型</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ summary.boreholeCount }}</span>
          <span class="stat-label">钻孔</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ summary.workingFaceCount }}</span>
          <span class="stat-label">工作面</span>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="main-area">
      <!-- 顶部 Header -->
      <header class="header">
        <div class="header-left">
          <span class="page-title">{{ currentPageTitle }}</span>
        </div>
        <div class="header-right">
          <el-tag type="success" size="small">系统运行中</el-tag>
          <span class="time">{{ currentTime }}</span>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="content">
        <RouterView v-slot="{ Component, route }">
          <KeepAlive include="DashboardView">
            <component :is="Component" :key="route.name" />
          </KeepAlive>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const { summary } = projectStore

const currentTime = ref('')
let timer: ReturnType<typeof setInterval>

const menuItems = [
  { path: '/dashboard', title: '三维分析', icon: 'DataBoard' },
  { path: '/cesium-view', title: 'Cesium场景', icon: 'Location' },
  { path: '/model-management', title: '模型管理', icon: 'Box' },
  { path: '/borehole-management', title: '钻孔管理', icon: 'SetUp' },
  { path: '/workingface-management', title: '工作面管理', icon: 'Grid' },
  { path: '/analysis', title: '统计分析', icon: 'TrendCharts' },
]

const activeRoute = computed(() => route.path)
const currentPageTitle = computed(
  () => menuItems.find(m => m.path === route.path)?.title ?? 'GeoMine3D'
)

function handleMenuSelect(path: string) {
  router.push(path)
}

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN')
}

onMounted(() => {
  projectStore.fetchSummary()
  updateTime()
  timer = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  clearInterval(timer)
})
</script>

<style scoped>
.layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: var(--color-bg-secondary);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--color-border);
}

.logo-icon {
  width: 28px;
  height: 28px;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-accent);
  letter-spacing: 1px;
}

.side-menu {
  flex: 1;
  border-right: none;
  margin-top: 8px;
}

:deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 6px;
  transition: all 0.2s;
}

:deep(.el-menu-item.is-active) {
  background: rgba(0, 200, 255, 0.12) !important;
  border-left: 3px solid var(--color-accent);
}

.sidebar-stats {
  display: flex;
  justify-content: space-around;
  padding: 16px 8px;
  border-top: 1px solid var(--color-border);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-accent);
}

.stat-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  height: var(--header-height);
  flex-shrink: 0;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.time {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.content {
  flex: 1;
  overflow: hidden;
}
</style>
