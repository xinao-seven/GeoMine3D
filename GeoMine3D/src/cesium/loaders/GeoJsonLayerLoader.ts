import { Color, GeoJsonDataSource, Viewer } from 'cesium'

type GeoJsonSource = Parameters<typeof GeoJsonDataSource.load>[0]
type GeoJsonOptions = Parameters<typeof GeoJsonDataSource.load>[1]

export interface GeoJsonStyle {
    strokeColor?: Color
    strokeWidth?: number
    fillColor?: Color
    fillAlpha?: number
}

export class GeoJsonLayerLoader {
    private readonly viewer: Viewer

    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    async load(
        source: GeoJsonSource,
        name?: string,
        options?: GeoJsonOptions,
        style: GeoJsonStyle = {},
    ): Promise<GeoJsonDataSource> {
        const dataSource = await GeoJsonDataSource.load(source, options)
        if (name) {
            dataSource.name = name
        }

        this.applyStyle(dataSource, style)
        this.viewer.dataSources.add(dataSource)
        return dataSource
    }

    applyStyle(dataSource: GeoJsonDataSource, style: GeoJsonStyle = {}) {
        const {
            strokeColor = Color.fromCssColorString('#00c8ff'),
            strokeWidth = 2,
            fillColor = Color.fromCssColorString('#00c8ff'),
            fillAlpha = 0.15,
        } = style

        const entities = dataSource.entities.values
        for (const entity of entities) {
            if (entity.polyline) {
                const polyline = entity.polyline as any
                polyline.material = strokeColor
                polyline.width = strokeWidth
            }
            if (entity.polygon) {
                const polygon = entity.polygon as any
                polygon.material = fillColor.withAlpha(fillAlpha)
                polygon.outline = true
                polygon.outlineColor = strokeColor
            }
        }
    }

    findByName(name: string): GeoJsonDataSource | undefined {
        return this.viewer.dataSources.getByName(name)[0] as GeoJsonDataSource | undefined
    }

    removeByName(name: string, destroy = true): boolean {
        const dataSource = this.findByName(name)
        if (!dataSource) {
            return false
        }
        return this.viewer.dataSources.remove(dataSource, destroy)
    }
}
