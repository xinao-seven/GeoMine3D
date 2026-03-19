import * as THREE from 'three'

export type ClipAxis = 'x' | 'y' | 'z'

interface ClipEnableOptions {
    axis?: ClipAxis
    position?: number
    keepLower?: boolean
    showHelper?: boolean
}

interface ClipToolCallbacks {
    onPositionChange?: (position: number) => void
    onRangeChange?: (min: number, max: number) => void
}

/**
 * 剖切工具 - 滑块控制 + 多轴剖切
 */
export class ClipTool {
    private renderer: THREE.WebGLRenderer
    private scene: THREE.Scene
    private enabled = false
    private clipPlane: THREE.Plane
    private axis: ClipAxis = 'y'
    private keepLower = true
    private showHelper = true
    private position = 0
    private minPosition = -1000
    private maxPosition = 1000

    private helperPlane: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>
    private helperFrame: THREE.LineSegments

    private callbacks: ClipToolCallbacks

    constructor(
        renderer: THREE.WebGLRenderer,
        scene: THREE.Scene,
        callbacks: ClipToolCallbacks = {}
    ) {
        this.renderer = renderer
        this.scene = scene
        this.callbacks = callbacks
        this.clipPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)

        const helperGeometry = new THREE.PlaneGeometry(1, 1)
        const helperMaterial = new THREE.MeshBasicMaterial({
            color: 0x00c8ff,
            transparent: true,
            opacity: 0.22,
            side: THREE.DoubleSide,
            depthWrite: false,
        })
        this.helperPlane = new THREE.Mesh(helperGeometry, helperMaterial)
        this.helperPlane.renderOrder = 1000
        this.helperPlane.name = 'clip-helper-plane'
        this.helperPlane.userData.clipHelper = true

        const frameGeometry = new THREE.EdgesGeometry(helperGeometry)
        const frameMaterial = new THREE.LineBasicMaterial({ color: 0x7be8ff, transparent: true, opacity: 0.85 })
        this.helperFrame = new THREE.LineSegments(frameGeometry, frameMaterial)
        this.helperFrame.userData.clipHelper = true
        this.helperPlane.add(this.helperFrame)
    }

    enable(options: ClipEnableOptions = {}) {
        this.axis = options.axis ?? this.axis
        this.keepLower = options.keepLower ?? this.keepLower
        this.showHelper = options.showHelper ?? this.showHelper

        this.updateBoundsFromScene()

        const fallbackPosition = this.keepLower ? this.maxPosition : this.minPosition
        this.position = this.clamp(options.position ?? this.position ?? fallbackPosition)

        this.updateClipPlane()
        this.updateHelperPlane()
        this.setHelperVisible(this.showHelper)

        this.renderer.clippingPlanes = [this.clipPlane]
        this.renderer.localClippingEnabled = true
        this.enabled = true

        this.callbacks.onPositionChange?.(this.position)
        this.callbacks.onRangeChange?.(this.minPosition, this.maxPosition)
    }

    disable() {
        this.renderer.clippingPlanes = []
        this.renderer.localClippingEnabled = false
        this.enabled = false

        this.setHelperVisible(false)
    }

    setAxis(axis: ClipAxis) {
        this.axis = axis
        this.updateBoundsFromScene()
        this.position = this.clamp(this.position)
        this.updateClipPlane()
        this.updateHelperPlane()
        this.callbacks.onPositionChange?.(this.position)
        this.callbacks.onRangeChange?.(this.minPosition, this.maxPosition)
        if (this.enabled) this.renderer.clippingPlanes = [this.clipPlane]
    }

    setKeepLower(keepLower: boolean) {
        this.keepLower = keepLower
        this.updateClipPlane()
        if (this.enabled) this.renderer.clippingPlanes = [this.clipPlane]
    }

    setShowHelper(showHelper: boolean) {
        this.showHelper = showHelper
        this.setHelperVisible(this.enabled && this.showHelper)
    }

    setHeight(value: number) {
        this.setPosition(value)
    }

    setPosition(value: number) {
        this.position = this.clamp(value)
        this.updateClipPlane()
        this.updateHelperPlane()
        if (this.enabled) this.renderer.clippingPlanes = [this.clipPlane]
        this.callbacks.onPositionChange?.(this.position)
    }

    getHeight() {
        return this.position
    }

    getPosition() {
        return this.position
    }

    getAxis() {
        return this.axis
    }

    getKeepLower() {
        return this.keepLower
    }

    getRange() {
        return { min: this.minPosition, max: this.maxPosition }
    }

    isEnabled() {
        return this.enabled
    }

    dispose() {
        this.disable()
        this.scene.remove(this.helperPlane)
        this.helperPlane.geometry.dispose()
        this.helperPlane.material.dispose()
        this.helperFrame.geometry.dispose()
        ;(this.helperFrame.material as THREE.Material).dispose()
    }

    private updateBoundsFromScene() {
        const box = new THREE.Box3()
        this.scene.traverse((obj) => {
            const mesh = obj as THREE.Mesh
            if (!mesh.isMesh) return
            if (mesh.userData.clipHelper || !mesh.visible) return
            box.expandByObject(mesh)
        })

        if (box.isEmpty()) {
            this.minPosition = -1000
            this.maxPosition = 1000
            this.resizeHelperPlane(600)
            return
        }

        const axisKey = this.axis
        this.minPosition = box.min[axisKey]
        this.maxPosition = box.max[axisKey]

        const size = box.getSize(new THREE.Vector3())
        const major = Math.max(size.x, size.y, size.z)
        this.resizeHelperPlane(Math.max(major * 1.2, 200))
    }

    private resizeHelperPlane(size: number) {
        const geometry = this.helperPlane.geometry
        geometry.dispose()
        this.helperPlane.geometry = new THREE.PlaneGeometry(size, size)
        this.helperFrame.geometry.dispose()
        this.helperFrame.geometry = new THREE.EdgesGeometry(this.helperPlane.geometry)
    }

    private updateClipPlane() {
        const axisVector = this.getAxisVector(this.axis)
        const normal = this.keepLower ? axisVector : axisVector.clone().multiplyScalar(-1)
        const constant = this.keepLower ? -this.position : this.position
        this.clipPlane.set(normal, constant)
    }

    private updateHelperPlane() {
        this.helperPlane.position.set(0, 0, 0)
        if (this.axis === 'x') {
            this.helperPlane.rotation.set(0, Math.PI / 2, 0)
            this.helperPlane.position.x = this.position
        }
        if (this.axis === 'y') {
            this.helperPlane.rotation.set(-Math.PI / 2, 0, 0)
            this.helperPlane.position.y = this.position
        }
        if (this.axis === 'z') {
            this.helperPlane.rotation.set(0, 0, 0)
            this.helperPlane.position.z = this.position
        }
    }

    private setHelperVisible(visible: boolean) {
        if (visible && !this.helperPlane.parent) {
            this.scene.add(this.helperPlane)
        }
        this.helperPlane.visible = visible
    }

    private getAxisVector(axis: ClipAxis) {
        if (axis === 'x') return new THREE.Vector3(1, 0, 0)
        if (axis === 'z') return new THREE.Vector3(0, 0, 1)
        return new THREE.Vector3(0, 1, 0)
    }

    private clamp(value: number) {
        return Math.min(this.maxPosition, Math.max(this.minPosition, value))
    }
}
