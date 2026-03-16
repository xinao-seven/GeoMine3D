import request from '../request'
import type { ModelItem, ModelDetail, ModelResource } from '@/types'

export function getModelList(params?: { type?: string; keyword?: string }): Promise<ModelItem[]> {
  return request.get('/models', { params })
}

export function getModelDetail(id: string): Promise<ModelDetail> {
  return request.get(`/models/${id}`)
}

export function getModelResourceUrl(id: string): Promise<ModelResource> {
  return request.get(`/models/${id}/resource`)
}
