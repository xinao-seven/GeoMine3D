import axios from 'axios'
import type { BoreholeDetail } from '@/types'

export interface ProjectRecord {
    id: string
    name: string
    description: string | null
    coordinate_system: string
    origin_x: number
    origin_y: number
    origin_z: number
    vertical_scale: number
    created_at: string
    updated_at: string
}

export interface ModelAssetRecord {
    id: string
    project_id: string
    name: string
    model_type: 'stratum' | 'working_face' | 'roadway' | 'other'
    status: string
    current_version_id: string | null
    metadata_json: Record<string, any>
}

export interface BoreholeSegmentRecord {
    id: string
    layer_name: string
    lithology: string | null
    top_depth: number
    bottom_depth: number
    thickness: number
    color: string
    sequence: number
}

export interface BoreholeRecord {
    id: string
    project_id: string
    code: string
    name: string
    x: number
    y: number
    z: number
    total_depth: number
    status: string
    metadata_json: Record<string, any>
    segments: BoreholeSegmentRecord[]
}

export interface ModelingJobRecord {
    id: string
    project_id: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    stage: string | null
    message: string | null
    params_json: Record<string, any>
    output_dir: string | null
    result_json: Record<string, any> | null
    error_message: string | null
    created_at: string
    updated_at: string
}

export interface SceneRecord {
    id: string
    project_id: string
    name: string
    camera_json: Record<string, any>
    layers_json: Array<Record<string, any>>
    clipping_json: Record<string, any>
    explode_json: Record<string, any>
    render_settings_json: Record<string, any>
    created_at: string
    updated_at: string
}

export interface ThicknessStat {
    layer_name: string
    count: number
    avg_thickness: number
    min_thickness: number
    max_thickness: number
    avg_top_depth: number
}

export interface AnalysisOverview {
    borehole_count: number
    segment_count: number
    strata_layer_count: number
    model_count: number
    workingface_count: number
    total_drilling_depth: number
    avg_borehole_depth: number
    max_borehole_depth: number
    thickness_distribution: ThicknessStat[]
    depth_distribution: {
        count: number
        min: number
        max: number
        avg: number
        bins: Array<{ start: number; end: number; count: number }>
    }
    layer_frequency: Array<{ layer_name: string; borehole_count: number; avg_top_depth: number }>
    workingface_status: Array<{ status: string; count: number; avg_length: number | null; avg_width: number | null }>
}

interface DataResponse<T> { data: T }
interface PageResponse<T> { data: T[]; meta: { page: number; page_size: number; total: number } }

const workspaceClient = axios.create({
    baseURL: '/api/v1',
    timeout: 20000,
})

export const workspaceApi = {
    async listProjects() {
        return (await workspaceClient.get<PageResponse<ProjectRecord>>('/projects')).data
    },
    async createProject(payload: Pick<ProjectRecord, 'name' | 'description' | 'coordinate_system'>) {
        return (await workspaceClient.post<DataResponse<ProjectRecord>>('/projects', payload)).data.data
    },
    async getProject(projectId: string) {
        return (await workspaceClient.get<DataResponse<ProjectRecord>>(`/projects/${projectId}`)).data.data
    },
    async listModels(projectId: string) {
        return (await workspaceClient.get<DataResponse<ModelAssetRecord[]>>(`/projects/${projectId}/models`)).data.data
    },
    async listBoreholes(projectId: string) {
        return (await workspaceClient.get<DataResponse<BoreholeRecord[]>>(`/projects/${projectId}/boreholes`)).data.data
    },
    async getBorehole(boreholeId: string) {
        return (await workspaceClient.get<DataResponse<BoreholeRecord>>(`/boreholes/${boreholeId}`)).data.data
    },
    modelFileUrl(modelId: string) {
        return `/api/v1/models/${modelId}/file`
    },
    async createModelingJob(form: FormData) {
        return (await workspaceClient.post<DataResponse<ModelingJobRecord>>('/modeling-jobs', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120000,
        })).data.data
    },
    async getModelingJob(jobId: string) {
        return (await workspaceClient.get<DataResponse<ModelingJobRecord>>(`/modeling-jobs/${jobId}`)).data.data
    },
    async listModelingJobs(projectId: string) {
        return (await workspaceClient.get<DataResponse<ModelingJobRecord[]>>(`/projects/${projectId}/modeling-jobs`)).data.data
    },
    async listScenes(projectId: string) {
        return (await workspaceClient.get<DataResponse<SceneRecord[]>>(`/projects/${projectId}/scenes`)).data.data
    },
    async createScene(projectId: string, payload: {
        name: string
        camera_json: Record<string, any>
        layers_json: Array<Record<string, any>>
        clipping_json: Record<string, any>
        explode_json: Record<string, any>
        render_settings_json: Record<string, any>
    }) {
        return (await workspaceClient.post<DataResponse<SceneRecord>>(`/projects/${projectId}/scenes`, payload)).data.data
    },
    async updateScene(sceneId: string, payload: Record<string, any>) {
        return (await workspaceClient.put<DataResponse<SceneRecord>>(`/scenes/${sceneId}`, payload)).data.data
    },
    async deleteScene(sceneId: string) {
        await workspaceClient.delete(`/scenes/${sceneId}`)
    },
    async getAnalysisOverview(projectId: string) {
        return (await workspaceClient.get<DataResponse<AnalysisOverview>>(`/projects/${projectId}/analysis/overview`)).data.data
    },
}

export function toBoreholeDetail(item: BoreholeRecord): BoreholeDetail {
    return {
        id: item.id,
        name: item.name || item.code,
        totalDepth: item.total_depth,
        layerCount: item.segments.length,
        location: { x: item.x, y: item.y, z: item.z },
        layers: item.segments.map(segment => ({
            layerName: segment.layer_name,
            topDepth: segment.top_depth,
            bottomDepth: segment.bottom_depth,
            thickness: segment.thickness,
            color: segment.color,
        })),
    }
}
