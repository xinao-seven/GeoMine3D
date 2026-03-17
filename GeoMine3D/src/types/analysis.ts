export interface ThicknessDistribution {
  labels: string[]
  values: number[]
  counts: number[]
}

export interface BoreholeDepthDistribution {
  items: Array<{ name: string; totalDepth: number }>
  labels: string[]
  values: number[]
}

export interface WorkingFaceStatusStats {
  items: Array<{ status: string; count: number }>
  labels: string[]
  values: number[]
}

export interface BoreholeCountStats {
  total: number
  items: Array<{ id: string; name: string; totalDepth: number; layerCount: number }>
}

export interface LayerFrequencyStats {
  labels: string[]
  values: number[]
}

export interface BoreholeXYRawStats {
  items: Array<{ id: string; name: string; x: number; y: number; z: number }>
  labels: string[]
  xValues: number[]
  yValues: number[]
}

export interface DashboardSummary {
  modelCount: number
  boreholeCount: number
  workingFaceCount: number
  stratumModelCount: number
  activeWorkingFaceCount: number
}
