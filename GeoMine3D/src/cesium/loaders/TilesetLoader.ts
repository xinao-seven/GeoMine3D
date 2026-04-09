import { Cartesian3, Cartographic, Cesium3DTileset, Matrix4, Viewer } from 'cesium'

type TilesetOptions = Parameters<typeof Cesium3DTileset.fromUrl>[1]

export class TilesetLoader {
    private readonly viewer: Viewer

    /**
     * 创建 3D Tiles 加载器。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    /**
     * 从 URL 加载 3D Tiles，并可选择直接加入场景。
     */
    async loadFromUrl(url: string, options: TilesetOptions = {}, addToScene = true): Promise<Cesium3DTileset> {
        const tileset = await Cesium3DTileset.fromUrl(url, options)
        if (addToScene) {
            this.viewer.scene.primitives.add(tileset)
        }
        return tileset
    }

    /**
     * 相机飞行至指定 Tileset。
     */
    async flyTo(tileset: Cesium3DTileset, duration = 1.6) {
        return this.viewer.flyTo(tileset, { duration })
    }

    /**
     * 为 Tileset 应用高度偏移。
     */
    setHeightOffset(tileset: Cesium3DTileset, heightOffset = 0) {
        const cartographic = Cartographic.fromCartesian(tileset.boundingSphere.center)
        const surface = Cartesian3.fromRadians(cartographic.longitude, cartographic.latitude, 0)
        const offset = Cartesian3.fromRadians(cartographic.longitude, cartographic.latitude, heightOffset)
        const translation = Cartesian3.subtract(offset, surface, new Cartesian3())
        tileset.modelMatrix = Matrix4.fromTranslation(translation)
    }

    /**
     * 从场景移除 Tileset。
     */
    remove(tileset: Cesium3DTileset, destroy = true) {
        return this.viewer.scene.primitives.remove(tileset)
    }
}
