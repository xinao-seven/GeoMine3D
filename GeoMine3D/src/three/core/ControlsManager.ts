import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'

export class ControlsManager {
    readonly controls: OrbitControls

    constructor(camera: THREE.Camera, domElement: HTMLElement) {
        this.controls = new OrbitControls(camera, domElement)
        // 阻尼让旋转/缩放有惯性，交互手感更自然
        this.controls.enableDamping = true
        // 阻尼系数越大，停止越快；越小，惯性越明显
        this.controls.dampingFactor = 0.05
        // false 表示平移基于世界竖直方向，适合地质场景“地面在下”的直觉
        this.controls.screenSpacePanning = false
        // 缩放最近距离，避免相机穿进模型
        this.controls.minDistance = 10
        // 缩放最远距离，限制用户拉得过远导致模型过小
        this.controls.maxDistance = 200000
        // 俯仰上限略高于水平线，避免翻转到地下造成方向迷失
        this.controls.maxPolarAngle = Math.PI / 2 + 0.1
    }

    update() {
        // 启用阻尼时必须每帧调用
        this.controls.update()
    }

    setDistanceLimits(minDistance: number, maxDistance: number) {
        // 保护性约束: 下限至少为 0.1，上限必须大于下限
        this.controls.minDistance = Math.max(0.1, minDistance)
        this.controls.maxDistance = Math.max(this.controls.minDistance + 1, maxDistance)
    }

    dispose() {
        this.controls.dispose()
    }
}
