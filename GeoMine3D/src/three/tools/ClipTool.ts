import * as THREE from 'three'

/**
 * 剖切工具 - 基础 Plane Clipping 实现
 */
export class ClipTool {
  private renderer: THREE.WebGLRenderer
  private enabled = false
  private clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0)

  constructor(renderer: THREE.WebGLRenderer) {
    this.renderer = renderer
  }

  enable(planeNormal = new THREE.Vector3(0, -1, 0), constant = 0) {
    this.clipPlane = new THREE.Plane(planeNormal, constant)
    this.renderer.clippingPlanes = [this.clipPlane]
    this.renderer.localClippingEnabled = true
    this.enabled = true
  }

  disable() {
    this.renderer.clippingPlanes = []
    this.enabled = false
  }

  setHeight(y: number) {
    this.clipPlane.constant = y
  }

  isEnabled() {
    return this.enabled
  }
}
