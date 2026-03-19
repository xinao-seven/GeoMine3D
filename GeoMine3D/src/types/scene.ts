export type SceneObjectType = 'stratum' | 'borehole' | 'workingface'

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
}

export interface OpacityState {
  stratum: number
  borehole: number
  workingface: number
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
  clipHelperVisible: boolean
  measureEnabled: boolean
  annotationEnabled: boolean
}

export interface MeasurementRecord {
  id: string
  distance: number
  start: { x: number; y: number; z: number }
  end: { x: number; y: number; z: number }
}
