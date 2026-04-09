import { Color, DataSource, Entity, ImageryLayer, Viewer } from 'cesium'

export class LayerManager {
    private readonly viewer: Viewer

    /**
     * 创建图层管理器。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    /**
     * 设置数据源可见性。
     */
    setDataSourceVisible(target: string | DataSource, visible: boolean) {
        const dataSources = typeof target === 'string' ? this.viewer.dataSources.getByName(target) : [target]
        for (const dataSource of dataSources) {
            dataSource.show = visible
        }
    }

    /**
     * 按条件切换实体可见性。
     */
    setEntityVisible(predicate: (entity: Entity) => boolean, visible: boolean) {
        for (const entity of this.viewer.entities.values) {
            if (predicate(entity)) {
                entity.show = visible
            }
        }
    }

    /**
     * 按条件统一调整实体透明度。
     */
    setEntityOpacity(predicate: (entity: Entity) => boolean, opacity: number) {
        const value = Math.max(0, Math.min(1, opacity))

        for (const entity of this.viewer.entities.values) {
            if (!predicate(entity)) {
                continue
            }

            if (entity.point && entity.point.color) {
                const color = entity.point.color.getValue() as Color | undefined
                if (color) {
                    const point = entity.point as any
                    point.color = color.withAlpha(value)
                }
            }

            if (entity.polyline && entity.polyline.material) {
                const material = entity.polyline.material.getValue() as Color | undefined
                if (material) {
                    const polyline = entity.polyline as any
                    polyline.material = material.withAlpha(value)
                }
            }

            if (entity.polygon && entity.polygon.material) {
                const material = entity.polygon.material.getValue() as Color | undefined
                if (material) {
                    const polygon = entity.polygon as any
                    polygon.material = material.withAlpha(value)
                }
            }

            if (entity.label && entity.label.fillColor) {
                const fillColor = entity.label.fillColor.getValue() as Color | undefined
                if (fillColor) {
                    const label = entity.label as any
                    label.fillColor = fillColor.withAlpha(value)
                }
            }

            if (entity.billboard && entity.billboard.color) {
                const color = entity.billboard.color.getValue() as Color | undefined
                if (color) {
                    const billboard = entity.billboard as any
                    billboard.color = color.withAlpha(value)
                }
            }
        }
    }

    /**
     * 设置影像图层可见性。
     */
    setImageryLayerVisible(layer: ImageryLayer, visible: boolean) {
        layer.show = visible
    }

    /**
     * 设置影像图层透明度。
     */
    setImageryLayerOpacity(layer: ImageryLayer, opacity: number) {
        layer.alpha = Math.max(0, Math.min(1, opacity))
    }

    /**
     * 设置 Primitive 可见性。
     */
    setPrimitiveVisible(primitive: { show?: boolean }, visible: boolean) {
        primitive.show = visible
    }
}
