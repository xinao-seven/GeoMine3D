export interface BoreholeLayer {
  layerName: string
  topDepth: number
  bottomDepth: number
  thickness: number
}

export interface BoreholeLocation {
  x: number  // Three.js X（东向偏移，米）
  y: number  // Three.js Y（高程偏移，米）
  z: number  // Three.js Z（北向偏移，米）
}

export interface BoreholeItem {
  id: string
  name: string
  totalDepth: number
  layerCount: number
  location?: BoreholeLocation
}

export interface BoreholeDetail extends BoreholeItem {
  layers: BoreholeLayer[]
}

export interface BoreholeListQuery {
  keyword?: string
  min_depth?: number
  max_depth?: number
}
