import {
    ImageryLayer,
    Rectangle,
    SingleTileImageryProvider,
    TileMapServiceImageryProvider,
    UrlTemplateImageryProvider,
    Viewer,
} from 'cesium'

type SingleTileOptions = Parameters<typeof SingleTileImageryProvider.fromUrl>[1]
type TmsOptions = Parameters<typeof TileMapServiceImageryProvider.fromUrl>[1]

export interface DegreeRectangle {
    west: number
    south: number
    east: number
    north: number
}

export interface UrlTemplateOptions {
    minimumLevel?: number
    maximumLevel?: number
    subdomains?: string[]
}

export class ImageryLayerLoader {
    private readonly viewer: Viewer

    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    static fromDegreeRectangle(bounds: DegreeRectangle): Rectangle {
        return Rectangle.fromDegrees(bounds.west, bounds.south, bounds.east, bounds.north)
    }

    async addSingleTile(
        imageUrl: string,
        bounds?: DegreeRectangle,
        options: SingleTileOptions = {},
        alpha = 1,
    ): Promise<ImageryLayer> {
        const rectangle = bounds ? ImageryLayerLoader.fromDegreeRectangle(bounds) : undefined
        const provider = await SingleTileImageryProvider.fromUrl(imageUrl, {
            ...options,
            rectangle,
        })

        const layer = this.viewer.imageryLayers.addImageryProvider(provider)
        layer.alpha = alpha
        return layer
    }

    addUrlTemplate(url: string, options: UrlTemplateOptions = {}, alpha = 1): ImageryLayer {
        const provider = new UrlTemplateImageryProvider({
            url,
            minimumLevel: options.minimumLevel,
            maximumLevel: options.maximumLevel,
            subdomains: options.subdomains,
        })
        const layer = this.viewer.imageryLayers.addImageryProvider(provider)
        layer.alpha = alpha
        return layer
    }

    async addTileMapService(
        baseUrl: string,
        options: TmsOptions = {},
        alpha = 1,
    ): Promise<ImageryLayer> {
        const provider = await TileMapServiceImageryProvider.fromUrl(baseUrl, options)
        const layer = this.viewer.imageryLayers.addImageryProvider(provider)
        layer.alpha = alpha
        return layer
    }

    remove(layer: ImageryLayer, destroy = true) {
        return this.viewer.imageryLayers.remove(layer, destroy)
    }

    removeAll(destroy = true) {
        this.viewer.imageryLayers.removeAll(destroy)
    }
}
