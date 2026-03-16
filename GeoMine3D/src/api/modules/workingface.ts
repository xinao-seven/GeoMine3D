import request from '../request'
import type { WorkingFaceItem, WorkingFaceDetail, WorkingFaceListQuery } from '@/types'

export function getWorkingFaceList(params?: WorkingFaceListQuery): Promise<WorkingFaceItem[]> {
  return request.get('/workingfaces', { params })
}

export function getWorkingFaceDetail(id: string): Promise<WorkingFaceDetail> {
  return request.get(`/workingfaces/${id}`)
}
