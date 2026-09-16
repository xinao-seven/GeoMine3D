import * as THREE from 'three'
import { BOREHOLE_LAYER_FALLBACK_COLOR } from '@/constants/strataColors'
import type { BoreholeItem, BoreholeLayer } from '@/types'

/**
 * 前端按分层生成钻孔柱体。
 *
 * 坐标系：1 unit = 1 meter，孔口位于组原点，柱体沿 -Z（向下 = 更深）生长。
 *
 * 性能：单根钻孔的多个分层合并到 **一个 InstancedMesh**（共用一份单位高圆柱几何，
 * 逐实例写变换矩阵 + instanceColor），2548 段 → 182 次绘制，同时保留
 * “每孔一个 Object3D”的结构，拾取/移除/显隐/整体透明度都不受影响。
 * 几何与材质在全部钻孔间共享，由 ResourceTracker 按引用计数管理。
 */

const BOREHOLE_RADIUS = 30
const COLLAR_MARKER_RADIUS = 50
const RADIAL_SEGMENTS = 10
/** 无分层数据时的兜底柱体颜色（与分层配色区分开） */
const UNIFORM_COLOR = 0x4488ff
const COLLAR_MARKER_COLOR = 0x00c8ff

let segmentGeometry: THREE.CylinderGeometry | null = null
let collarGeometry: THREE.SphereGeometry | null = null
/** 分层柱体材质：底色必须是白色，实例色才是最终颜色 */
let segmentMaterial: THREE.MeshLambertMaterial | null = null
let uniformMaterial: THREE.MeshLambertMaterial | null = null
let collarMaterial: THREE.MeshLambertMaterial | null = null

/** 单位高圆柱：顶面 z=0、底面 z=-1，实例只做 Z 方向缩放与平移 */
function getSegmentGeometry() {
  if (!segmentGeometry) {
    segmentGeometry = new THREE.CylinderGeometry(
      BOREHOLE_RADIUS,
      BOREHOLE_RADIUS,
      1,
      RADIAL_SEGMENTS,
    )
    // CylinderGeometry 默认沿 Y 轴，转到 Z 轴以匹配地质竖直方向
    segmentGeometry.rotateX(Math.PI / 2)
    segmentGeometry.translate(0, 0, -0.5)
  }
  return segmentGeometry
}

function getCollarGeometry() {
  if (!collarGeometry) {
    collarGeometry = new THREE.SphereGeometry(COLLAR_MARKER_RADIUS, 8, 8)
  }
  return collarGeometry
}

function getSegmentMaterial() {
  if (!segmentMaterial) {
    segmentMaterial = new THREE.MeshLambertMaterial({ color: 0xffffff, clipShadows: true })
  }
  return segmentMaterial
}

function getUniformMaterial() {
  if (!uniformMaterial) {
    uniformMaterial = new THREE.MeshLambertMaterial({ color: UNIFORM_COLOR, clipShadows: true })
  }
  return uniformMaterial
}

function getCollarMaterial() {
  if (!collarMaterial) {
    collarMaterial = new THREE.MeshLambertMaterial({ color: COLLAR_MARKER_COLOR })
  }
  return collarMaterial
}

export class BoreholeModelLoader {
  // 根据钻孔数据生成可视化对象，并可按需指定场景坐标与垂向缩放。
  createBoreholeObject(
    borehole: BoreholeItem,
    position?: { x: number; y: number; z: number },
    verticalScale = 1
  ): THREE.Group {
    const group = new THREE.Group()
    group.name = `borehole_${borehole.id}`
    group.userData = { id: borehole.id, name: borehole.name, type: 'borehole', boreholeData: borehole }

    const scale = Number.isFinite(verticalScale) && verticalScale > 0 ? verticalScale : 1
    // 0 厚度层没有体积，不生成几何（数据仍保留在 boreholeData.layers 中）
    const layers = (borehole.layers ?? []).filter((layer) => layer.thickness > 0)

    group.add(layers.length ? this.createLayerColumn(layers, scale) : this.createUniformColumn(borehole, scale))

    // 顶部标记球（地表位置）
    const marker = new THREE.Mesh(getCollarGeometry(), getCollarMaterial())
    marker.name = 'borehole_collar'
    group.add(marker)

    if (position) {
      group.position.set(position.x, position.y, position.z)
    }

    return group
  }

  /** 分层柱体：一个 InstancedMesh 承载该孔全部非零厚度分层 */
  private createLayerColumn(layers: BoreholeLayer[], scale: number) {
    const column = new THREE.InstancedMesh(getSegmentGeometry(), getSegmentMaterial(), layers.length)
    column.name = 'borehole_layers'

    const matrix = new THREE.Matrix4()
    const instancePosition = new THREE.Vector3()
    const instanceScale = new THREE.Vector3()
    const quaternion = new THREE.Quaternion()
    const color = new THREE.Color()

    layers.forEach((layer, index) => {
      // 顶面对齐到该层顶深，长度 = 厚度（几何本身高 1，因此 Z 缩放即厚度）
      instancePosition.set(0, 0, -layer.topDepth * scale)
      instanceScale.set(1, 1, layer.thickness * scale)
      matrix.compose(instancePosition, quaternion, instanceScale)
      column.setMatrixAt(index, matrix)
      column.setColorAt(index, color.set(layer.color || BOREHOLE_LAYER_FALLBACK_COLOR))
    })

    column.instanceMatrix.needsUpdate = true
    if (column.instanceColor) column.instanceColor.needsUpdate = true
    // 拾取与视锥剔除都依赖包围体：先算紧包围盒，再由盒推一个紧包围球。
    // （不能用 InstancedMesh.computeBoundingSphere：它按“最大轴缩放”估算球半径，
    //   在“细长柱体”这种非均匀缩放下会把半径放大约 thickness 倍。）
    column.computeBoundingBox()
    if (column.boundingBox) {
      column.boundingSphere = column.boundingBox.getBoundingSphere(new THREE.Sphere())
    }
    return column
  }

  /** 兜底柱体：没有分层数据时按总孔深画一根单色柱子 */
  private createUniformColumn(borehole: BoreholeItem, scale: number) {
    const depth = Math.max(borehole.totalDepth, 100) * scale
    const mesh = new THREE.Mesh(getSegmentGeometry(), getUniformMaterial())
    mesh.name = 'borehole_column'
    // 单位高几何：Z 缩放即孔深，顶面仍在孔口
    mesh.scale.set(1, 1, depth)
    return mesh
  }
}
