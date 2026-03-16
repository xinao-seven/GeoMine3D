export interface ModelBbox {
  min: [number, number, number]
  max: [number, number, number]
}

export type ModelType = 'stratum' | 'borehole' | 'workingface'

export interface ModelItem {
  id: string
  name: string
  type: ModelType
  version: string
  format: string
  description: string
  fileName: string
  fileUrl: string
  bbox?: ModelBbox
}

export type ModelDetail = ModelItem

export interface ModelResource {
  id: string
  name: string
  fileUrl: string
  format: string
  bbox?: ModelBbox
}
