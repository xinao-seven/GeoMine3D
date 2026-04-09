import { CzmlDataSource, GeoJsonDataSource, KmlDataSource, Viewer } from 'cesium'

type GeoJsonSource = Parameters<typeof GeoJsonDataSource.load>[0]
type GeoJsonOptions = Parameters<typeof GeoJsonDataSource.load>[1]
type CzmlSource = Parameters<typeof CzmlDataSource.load>[0]
type KmlSource = Parameters<typeof KmlDataSource.load>[0]
type KmlOptions = Parameters<typeof KmlDataSource.load>[1]

export class DataSourceManager {
    private readonly viewer: Viewer

    /**
     * 创建数据源管理器。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    /**
     * 将数据源添加到 Viewer。
     */
    add(dataSource: Parameters<Viewer['dataSources']['add']>[0]) {
        return this.viewer.dataSources.add(dataSource)
    }

    /**
     * 加载并添加 GeoJSON 数据源。
     */
    async loadGeoJson(source: GeoJsonSource, options?: GeoJsonOptions) {
        const dataSource = await GeoJsonDataSource.load(source, options)
        this.viewer.dataSources.add(dataSource)
        return dataSource
    }

    /**
     * 加载并添加 CZML 数据源。
     */
    async loadCzml(source: CzmlSource) {
        const dataSource = await CzmlDataSource.load(source)
        this.viewer.dataSources.add(dataSource)
        return dataSource
    }

    /**
     * 加载并添加 KML 数据源。
     */
    async loadKml(source: KmlSource, options?: KmlOptions) {
        const dataSource = await KmlDataSource.load(source, options)
        this.viewer.dataSources.add(dataSource)
        return dataSource
    }

    /**
     * 根据名称获取数据源列表。
     */
    getByName(name: string) {
        return this.viewer.dataSources.getByName(name)
    }

    /**
     * 根据名称移除匹配的数据源。
     */
    removeByName(name: string, destroy = true) {
        const list = this.viewer.dataSources.getByName(name)
        for (const item of list) {
            this.viewer.dataSources.remove(item, destroy)
        }
        return list.length
    }

    /**
     * 清空全部数据源。
     */
    clear(destroy = true) {
        this.viewer.dataSources.removeAll(destroy)
    }
}
