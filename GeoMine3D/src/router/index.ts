import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    {
        path: '/',
        redirect: '/projects',
    },
    {
        path: '/projects',
        name: 'ProjectCenter',
        component: () => import('@/views/projects/ProjectCenter.vue'),
        meta: { title: '项目中心' },
    },
    {
        path: '/workspace/:projectId',
        name: 'GeoWorkspace',
        component: () => import('@/views/workspace/GeoWorkspace.vue'),
        meta: { title: '三维地质工作台' },
    },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

export default router
