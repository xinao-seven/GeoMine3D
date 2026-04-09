import {
    Cartesian2,
    Cartesian3,
    ScreenSpaceEventHandler,
    ScreenSpaceEventType,
    Viewer,
    defined,
} from 'cesium'

export type ScreenSpaceCallback<T = any> = (event: T) => void

export class InteractionManager {
    private readonly viewer: Viewer
    private readonly handler: ScreenSpaceEventHandler

    constructor(viewer: Viewer) {
        this.viewer = viewer
        this.handler = new ScreenSpaceEventHandler(viewer.scene.canvas)
    }

    setInputAction(callback: ScreenSpaceCallback, type: ScreenSpaceEventType) {
        this.handler.setInputAction(callback, type)
    }

    removeInputAction(type: ScreenSpaceEventType) {
        this.handler.removeInputAction(type)
    }

    onLeftClick(callback: ScreenSpaceCallback<{ position: Cartesian2 }>) {
        this.handler.setInputAction(callback, ScreenSpaceEventType.LEFT_CLICK)
    }

    onRightClick(callback: ScreenSpaceCallback<{ position: Cartesian2 }>) {
        this.handler.setInputAction(callback, ScreenSpaceEventType.RIGHT_CLICK)
    }

    onMouseMove(callback: ScreenSpaceCallback<{ endPosition: Cartesian2 }>) {
        this.handler.setInputAction(callback, ScreenSpaceEventType.MOUSE_MOVE)
    }

    pickCartesian(windowPosition: Cartesian2): Cartesian3 | null {
        const scene = this.viewer.scene

        if (scene.pickPositionSupported) {
            const picked = scene.pickPosition(windowPosition)
            if (defined(picked)) {
                return picked
            }
        }

        return this.viewer.camera.pickEllipsoid(windowPosition, scene.globe.ellipsoid) ?? null
    }

    pickObject(windowPosition: Cartesian2) {
        return this.viewer.scene.pick(windowPosition)
    }

    setCameraControllerEnabled(enabled: boolean) {
        const controller = this.viewer.scene.screenSpaceCameraController
        controller.enableRotate = enabled
        controller.enableTranslate = enabled
        controller.enableZoom = enabled
        controller.enableTilt = enabled
        controller.enableLook = enabled
    }

    destroy() {
        this.handler.destroy()
    }
}
