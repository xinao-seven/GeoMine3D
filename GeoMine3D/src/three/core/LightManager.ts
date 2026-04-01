import * as THREE from 'three'
import {
    AMBIENT_LIGHT_COLOR,
    DIR_LIGHT_COLOR,
} from '../constants'

export class LightManager {
    // 环境光: 提供基础亮度，避免未被直射的面完全黑掉
    private ambientLight: THREE.AmbientLight
    // 方向光: 作为“头灯”随相机朝向变化，突出当前观察区域
    private headLight: THREE.DirectionalLight
    // DirectionalLight 的 target 必须是场景对象，不能只传坐标
    private headLightTarget: THREE.Object3D
    // 复用临时向量，减少每帧 update 产生的对象分配
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

    // 根据当前相机姿态更新头灯位置与方向。
    updateFromCamera(camera: THREE.PerspectiveCamera) {
        // 光源与相机同位，形成“看向哪里亮哪里”的照明效果
        this.headLight.position.copy(camera.position)
        camera.getWorldDirection(this.tempForward)
        // 沿相机前向放置 target，决定方向光照射方向
        this.tempTarget.copy(camera.position).add(this.tempForward.multiplyScalar(300))
        this.headLightTarget.position.copy(this.tempTarget)
        // target 位置变化后需要刷新矩阵，确保本帧方向生效
        this.headLightTarget.updateMatrixWorld()
    }
}
