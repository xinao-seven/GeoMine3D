import * as THREE from 'three'

export interface MeasureResult {
  id: string
  start: THREE.Vector3
  end: THREE.Vector3
  distance: number
}

/**
 * 测量工具 - 两点直线距离
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

  constructor(scene: THREE.Scene, camera: THREE.Camera, domElement: HTMLElement) {
    this.scene = scene
    this.camera = camera
    this.domElement = domElement
    this.group.name = 'measurements'
    this.group.userData.measureHelper = true
    this.scene.add(this.group)
  }

  enable(onMeasure?: (result: MeasureResult) => void) {
    if (this.enabled) return
    this.enabled = true
    this.onMeasure = onMeasure
    this.pendingPoint = null
    this.domElement.addEventListener('click', this.onClick)
  }

  disable() {
    if (!this.enabled) return
    this.enabled = false
    this.pendingPoint = null
    this.domElement.removeEventListener('click', this.onClick)
  }

  clear() {
    this.pendingPoint = null
    this.results = []
    this.group.clear()
  }

  isEnabled() {
    return this.enabled
  }

  getResults() {
    return [...this.results]
  }

  dispose() {
    this.disable()
    this.clear()
    this.scene.remove(this.group)
  }

  private onClick = (event: MouseEvent) => {
    const point = this.pickPoint(event)
    if (!point) return

    if (!this.pendingPoint) {
      this.pendingPoint = point
      this.addPointMarker(point)
      return
    }

    const result = this.createMeasurement(this.pendingPoint, point)
    this.results.push(result)
    this.pendingPoint = null
    this.onMeasure?.(result)
  }

  private pickPoint(event: MouseEvent) {
    const rect = this.domElement.getBoundingClientRect()
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    this.raycaster.setFromCamera(this.pointer, this.camera)
    const intersects = this.raycaster.intersectObjects(this.scene.children, true)
    const hit = intersects.find((item) => !item.object.userData.measureHelper)
    return hit?.point.clone() || null
  }

  private createMeasurement(start: THREE.Vector3, end: THREE.Vector3): MeasureResult {
    const distance = start.distanceTo(end)
    const id = `measure_${Date.now()}_${this.results.length + 1}`

    const geometry = new THREE.BufferGeometry().setFromPoints([start, end])
    const material = new THREE.LineBasicMaterial({ color: 0x00c8ff })
    const line = new THREE.Line(geometry, material)
    line.userData.measureHelper = true
    this.group.add(line)

    this.addPointMarker(end)

    const center = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)
    const label = this.createLabelSprite(`${distance.toFixed(2)} m`)
    label.position.copy(center)
    label.position.y += 10
    label.userData.measureHelper = true
    this.group.add(label)

    return {
      id,
      start: start.clone(),
      end: end.clone(),
      distance,
    }
  }

  private addPointMarker(position: THREE.Vector3) {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(2.5, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0xffb020 })
    )
    marker.position.copy(position)
    marker.userData.measureHelper = true
    this.group.add(marker)
  }

  private createLabelSprite(text: string) {
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 64
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.fillStyle = 'rgba(10, 22, 40, 0.9)'
      ctx.strokeStyle = 'rgba(0, 200, 255, 0.8)'
      ctx.lineWidth = 2
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2)
      ctx.fillStyle = '#e8f4ff'
      ctx.font = 'bold 24px Microsoft YaHei'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(text, canvas.width / 2, canvas.height / 2)
    }

    const texture = new THREE.CanvasTexture(canvas)
    texture.needsUpdate = true
    const material = new THREE.SpriteMaterial({ map: texture, depthTest: false })
    const sprite = new THREE.Sprite(material)
    sprite.scale.set(40, 10, 1)
    return sprite
  }
}
