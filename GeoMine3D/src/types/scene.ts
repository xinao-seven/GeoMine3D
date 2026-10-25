export type SceneObjectType = 'stratum' | 'borehole' | 'workingface' | 'roadway'

export interface SceneObject {
  id: string
  name: string
  type: SceneObjectType
  data?: Record<string, unknown>
}

export interface LayerState {
  stratum: boolean
  borehole: boolean
  workingface: boolean
  roadway: boolean
}

export interface StratumLayerControl {
  key: string
  modelId: string
  modelName: string
  layerName: string
  visible: boolean
  opacity: number
  color: string
}

export interface ToolState {
  clipEnabled: boolean
  clipHeight: number
  clipAxis: 'x' | 'y' | 'z'
  clipKeepLower: boolean
  measureEnabled: boolean
  annotationEnabled: boolean
  explodeGap: number
}

export interface MeasurementRecord {
  id: string
  distance: number
  start: { x: number; y: number; z: number }
  end: { x: number; y: number; z: number }
}

/** 标注记录镜像（来自 AnnotationTool，或持久化恢复），坐标为场景世界坐标 */
export interface AnnotationRecord {
  id: string
  text: string
  position: { x: number; y: number; z: number }
  createdAt: number
  /** 持久化到服务端后的记录 id（本地模式为 null） */
  serverId?: string | null
}
