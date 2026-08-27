import axios from 'axios'

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
    model_type: 'stratum' | 'working_face' | 'other'
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
    modelFileUrl(modelId: string) {
        return `/api/v1/models/${modelId}/file`
    },
}
