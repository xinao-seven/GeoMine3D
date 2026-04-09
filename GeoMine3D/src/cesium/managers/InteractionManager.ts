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

    /**
     * 创建屏幕交互管理器。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
        this.handler = new ScreenSpaceEventHandler(viewer.scene.canvas)
    }

    /**
     * 注册原生屏幕事件回调。
     */
    setInputAction(callback: ScreenSpaceCallback, type: ScreenSpaceEventType) {
        this.handler.setInputAction(callback, type)
    }

    /**
     * 移除指定类型的屏幕事件回调。
     */
    removeInputAction(type: ScreenSpaceEventType) {
        this.handler.removeInputAction(type)
    }

    /**
     * 注册左键点击事件。
     */
    onLeftClick(callback: ScreenSpaceCallback<{ position: Cartesian2 }>) {
        this.handler.setInputAction(callback, ScreenSpaceEventType.LEFT_CLICK)
    }

    /**
     * 注册右键点击事件。
     */
    onRightClick(callback: ScreenSpaceCallback<{ position: Cartesian2 }>) {
        this.handler.setInputAction(callback, ScreenSpaceEventType.RIGHT_CLICK)
    }

    /**
     * 注册鼠标移动事件。
     */
    onMouseMove(callback: ScreenSpaceCallback<{ endPosition: Cartesian2 }>) {
        this.handler.setInputAction(callback, ScreenSpaceEventType.MOUSE_MOVE)
    }

    /**
     * 根据屏幕坐标拾取三维位置。
     */
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

    /**
     * 根据屏幕坐标拾取场景对象。
     */
    pickObject(windowPosition: Cartesian2) {
        return this.viewer.scene.pick(windowPosition)
    }

    /**
     * 统一启停相机交互控制。
     */
    setCameraControllerEnabled(enabled: boolean) {
        const controller = this.viewer.scene.screenSpaceCameraController
        controller.enableRotate = enabled
        controller.enableTranslate = enabled
        controller.enableZoom = enabled
        controller.enableTilt = enabled
        controller.enableLook = enabled
    }

    /**
     * 销毁交互处理器。
     */
    destroy() {
        this.handler.destroy()
    }
}
