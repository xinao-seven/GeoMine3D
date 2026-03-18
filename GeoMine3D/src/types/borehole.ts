export interface BoreholeLayer {
  layerName: string
  topDepth: number
  bottomDepth: number
  thickness: number
}

export interface BoreholeLocation {
  x: number  // 原始 X（东向）
  y: number  // 原始 Y（北向）
  z: number  // 原始 Z（高程）
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
