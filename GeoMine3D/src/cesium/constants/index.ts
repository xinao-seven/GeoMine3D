import { HeadingPitchRange, Math as CesiumMath } from 'cesium'

export const DEFAULT_VIEWER_OPTIONS = {
  animation: false,
  timeline: false,
  baseLayerPicker: true,
  geocoder: false,
  homeButton: true,
  sceneModePicker: true,
  navigationHelpButton: false,
  infoBox: false,
  selectionIndicator: true,
  shouldAnimate: true,
} as const

export const DEFAULT_GLOBE_DEPTH_TEST = false
export const DEFAULT_GLOBE_LIGHTING = false
export const DEFAULT_FOG_ENABLED = false

export const DEFAULT_CAMERA_FLY_DURATION = 1.2
export const DEFAULT_CAMERA_HEADING = CesiumMath.toRadians(0)
export const DEFAULT_CAMERA_PITCH = CesiumMath.toRadians(-35)
export const DEFAULT_CAMERA_ROLL = 0

export const DEFAULT_CAMERA_OFFSET = new HeadingPitchRange(
  DEFAULT_CAMERA_HEADING,
  DEFAULT_CAMERA_PITCH,
  2500,
)

export const DEFAULT_POINT_PIXEL_SIZE = 8
export const DEFAULT_LABEL_FONT = '12px Microsoft YaHei'
export const DEFAULT_MEASURE_LABEL_FONT = '14px Microsoft YaHei'

export const DEFAULT_PICK_DISTANCE = Number.POSITIVE_INFINITY
