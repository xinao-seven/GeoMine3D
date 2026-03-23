import * as THREE from 'three'
import type { BoreholeItem } from '@/types'

/**
 * 用几何体在前端生成简化钻孔柱体表示。
 * 坐标系：1 unit = 1 meter，钻孔范围约 5km × 5km。
 */
export class BoreholeModelLoader {
  createBoreholeObject(
    borehole: BoreholeItem,
    position?: { x: number; y: number; z: number },
    verticalScale = 1
  ): THREE.Group {
    const group = new THREE.Group()
    group.name = `borehole_${borehole.id}`
    group.userData = { id: borehole.id, name: borehole.name, type: 'borehole', boreholeData: borehole }

    const depth = Math.max(borehole.totalDepth, 100) * verticalScale
    const radius = 30
    const geometry = new THREE.CylinderGeometry(radius, radius, depth, 8)
    const material = new THREE.MeshLambertMaterial({
      color: 0x4488ff,
      clipShadows: true,
    })
    material.clippingPlanes = []
    const mesh = new THREE.Mesh(geometry, material)
    // CylinderGeometry默认沿Y轴，旋转到Z轴以匹配原始地质坐标的竖直方向
    mesh.rotation.x = Math.PI / 2
    mesh.position.z = -depth / 2
    group.add(mesh)

    // 顶部标记球（地表位置）
    const markerGeom = new THREE.SphereGeometry(50, 8, 8)
    const markerMat = new THREE.MeshLambertMaterial({ color: 0x00c8ff })
    markerMat.clippingPlanes = []
    const marker = new THREE.Mesh(markerGeom, markerMat)
    group.add(marker)

    if (position) {
      group.position.set(position.x, position.y, position.z)
    }

    return group
  }
}
