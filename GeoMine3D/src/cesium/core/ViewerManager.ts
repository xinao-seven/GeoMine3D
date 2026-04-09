import { Color, Viewer } from 'cesium'
import {
    DEFAULT_FOG_ENABLED,
    DEFAULT_GLOBE_DEPTH_TEST,
    DEFAULT_GLOBE_LIGHTING,
    DEFAULT_VIEWER_OPTIONS,
} from '../constants'

type ViewerConstructorOptions = NonNullable<ConstructorParameters<typeof Viewer>[1]>

export class ViewerManager {
    readonly viewer: Viewer

    /**
     * 创建 Viewer 实例并应用默认场景配置。
     */
    constructor(container: string | HTMLElement, options: Partial<ViewerConstructorOptions> = {}) {
        const mergedOptions = {
            ...DEFAULT_VIEWER_OPTIONS,
            ...options,
        } as ViewerConstructorOptions

        this.viewer = new Viewer(container, mergedOptions)
        this.applyDefaultSceneConfig()
    }

    /**
     * 应用地球深度测试、光照和雾效的默认设置。
     */
    applyDefaultSceneConfig() {
        const scene = this.viewer.scene
        scene.globe.depthTestAgainstTerrain = DEFAULT_GLOBE_DEPTH_TEST
        scene.globe.enableLighting = DEFAULT_GLOBE_LIGHTING
        scene.fog.enabled = DEFAULT_FOG_ENABLED
    }

    /**
     * 设置场景背景色。
     */
    setBackgroundColor(cssColor: string) {
        this.viewer.scene.backgroundColor = Color.fromCssColorString(cssColor)
    }

    /**
     * 控制地形深度测试开关。
     */
    setDepthTestAgainstTerrain(enabled: boolean) {
        this.viewer.scene.globe.depthTestAgainstTerrain = enabled
    }

    /**
     * 控制地球光照开关。
     */
    setGlobeLighting(enabled: boolean) {
        this.viewer.scene.globe.enableLighting = enabled
    }

    /**
     * 控制场景雾效开关。
     */
    setFogEnabled(enabled: boolean) {
        this.viewer.scene.fog.enabled = enabled
    }

    /**
     * 清空当前场景中的数据源与实体。
     */
    clearData() {
        this.viewer.dataSources.removeAll()
        this.viewer.entities.removeAll()
    }

    /**
     * 通知 Viewer 重新计算尺寸。
     */
    resize() {
        this.viewer.resize()
    }

    /**
     * 销毁 Viewer，释放底层资源。
     */
    destroy() {
        if (!this.viewer.isDestroyed()) {
            this.viewer.destroy()
        }
    }
}
