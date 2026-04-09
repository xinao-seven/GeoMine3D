import { BoundingSphere, Cartesian3, HeadingPitchRange, Math as CesiumMath, Matrix4, Rectangle, Viewer } from 'cesium'
import {
    DEFAULT_CAMERA_FLY_DURATION,
    DEFAULT_CAMERA_HEADING,
    DEFAULT_CAMERA_PITCH,
    DEFAULT_CAMERA_ROLL,
} from '../constants'

export interface CameraDegreePosition {
    lon: number
    lat: number
    height?: number
}

export class CameraManager {
    private readonly viewer: Viewer

    /**
     * 使用现有 Viewer 构建相机管理器。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    /**
     * 飞行到实体、数据源或图层等目标对象。
     */
    flyTo(target: Parameters<Viewer['flyTo']>[0], options?: Parameters<Viewer['flyTo']>[1]) {
        return this.viewer.flyTo(target, options)
    }

    /**
     * 缩放并定位到指定目标。
     */
    zoomTo(target: Parameters<Viewer['zoomTo']>[0], offset?: Parameters<Viewer['zoomTo']>[1]) {
        return this.viewer.zoomTo(target, offset)
    }

    /**
     * 按经纬度飞行到指定位置。
     */
    flyToDegrees(position: CameraDegreePosition, duration = DEFAULT_CAMERA_FLY_DURATION) {
        const { lon, lat, height = 2000 } = position
        return this.viewer.camera.flyTo({
            destination: Cartesian3.fromDegrees(lon, lat, height),
            orientation: {
                heading: DEFAULT_CAMERA_HEADING,
                pitch: DEFAULT_CAMERA_PITCH,
                roll: DEFAULT_CAMERA_ROLL,
            },
            duration,
        })
    }

    /**
     * 直接设置相机视角到经纬度位置。
     */
    setViewDegrees(position: CameraDegreePosition, headingDeg = 0, pitchDeg = -35, rollDeg = 0) {
        const { lon, lat, height = 2000 } = position
        this.viewer.camera.setView({
            destination: Cartesian3.fromDegrees(lon, lat, height),
            orientation: {
                heading: CesiumMath.toRadians(headingDeg),
                pitch: CesiumMath.toRadians(pitchDeg),
                roll: CesiumMath.toRadians(rollDeg),
            },
        })
    }

    /**
     * 飞行到矩形范围。
     */
    flyToRectangle(rectangle: Rectangle, duration = DEFAULT_CAMERA_FLY_DURATION) {
        return this.viewer.camera.flyTo({
            destination: rectangle,
            duration,
        })
    }

    /**
     * 飞行到包围球范围，可附带观察偏移。
     */
    flyToBoundingSphere(sphere: BoundingSphere, offset?: HeadingPitchRange, duration = DEFAULT_CAMERA_FLY_DURATION) {
        this.viewer.camera.flyToBoundingSphere(sphere, {
            offset,
            duration,
        })
    }

    /**
     * 以经纬度目标为中心设置 lookAt 观察。
     */
    lookAtDegrees(target: CameraDegreePosition, range = 2500, headingDeg = 0, pitchDeg = -35) {
        const targetCartesian = Cartesian3.fromDegrees(target.lon, target.lat, target.height ?? 0)
        this.viewer.camera.lookAt(
            targetCartesian,
            new HeadingPitchRange(CesiumMath.toRadians(headingDeg), CesiumMath.toRadians(pitchDeg), range),
        )
    }

    /**
     * 清除 lookAt 状态，恢复默认变换。
     */
    clearLookAt() {
        this.viewer.camera.lookAtTransform(Matrix4.IDENTITY)
    }

    /**
     * 根据目标半径动态调整相机裁剪面。
     */
    tuneFrustumByRadius(radius: number) {
        const frustum = this.viewer.camera.frustum as { near?: number; far?: number }
        if (typeof frustum.near !== 'number' || typeof frustum.far !== 'number') {
            return
        }

        const safeRadius = Math.max(1, radius)
        frustum.near = Math.max(0.5, safeRadius / 4000)
        frustum.far = Math.max(2_000_000, safeRadius * 120)
    }
}
