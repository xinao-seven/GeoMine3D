import * as THREE from 'three'
import type { HighlightManager } from './HighlightManager'

export type SelectionCallback = (object: THREE.Object3D | null) => void

export class SelectionManager {
  private raycaster = new THREE.Raycaster()
  private pointer = new THREE.Vector2()
  private camera: THREE.Camera
  private scene: THREE.Scene
  private domElement: HTMLElement
  private highlightManager: HighlightManager
  private onSelect: SelectionCallback

  constructor(
    camera: THREE.Camera,
    scene: THREE.Scene,
    domElement: HTMLElement,
    highlightManager: HighlightManager,
    onSelect: SelectionCallback
  ) {
    this.camera = camera
    this.scene = scene
    this.domElement = domElement
    this.highlightManager = highlightManager
    this.onSelect = onSelect
    this.domElement.addEventListener('click', this._onClick)
  }

  private _onClick = (event: MouseEvent) => {
    const rect = this.domElement.getBoundingClientRect()
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    this.raycaster.setFromCamera(this.pointer, this.camera)
    const intersects = this.raycaster.intersectObjects(this.scene.children, true)

    const hit = intersects.find(i => {
      let obj: THREE.Object3D | null = i.object
      while (obj) {
        if (obj.userData.type) return true
        obj = obj.parent
      }
      return false
    })

    if (hit) {
      let obj: THREE.Object3D | null = hit.object
      while (obj) {
        if (obj.userData.type) break
        obj = obj.parent ?? null
      }
      if (obj) {
        this.highlightManager.select(obj)
        this.onSelect(obj)
        return
      }
    }

    this.highlightManager.select(null)
    this.onSelect(null)
  }

  dispose() {
    this.domElement.removeEventListener('click', this._onClick)
  }
}
