import {
    Cartesian2,
    Cartesian3,
    Color,
    DistanceDisplayCondition,
    Entity,
    HeightReference,
    LabelStyle,
    Viewer,
} from 'cesium'
import { DEFAULT_LABEL_FONT, DEFAULT_PICK_DISTANCE, DEFAULT_POINT_PIXEL_SIZE } from '../constants'
import { degreesToCartesian, degreesArrayToCartesianArray, type DegreePosition } from '../core'

export interface PointEntityOptions {
    id?: string
    name?: string
    position: Cartesian3 | DegreePosition
    pixelSize?: number
    color?: Color
    outlineColor?: Color
    outlineWidth?: number
    labelText?: string
    tag?: string
}

export interface PolylineEntityOptions {
    id?: string
    name?: string
    positions: Cartesian3[] | DegreePosition[]
    width?: number
    color?: Color
    clampToGround?: boolean
    tag?: string
}

export interface PolygonEntityOptions {
    id?: string
    name?: string
    positions: Cartesian3[] | DegreePosition[]
    color?: Color
    outlineColor?: Color
    outlineWidth?: number
    extrudedHeight?: number
    tag?: string
}

export class EntityManager {
    private readonly viewer: Viewer

    /**
     * 创建实体管理器。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    /**
     * 添加点实体，可附带标签。
     */
    addPoint(options: PointEntityOptions): Entity {
        const position = options.position instanceof Cartesian3
            ? options.position
            : degreesToCartesian(options.position)

        const entity = this.viewer.entities.add({
            id: options.id,
            name: options.name,
            position,
            point: {
                pixelSize: options.pixelSize ?? DEFAULT_POINT_PIXEL_SIZE,
                color: options.color ?? Color.fromCssColorString('#00c8ff'),
                outlineColor: options.outlineColor ?? Color.WHITE,
                outlineWidth: options.outlineWidth ?? 1,
                heightReference: HeightReference.NONE,
                disableDepthTestDistance: DEFAULT_PICK_DISTANCE,
            },
            label: options.labelText
                ? {
                    text: options.labelText,
                    font: DEFAULT_LABEL_FONT,
                    showBackground: true,
                    backgroundColor: Color.fromCssColorString('#0a1628').withAlpha(0.68),
                    fillColor: Color.fromCssColorString('#e8f4ff'),
                    outlineColor: Color.BLACK,
                    outlineWidth: 1,
                    style: LabelStyle.FILL_AND_OUTLINE,
                    pixelOffset: new Cartesian2(0, -16),
                    disableDepthTestDistance: DEFAULT_PICK_DISTANCE,
                    distanceDisplayCondition: new DistanceDisplayCondition(0, Number.POSITIVE_INFINITY),
                }
                : undefined,
            properties: {
                tag: options.tag ?? 'default',
            },
        })

        return entity
    }

    /**
     * 添加公告牌实体。
     */
    addBillboard(options: {
        id?: string
        name?: string
        position: Cartesian3 | DegreePosition
        image: string
        scale?: number
        tag?: string
    }): Entity {
        const position = options.position instanceof Cartesian3
            ? options.position
            : degreesToCartesian(options.position)

        return this.viewer.entities.add({
            id: options.id,
            name: options.name,
            position,
            billboard: {
                image: options.image,
                scale: options.scale ?? 1,
            },
            properties: {
                tag: options.tag ?? 'default',
            },
        })
    }

    /**
     * 添加文本标签实体。
     */
    addLabel(options: {
        id?: string
        name?: string
        position: Cartesian3 | DegreePosition
        text: string
        color?: Color
        tag?: string
    }): Entity {
        const position = options.position instanceof Cartesian3
            ? options.position
            : degreesToCartesian(options.position)

        return this.viewer.entities.add({
            id: options.id,
            name: options.name,
            position,
            label: {
                text: options.text,
                font: DEFAULT_LABEL_FONT,
                showBackground: true,
                backgroundColor: Color.fromCssColorString('#0a1628').withAlpha(0.68),
                fillColor: options.color ?? Color.fromCssColorString('#e8f4ff'),
                outlineColor: Color.BLACK,
                outlineWidth: 1,
                style: LabelStyle.FILL_AND_OUTLINE,
            },
            properties: {
                tag: options.tag ?? 'default',
            },
        })
    }

    /**
     * 添加折线实体。
     */
    addPolyline(options: PolylineEntityOptions): Entity {
        const positions = this.normalizePositions(options.positions)
        return this.viewer.entities.add({
            id: options.id,
            name: options.name,
            polyline: {
                positions,
                width: options.width ?? 2,
                material: options.color ?? Color.fromCssColorString('#00c8ff'),
                clampToGround: options.clampToGround ?? false,
            },
            properties: {
                tag: options.tag ?? 'default',
            },
        })
    }

    /**
     * 添加多边形实体。
     */
    addPolygon(options: PolygonEntityOptions): Entity {
        const positions = this.normalizePositions(options.positions)
        return this.viewer.entities.add({
            id: options.id,
            name: options.name,
            polygon: {
                hierarchy: positions,
                material: (options.color ?? Color.fromCssColorString('#00c8ff')).withAlpha(0.2),
                outline: true,
                outlineColor: options.outlineColor ?? Color.fromCssColorString('#00c8ff'),
                outlineWidth: options.outlineWidth ?? 1,
                extrudedHeight: options.extrudedHeight,
            },
            properties: {
                tag: options.tag ?? 'default',
            },
        })
    }

    /**
     * 根据实体 ID 移除对象。
     */
    removeById(id: string) {
        const entity = this.viewer.entities.getById(id)
        if (!entity) {
            return false
        }
        return this.viewer.entities.remove(entity)
    }

    /**
     * 根据业务标签清理实体。
     */
    clearByTag(tag: string) {
        const targets = this.viewer.entities.values.filter((item) => item.properties?.tag?.getValue() === tag)
        for (const entity of targets) {
            this.viewer.entities.remove(entity)
        }
    }

    /**
     * 根据业务标签控制显隐。
     */
    setVisibleByTag(tag: string, visible: boolean) {
        const targets = this.viewer.entities.values.filter((item) => item.properties?.tag?.getValue() === tag)
        for (const entity of targets) {
            entity.show = visible
        }
    }

    /**
     * 统一将输入位置数组归一化为 Cartesian3 数组。
     */
    private normalizePositions(positions: Cartesian3[] | DegreePosition[]) {
        if (positions.length === 0) {
            return []
        }

        if (positions[0] instanceof Cartesian3) {
            return positions as Cartesian3[]
        }

        return degreesArrayToCartesianArray(positions as DegreePosition[])
    }
}
