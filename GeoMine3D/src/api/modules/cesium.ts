import request from '../request'
import type { BoundaryFeatureCollection, BoreholeWGS84Response, ProjectionMetadata } from '@/types'

export function getMineAreaBoundary(): Promise<BoundaryFeatureCollection> {
  return request.get('/boundaries/mine-area')
}

export function getWorkingFaceBoundaries(): Promise<BoundaryFeatureCollection> {
  return request.get('/boundaries/working-faces')
}

export function getProjectionMetadata(): Promise<ProjectionMetadata> {
  return request.get('/system/projection')
}

export function getBoreholeWGS84Points(): Promise<BoreholeWGS84Response> {
  return request.get('/boreholes/wgs84')
}
