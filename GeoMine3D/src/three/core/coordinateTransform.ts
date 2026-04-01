import * as THREE from 'three'

// 原始地质坐标系: x右, y向屏幕内, z向上
// Three.js坐标系:   x右, y向上,   z向屏幕外
// 统一映射: (x, y, z) -> (x, z, -y)
export const GEO_ROOT_ROTATION_X = -Math.PI / 2

export interface RawGeoPoint {
	x: number
	y: number
	z: number
}

// 将原始地学坐标映射到 Three.js 显示坐标。
export function mapRawGeoToThreeDisplay(point: RawGeoPoint): THREE.Vector3 {
	return new THREE.Vector3(point.x, point.z, -point.y)
}
