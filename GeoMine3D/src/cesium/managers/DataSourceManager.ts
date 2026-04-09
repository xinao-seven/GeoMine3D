import { CzmlDataSource, GeoJsonDataSource, KmlDataSource, Viewer } from 'cesium'

type GeoJsonSource = Parameters<typeof GeoJsonDataSource.load>[0]
type GeoJsonOptions = Parameters<typeof GeoJsonDataSource.load>[1]
type CzmlSource = Parameters<typeof CzmlDataSource.load>[0]
type KmlSource = Parameters<typeof KmlDataSource.load>[0]
type KmlOptions = Parameters<typeof KmlDataSource.load>[1]

export class DataSourceManager {
    private readonly viewer: Viewer

    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    add(dataSource: Parameters<Viewer['dataSources']['add']>[0]) {
        return this.viewer.dataSources.add(dataSource)
    }

    async loadGeoJson(source: GeoJsonSource, options?: GeoJsonOptions) {
        const dataSource = await GeoJsonDataSource.load(source, options)
        this.viewer.dataSources.add(dataSource)
        return dataSource
    }

    async loadCzml(source: CzmlSource) {
        const dataSource = await CzmlDataSource.load(source)
        this.viewer.dataSources.add(dataSource)
        return dataSource
    }

    async loadKml(source: KmlSource, options?: KmlOptions) {
        const dataSource = await KmlDataSource.load(source, options)
        this.viewer.dataSources.add(dataSource)
        return dataSource
    }

    getByName(name: string) {
        return this.viewer.dataSources.getByName(name)
    }

    removeByName(name: string, destroy = true) {
        const list = this.viewer.dataSources.getByName(name)
        for (const item of list) {
            this.viewer.dataSources.remove(item, destroy)
        }
        return list.length
    }

    clear(destroy = true) {
        this.viewer.dataSources.removeAll(destroy)
    }
}
