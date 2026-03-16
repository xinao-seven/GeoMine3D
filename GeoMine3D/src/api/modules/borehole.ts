import request from '../request'
import type { BoreholeItem, BoreholeDetail, BoreholeListQuery } from '@/types'

export function getBoreholeList(params?: BoreholeListQuery): Promise<BoreholeItem[]> {
  return request.get('/boreholes', { params })
}

export function getBoreholeDetail(id: string): Promise<BoreholeDetail> {
  return request.get(`/boreholes/${id}`)
}

export function searchBoreholes(keyword: string): Promise<BoreholeItem[]> {
  return request.get('/boreholes/search', { params: { keyword } })
}
