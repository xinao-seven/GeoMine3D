export interface BoundaryGeometry {
  type: string
  coordinates: any
}

export interface BoundaryFeature {
  type: 'Feature'
  properties: Record<string, any>
  geometry: BoundaryGeometry
}

export interface BoundaryFeatureCollection {
  type: 'FeatureCollection'
  sourceCrs: string
  targetCrs: string
  features: BoundaryFeature[]
}

export interface BoreholeWGS84Point {
  id: string
  name: string
  longitude: number
  latitude: number
  altitude: number
  source: {
    x: number
    y: number
    z: number
  }
}

export interface BoreholeWGS84Response {
  items: BoreholeWGS84Point[]
}

export interface ProjectionMetadata {
  sourceCrs: string
  targetCrs: string
  sourceShpDir: string
}

export interface CesiumTiffBounds {
  west: number
  east: number
  south: number
  north: number
}

export interface CesiumTiffLayerItem {
  id: string
  name: string
  fileName: string
  tifUrl: string
  previewUrl: string
  tfwUrl: string
  auxXmlUrl: string
  ovrUrl: string
  width: number
  height: number
  bounds: CesiumTiffBounds
}

export interface CesiumTiffLayerSkippedItem {
  fileName: string
  reason: string
}

export interface CesiumTiffLayerResponse {
  sourceCrs: string
  targetCrs: string
  items: CesiumTiffLayerItem[]
  skipped: CesiumTiffLayerSkippedItem[]
}
