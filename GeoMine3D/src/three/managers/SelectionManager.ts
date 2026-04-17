import * as THREE from 'three'
import type { HighlightManager } from './HighlightManager'

export type SelectionCallback = (object: THREE.Object3D | null) => void
export type HoverCallback = (object: THREE.Object3D | null, event: MouseEvent | null) => void

export class SelectionManager {
  private raycaster = new THREE.Raycaster()
  private pointer = new THREE.Vector2()
  private camera: THREE.Camera
  private scene: THREE.Scene
  private domElement: HTMLElement
  private highlightManager: HighlightManager
  private onSelect: SelectionCallback
  private onHover?: HoverCallback
  private enabled = true
  private hoverEnabled = true
  private hoveredObject: THREE.Object3D | null = null
  private hoverRafId: number | null = null
  private pendingHoverEvent: MouseEvent | null = null
  private pickTargets: THREE.Object3D[] = []

  constructor(
    camera: THREE.Camera,
    scene: THREE.Scene,
    domElement: HTMLElement,
    highlightManager: HighlightManager,
    onSelect: SelectionCallback,
    onHover?: HoverCallback
  ) {
    this.camera = camera
    this.scene = scene
    this.domElement = domElement
    this.highlightManager = highlightManager
    this.onSelect = onSelect
    this.onHover = onHover
    this.domElement.addEventListener('click', this._onClick)
    this.domElement.addEventListener('mousemove', this._onMouseMove)
    this.domElement.addEventListener('mouseleave', this._onMouseLeave)
  }

  // 从命中结果中回溯到业务对象节点（带 type）。
  private _findBusinessObject(intersects: THREE.Intersection[]): THREE.Object3D | null {
    const hit = intersects.find(i => {
      let obj: THREE.Object3D | null = i.object
      while (obj) {
        if (obj.userData.type) return true
        obj = obj.parent
      }
      return false
    })

    if (!hit) return null

    let obj: THREE.Object3D | null = hit.object
    while (obj) {
      if (obj.userData.type) return obj
      obj = obj.parent ?? null
    }

    return null
  }

  private _pickObjectByEvent(event: MouseEvent): THREE.Object3D | null {
    const rect = this.domElement.getBoundingClientRect()
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    this.raycaster.setFromCamera(this.pointer, this.camera)
    const pickRoots = this.pickTargets.length ? this.pickTargets : this.scene.children
    const intersects = this.raycaster.intersectObjects(pickRoots, true)
    return this._findBusinessObject(intersects)
  }

  // 基于鼠标点击执行射线拾取，并向上回溯到业务对象节点。
  private _onClick = (event: MouseEvent) => {
    if (!this.enabled) return

    const obj = this._pickObjectByEvent(event)
    if (obj) {
      this.highlightManager.select(obj)
      this.onSelect(obj)
      return
    }

    this.highlightManager.select(null)
    this.onSelect(null)
  }

  // 鼠标移动时执行轻量拾取，仅用于悬停提示。
  private _onMouseMove = (event: MouseEvent) => {
    if (!this.enabled || !this.hoverEnabled) {
      if (this.hoveredObject) {
        this.hoveredObject = null
        this.onHover?.(null, null)
      }
      return
    }

    this.pendingHoverEvent = event
    if (this.hoverRafId !== null) return

    this.hoverRafId = window.requestAnimationFrame(() => {
      this.hoverRafId = null
      const latestEvent = this.pendingHoverEvent
      this.pendingHoverEvent = null
      if (!latestEvent || !this.enabled || !this.hoverEnabled) return

      const obj = this._pickObjectByEvent(latestEvent)
      const nextUuid = obj?.uuid ?? null
      const prevUuid = this.hoveredObject?.uuid ?? null
      if (nextUuid === prevUuid) return

      this.hoveredObject = obj
      this.onHover?.(obj, obj ? latestEvent : null)
    })
  }

  // 鼠标离开画布时清理悬停状态。
  private _onMouseLeave = () => {
    this.pendingHoverEvent = null
    if (this.hoverRafId !== null) {
      window.cancelAnimationFrame(this.hoverRafId)
      this.hoverRafId = null
    }
    if (!this.hoveredObject) return
    this.hoveredObject = null
    this.onHover?.(null, null)
  }

  // 启停选择能力，关闭时会清空当前选中状态。
  setEnabled(enabled: boolean) {
    this.enabled = enabled
    if (!enabled) {
      this.highlightManager.select(null)
      this.onSelect(null)
      if (this.hoveredObject) {
        this.hoveredObject = null
        this.onHover?.(null, null)
      }
      this.pendingHoverEvent = null
      if (this.hoverRafId !== null) {
        window.cancelAnimationFrame(this.hoverRafId)
        this.hoverRafId = null
      }
    }
  }

  // 控制悬停拾取能力，不影响点击选择。
  setHoverEnabled(enabled: boolean) {
    this.hoverEnabled = enabled
    if (!enabled) {
      this.pendingHoverEvent = null
      if (this.hoverRafId !== null) {
        window.cancelAnimationFrame(this.hoverRafId)
        this.hoverRafId = null
      }
      if (this.hoveredObject) {
        this.hoveredObject = null
        this.onHover?.(null, null)
      }
    }
  }

  // 设置用于拾取的对象根节点白名单。
  setPickTargets(targets: THREE.Object3D[]) {
    this.pickTargets = targets
  }

  // 解绑事件监听。
  dispose() {
    this.pendingHoverEvent = null
    if (this.hoverRafId !== null) {
      window.cancelAnimationFrame(this.hoverRafId)
      this.hoverRafId = null
    }
    this.domElement.removeEventListener('click', this._onClick)
    this.domElement.removeEventListener('mousemove', this._onMouseMove)
    this.domElement.removeEventListener('mouseleave', this._onMouseLeave)
  }
}
