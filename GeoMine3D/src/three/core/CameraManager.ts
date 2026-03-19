import * as THREE from 'three'
import { CAMERA_FOV, CAMERA_NEAR, CAMERA_FAR, CAMERA_INITIAL_POSITION } from '../constants'

export class CameraManager {
    readonly camera: THREE.PerspectiveCamera

    constructor(aspect: number) {
        // 透视相机: FOV 决定纵向视角，near/far 决定可见深度范围
        this.camera = new THREE.PerspectiveCamera(CAMERA_FOV, aspect, CAMERA_NEAR, CAMERA_FAR)
        this.resetPosition()
    }

    resetPosition() {
        const { x, y, z } = CAMERA_INITIAL_POSITION
        // 初始位姿采用俯视全场，便于进入页面后快速建立空间方位感
        this.camera.position.set(x, y, z)
        this.camera.lookAt(0, 0, 0)
    }

    updateAspect(width: number, height: number) {
        // 只更新宽高比并重建投影矩阵，避免画面拉伸
        this.camera.aspect = width / height
        this.camera.updateProjectionMatrix()
    }

    flyTo(target: THREE.Vector3, distance = 2000) {
        // 沿当前“相机->目标”反方向回退固定距离，保证飞行后仍朝向目标
        const dir = this.camera.position.clone().sub(target).normalize()
        this.camera.position.copy(target.clone().add(dir.multiplyScalar(distance)))
        this.camera.lookAt(target)
    }

    fitToBox(box: THREE.Box3) {
        if (box.isEmpty()) return null

        const center = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        const maxDim = Math.max(size.x, size.y, size.z)
        const fov = THREE.MathUtils.degToRad(this.camera.fov)
        // 根据视锥几何关系估算“看全包围盒”所需距离，并给 2 倍余量
        const fitDistance = Math.max(Math.abs(maxDim / 2 / Math.tan(fov / 2)) * 2.0, 300)

        // 斜向观察比纯正上方/正前方更容易看出体积关系
        const offset = new THREE.Vector3(0.7, 0.7, 0.7).normalize().multiplyScalar(fitDistance)
        const position = center.clone().add(offset)

        // near/far 跟随目标尺度调整，兼顾精度与可见范围
        const near = Math.max(fitDistance / 100, 0.1)
        const far = Math.max(fitDistance * 10, near + 1000)

        return { center, size, maxDim, fitDistance, position, near, far }
    }

    animateTo(
        targetPosition: THREE.Vector3,
        targetLookAt: THREE.Vector3,
        startLookAt: THREE.Vector3,
        onFrame: (lookAt: THREE.Vector3) => void,
        duration = 900
    ) {
        const startPos = this.camera.position.clone()
        const startTime = performance.now()

        const frame = (now: number) => {
            const t = Math.min((now - startTime) / duration, 1)
            // easeInOutQuad: 起停平滑，避免机械匀速的突兀感
            const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2

            this.camera.position.lerpVectors(startPos, targetPosition, eased)
            const lookAt = new THREE.Vector3().lerpVectors(startLookAt, targetLookAt, eased)
            this.camera.lookAt(lookAt)
            onFrame(lookAt)

            if (t < 1) {
                requestAnimationFrame(frame)
            }
        }

        requestAnimationFrame(frame)
    }
}
