import request from '../request'
import type {
  ThicknessDistribution,
  BoreholeDepthDistribution,
  WorkingFaceStatusStats,
  BoreholeCountStats,
  LayerFrequencyStats,
  BoreholeXYRawStats,
  DashboardSummary,
} from '@/types'

export function getThicknessStats(): Promise<ThicknessDistribution> {
  return request.get('/analysis/thickness-distribution')
}

export function getBoreholeDepthStats(): Promise<BoreholeDepthDistribution> {
  return request.get('/analysis/borehole-depth-distribution')
}

export function getWorkingFaceStats(): Promise<WorkingFaceStatusStats> {
  return request.get('/analysis/workingface-status')
}

export function getBoreholeCountStats(): Promise<BoreholeCountStats> {
  return request.get('/analysis/borehole-count')
}

export function getLayerFrequencyStats(): Promise<LayerFrequencyStats> {
  return request.get('/analysis/layer-frequency')
}

export function getBoreholeXYRawStats(): Promise<BoreholeXYRawStats> {
  return request.get('/analysis/borehole-xy-raw')
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return request.get('/dashboard/summary')
}
