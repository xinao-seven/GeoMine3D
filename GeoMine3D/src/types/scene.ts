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
