import * as THREE from 'three'

export interface MeasureResult {
  id: string
  start: THREE.Vector3
  end: THREE.Vector3
  distance: number
}

interface DynamicLabel {
  sprite: THREE.Sprite
  aspect: number
  anchor: THREE.Vector3
}

const LINE_COLOR = 0xffa733
const MARKER_COLOR = 0xffc85e
const TARGET_LABEL_PX_HEIGHT = 30
const MIN_LABEL_HEIGHT = 8
const MAX_LABEL_HEIGHT = 600

/**
 * 测量工具 - 两点直线距离
 * 线体用圆柱网格加粗并关闭深度测试，保证在地层模型上方始终可见；
 * 距离标签放在测线旁并随视角距离自动缩放。
 */
export class MeasureTool {
  private scene: THREE.Scene
  private camera: THREE.Camera
  private domElement: HTMLElement
  private raycaster = new THREE.Raycaster()
  private pointer = new THREE.Vector2()
  private enabled = false
  private pendingPoint: THREE.Vector3 | null = null
  private group = new THREE.Group()
  private results: MeasureResult[] = []
  private onMeasure?: (result: MeasureResult) => void
  private resources: Array<THREE.Material | THREE.BufferGeometry | THREE.Texture> = []
  private labels: DynamicLabel[] = []

  constructor(scene: THREE.Scene, camera: THREE.Camera, domElement: HTMLElement) {
    this.scene = scene
    this.camera = camera
    this.domElement = domElement
    this.group.name = 'measurements'
    this.group.userData.measureHelper = true
    this.scene.add(this.group)
  }

  // 启用测量模式并绑定点击事件。
  enable(onMeasure?: (result: MeasureResult) => void) {
    if (this.enabled) return
    this.enabled = true
    this.onMeasure = onMeasure
    this.pendingPoint = null
    this.domElement.addEventListener('click', this.onClick)
  }

  // 关闭测量模式并解绑点击事件。
  disable() {
    if (!this.enabled) return
    this.enabled = false
    this.pendingPoint = null
    this.domElement.removeEventListener('click', this.onClick)
  }

  // 清空所有测量结果与辅助图元。
  clear() {
    this.pendingPoint = null
    this.results = []
    this.labels = []
    this.group.clear()
    for (const res of this.resources) res.dispose()
    this.resources = []
  }

  // 每帧根据相机距离缩放距离标签，保证任何视角下清晰可读。
  update() {
    if (!this.labels.length) return
    for (const item of this.labels) {
      const height = THREE.MathUtils.clamp(
        this.getWorldUnitsPerPixel(item.anchor) * TARGET_LABEL_PX_HEIGHT,
        MIN_LABEL_HEIGHT,
        MAX_LABEL_HEIGHT,
      )
      item.sprite.scale.set(height * item.aspect, height, 1)
    }
  }

  // 获取测量工具是否启用。
  isEnabled() {
    return this.enabled
  }

  // 获取当前测量结果快照。
  getResults() {
    return [...this.results]
  }

  // 销毁工具并从场景移除内部容器。
  dispose() {
    this.disable()
    this.clear()
    this.scene.remove(this.group)
  }

  // 点击一次记录起点，再点击一次完成一条测距线。
  private onClick = (event: MouseEvent) => {
    const point = this.pickPoint(event)
    if (!point) return

    if (!this.pendingPoint) {
      this.pendingPoint = point
      this.addPointMarker(point, 6)
      return
    }

    const result = this.createMeasurement(this.pendingPoint, point)
    this.results.push(result)
    this.pendingPoint = null
    this.onMeasure?.(result)
  }

  // 通过射线拾取获取场景中的落点。
  private pickPoint(event: MouseEvent) {
    const rect = this.domElement.getBoundingClientRect()
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    this.raycaster.setFromCamera(this.pointer, this.camera)
    const intersects = this.raycaster.intersectObjects(this.scene.children, true)
    const hit = intersects.find((item) => {
      const data = item.object.userData
      return !data.measureHelper && !data.annotationHelper && !data.clipHelper
    })
    return hit?.point.clone() || null
  }

