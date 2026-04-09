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

    constructor(container: string | HTMLElement, options: Partial<ViewerConstructorOptions> = {}) {
        const mergedOptions = {
            ...DEFAULT_VIEWER_OPTIONS,
            ...options,
        } as ViewerConstructorOptions

        this.viewer = new Viewer(container, mergedOptions)
        this.applyDefaultSceneConfig()
    }

    applyDefaultSceneConfig() {
        const scene = this.viewer.scene
        scene.globe.depthTestAgainstTerrain = DEFAULT_GLOBE_DEPTH_TEST
        scene.globe.enableLighting = DEFAULT_GLOBE_LIGHTING
        scene.fog.enabled = DEFAULT_FOG_ENABLED
    }

    setBackgroundColor(cssColor: string) {
        this.viewer.scene.backgroundColor = Color.fromCssColorString(cssColor)
    }

    setDepthTestAgainstTerrain(enabled: boolean) {
        this.viewer.scene.globe.depthTestAgainstTerrain = enabled
    }

    setGlobeLighting(enabled: boolean) {
        this.viewer.scene.globe.enableLighting = enabled
    }

    setFogEnabled(enabled: boolean) {
        this.viewer.scene.fog.enabled = enabled
    }

    clearData() {
        this.viewer.dataSources.removeAll()
        this.viewer.entities.removeAll()
    }

    resize() {
        this.viewer.resize()
    }

    destroy() {
        if (!this.viewer.isDestroyed()) {
            this.viewer.destroy()
        }
    }
}
