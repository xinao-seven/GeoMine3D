import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'

export class ControlsManager {
  readonly controls: OrbitControls

  constructor(camera: THREE.Camera, domElement: HTMLElement) {
    this.controls = new OrbitControls(camera, domElement)
    this.controls.enableDamping = true
    this.controls.dampingFactor = 0.05
    this.controls.screenSpacePanning = false
    this.controls.minDistance = 10
    this.controls.maxDistance = 200000
    this.controls.maxPolarAngle = Math.PI / 2 + 0.1
  }

  update() {
    this.controls.update()
  }

  setDistanceLimits(minDistance: number, maxDistance: number) {
    this.controls.minDistance = Math.max(0.1, minDistance)
    this.controls.maxDistance = Math.max(this.controls.minDistance + 1, maxDistance)
  }

  dispose() {
    this.controls.dispose()
  }
}
