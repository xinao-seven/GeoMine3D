export type WorkingFaceStatus = '开采中' | '已完成' | '规划中'

export interface WorkingFaceItem {
  id: string
  code: string
  name: string
  status: WorkingFaceStatus
  description: string
  modelId: string | null
  length?: number
  width?: number
  coalSeam?: string
}

export type WorkingFaceDetail = WorkingFaceItem

export interface WorkingFaceListQuery {
  keyword?: string
  status?: WorkingFaceStatus
}
