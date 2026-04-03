export const SCENE_BACKGROUND_COLOR = 0x0a1628
export const GRID_COLOR = 0x1e3a5f
export const AMBIENT_LIGHT_COLOR = 0xffffff
export const AMBIENT_LIGHT_INTENSITY = 0.6
export const DIR_LIGHT_COLOR = 0xffffff
export const DIR_LIGHT_INTENSITY = 0.8

export const CAMERA_FOV = 50
export const CAMERA_NEAR = 1
export const CAMERA_FAR = 500000
// 矿区范围约 5km × 4.5km，相机初始位于中心上方偏后方俯视全场
export const CAMERA_INITIAL_POSITION = { x: 0, y: 2000, z: 6000 }

export const HIGHLIGHT_COLOR = 0x00c8ff
export const SELECTION_COLOR = 0xffb020

export const OBJECT_TYPES = {
  STRATUM: 'stratum',
  BOREHOLE: 'borehole',
  WORKINGFACE: 'workingface',
} as const