  // 根据两点创建加粗测线、端点标记和线旁距离标签。
  private createMeasurement(start: THREE.Vector3, end: THREE.Vector3): MeasureResult {
    const distance = start.distanceTo(end)
    const id = `measure_${Date.now()}_${this.results.length + 1}`
    const renderOrder = 998

    // 用单位圆柱按两点方向摆放，形成有粗细的测线；半径随线长自适应。
    const radius = THREE.MathUtils.clamp(distance * 0.004, 1.2, 60)
    const direction = end.clone().sub(start).normalize()
    const unitCylinder = new THREE.CylinderGeometry(1, 1, 1, 10, 1, true)
    const lineMaterial = new THREE.MeshBasicMaterial({
      color: LINE_COLOR,
      depthTest: false,
      transparent: true,
      opacity: 0.95,
    })
    const line = new THREE.Mesh(unitCylinder, lineMaterial)
    line.scale.set(radius, distance, radius)
    line.position.copy(start).add(end).multiplyScalar(0.5)
    line.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction)
    line.renderOrder = renderOrder
    line.userData.measureHelper = true
    this.group.add(line)
    this.resources.push(unitCylinder, lineMaterial)

    this.addPointMarker(start, radius * 1.6)
    this.addPointMarker(end, radius * 1.6)

    // 标签放在测线中点旁：沿测线水平法向偏移，避免遮住线体。
    const center = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)
    const perpendicular = new THREE.Vector3()
      .crossVectors(direction, new THREE.Vector3(0, 1, 0))
    if (perpendicular.lengthSq() < 1e-6) {
      perpendicular.set(1, 0, 0)
    }
    perpendicular.normalize()
    const anchor = center.clone()
      .addScaledVector(perpendicular, radius * 4)
      .add(new THREE.Vector3(0, radius * 2, 0))
    const { sprite, aspect } = this.createLabelSprite(`${distance.toFixed(2)} m`)
    sprite.position.copy(anchor)
    sprite.renderOrder = 999
    sprite.userData.measureHelper = true
    this.group.add(sprite)
    this.labels.push({ sprite, aspect, anchor })

    return {
      id,
      start: start.clone(),
      end: end.clone(),
      distance,
    }
  }

  // 添加测量点位标记（尺寸随测线粗细缩放，始终浮于模型上方）。
  private addPointMarker(position: THREE.Vector3, radius: number) {
    const geometry = new THREE.SphereGeometry(radius, 14, 14)
    const material = new THREE.MeshBasicMaterial({
      color: MARKER_COLOR,
      depthTest: false,
      transparent: true,
      opacity: 0.95,
    })
    const marker = new THREE.Mesh(geometry, material)
    marker.position.copy(position)
    marker.renderOrder = 999
    marker.userData.measureHelper = true
    this.group.add(marker)
    this.resources.push(geometry, material)
  }

  // 生成用于显示距离文本的精灵。
  private createLabelSprite(text: string) {
    const canvas = document.createElement('canvas')
    canvas.width = 320
    canvas.height = 80
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.fillStyle = 'rgba(12, 18, 14, 0.92)'
      ctx.strokeStyle = 'rgba(255, 167, 51, 0.95)'
      ctx.lineWidth = 4
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.strokeRect(2, 2, canvas.width - 4, canvas.height - 4)
      ctx.fillStyle = '#ffe9c4'
      ctx.font = 'bold 36px Microsoft YaHei'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(text, canvas.width / 2, canvas.height / 2)
    }

    const texture = new THREE.CanvasTexture(canvas)
    texture.needsUpdate = true
    const material = new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true })
    const sprite = new THREE.Sprite(material)
    sprite.scale.set(40, 10, 1)

    this.resources.push(texture, material)
    return { sprite, aspect: canvas.width / canvas.height }
  }

  private getWorldUnitsPerPixel(anchor: THREE.Vector3) {
    const viewportHeight = Math.max(
      this.domElement.clientHeight || this.domElement.getBoundingClientRect().height,
      1,
    )

    if ((this.camera as THREE.PerspectiveCamera).isPerspectiveCamera) {
      const perspective = this.camera as THREE.PerspectiveCamera
      const distance = perspective.position.distanceTo(anchor)
      const fov = THREE.MathUtils.degToRad(perspective.fov)
      return (2 * distance * Math.tan(fov / 2)) / viewportHeight
    }

    if ((this.camera as THREE.OrthographicCamera).isOrthographicCamera) {
      const ortho = this.camera as THREE.OrthographicCamera
      return ((ortho.top - ortho.bottom) / ortho.zoom) / viewportHeight
    }

    return 1
  }
}
