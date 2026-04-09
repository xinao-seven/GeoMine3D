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

    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    flyTo(target: Parameters<Viewer['flyTo']>[0], options?: Parameters<Viewer['flyTo']>[1]) {
        return this.viewer.flyTo(target, options)
    }

    zoomTo(target: Parameters<Viewer['zoomTo']>[0], offset?: Parameters<Viewer['zoomTo']>[1]) {
        return this.viewer.zoomTo(target, offset)
    }

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

    flyToRectangle(rectangle: Rectangle, duration = DEFAULT_CAMERA_FLY_DURATION) {
        return this.viewer.camera.flyTo({
            destination: rectangle,
            duration,
        })
    }

    flyToBoundingSphere(sphere: BoundingSphere, offset?: HeadingPitchRange, duration = DEFAULT_CAMERA_FLY_DURATION) {
        this.viewer.camera.flyToBoundingSphere(sphere, {
            offset,
            duration,
        })
    }

    lookAtDegrees(target: CameraDegreePosition, range = 2500, headingDeg = 0, pitchDeg = -35) {
        const targetCartesian = Cartesian3.fromDegrees(target.lon, target.lat, target.height ?? 0)
        this.viewer.camera.lookAt(
            targetCartesian,
            new HeadingPitchRange(CesiumMath.toRadians(headingDeg), CesiumMath.toRadians(pitchDeg), range),
        )
    }

    clearLookAt() {
        this.viewer.camera.lookAtTransform(Matrix4.IDENTITY)
    }

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
