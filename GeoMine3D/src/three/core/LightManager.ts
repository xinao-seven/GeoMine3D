import * as THREE from 'three'
import {
    AMBIENT_LIGHT_COLOR,
    DIR_LIGHT_COLOR,
} from '../constants'

export class LightManager {
    private ambientLight: THREE.AmbientLight
    private headLight: THREE.DirectionalLight
    private headLightTarget: THREE.Object3D
    private tempForward = new THREE.Vector3()
    private tempTarget = new THREE.Vector3()

    constructor(scene: THREE.Scene) {
        // 适量环境光，避免背光面完全发黑
        this.ambientLight = new THREE.AmbientLight(AMBIENT_LIGHT_COLOR, 0.32)
        scene.add(this.ambientLight)

        // Headlight：主方向光随相机移动与朝向
        this.headLight = new THREE.DirectionalLight(DIR_LIGHT_COLOR, 1.05)
        this.headLight.castShadow = false
        scene.add(this.headLight)

        this.headLightTarget = new THREE.Object3D()
        scene.add(this.headLightTarget)
        this.headLight.target = this.headLightTarget
    }

    updateFromCamera(camera: THREE.PerspectiveCamera) {
        this.headLight.position.copy(camera.position)
        camera.getWorldDirection(this.tempForward)
        this.tempTarget.copy(camera.position).add(this.tempForward.multiplyScalar(300))
        this.headLightTarget.position.copy(this.tempTarget)
        this.headLightTarget.updateMatrixWorld()
    }
}
