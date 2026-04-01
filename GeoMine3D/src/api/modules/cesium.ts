import request from '../request'
import type {
  BoundaryFeatureCollection,
  BoreholeWGS84Response,
  CesiumTiffLayerResponse,
  ProjectionMetadata,
} from '@/types'

// 获取矿区边界 GeoJSON 数据。
export function getMineAreaBoundary(): Promise<BoundaryFeatureCollection> {
  return request.get('/boundaries/mine-area')
}

// 获取工作面边界 GeoJSON 数据。
export function getWorkingFaceBoundaries(): Promise<BoundaryFeatureCollection> {
  return request.get('/boundaries/working-faces')
}

// 获取后端投影转换元信息。
export function getProjectionMetadata(): Promise<ProjectionMetadata> {
  return request.get('/system/projection')
}

// 获取已转换为 WGS84 的钻孔点位集合。
export function getBoreholeWGS84Points(): Promise<BoreholeWGS84Response> {
  return request.get('/boreholes/wgs84')
}

// 获取可用于 Cesium 加载的 TIFF 影像列表。
export function getTiffLayers(): Promise<CesiumTiffLayerResponse> {
  return request.get('/cesium/tiff-layers')
}
