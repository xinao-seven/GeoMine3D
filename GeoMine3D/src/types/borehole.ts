export interface BoreholeLayer {
  layerName: string
  topDepth: number
  bottomDepth: number
  thickness: number
  /** 分层显示色（来自后端 borehole_segments.color） */
  color: string
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
  /** 分层数据（BoreholeDetail 必填；列表项可能为 undefined） */
  layers?: BoreholeLayer[]
}

export interface BoreholeDetail extends BoreholeItem {
  layers: BoreholeLayer[]
}
