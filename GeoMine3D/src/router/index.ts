import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/',
    component: () => import('@/components/common/MainLayout.vue'),
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '三维分析', icon: 'DataBoard' },
      },
      {
        path: 'cesium-view',
        name: 'CesiumView',
        component: () => import('@/views/cesium/index.vue'),
        meta: { title: 'Cesium场景', icon: 'Location' },
      },
      {
        path: 'model-management',
        name: 'ModelManagement',
        component: () => import('@/views/model-management/index.vue'),
        meta: { title: '模型管理', icon: 'Box' },
      },
      {
        path: 'borehole-management',
        name: 'BoreholeManagement',
        component: () => import('@/views/borehole-management/index.vue'),
        meta: { title: '钻孔管理', icon: 'SetUp' },
      },
      {
        path: 'workingface-management',
        name: 'WorkingFaceManagement',
        component: () => import('@/views/workingface-management/index.vue'),
        meta: { title: '工作面管理', icon: 'Grid' },
      },
      {
        path: 'analysis',
        name: 'Analysis',
        component: () => import('@/views/analysis/index.vue'),
        meta: { title: '统计分析', icon: 'TrendCharts' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
