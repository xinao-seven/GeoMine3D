import {
    Cartesian2,
    Cartesian3,
    Cartographic,
    Color,
    EllipsoidGeodesic,
    EllipsoidTangentPlane,
    Entity,
    LabelStyle,
    ScreenSpaceEventHandler,
    ScreenSpaceEventType,
    Viewer,
} from 'cesium'
import { DEFAULT_MEASURE_LABEL_FONT } from '../constants'

export type MeasureMode = 'distance' | 'area'

export interface MeasureResult {
    id: string
    mode: MeasureMode
    positions: Cartesian3[]
    distanceMeters?: number
    areaSquareMeters?: number
}

export class MeasureTool {
    private readonly viewer: Viewer
    private readonly handler: ScreenSpaceEventHandler

    private mode: MeasureMode | null = null
    private points: Cartesian3[] = []
    private tempEntities: Entity[] = []
    private results: MeasureResult[] = []

    private onComplete?: (result: MeasureResult) => void

    /**
     * 创建空间测量工具。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
        this.handler = new ScreenSpaceEventHandler(viewer.scene.canvas)
    }

    /**
     * 启动距离测量模式。
     */
    startDistance(onComplete?: (result: MeasureResult) => void) {
        this.start('distance', onComplete)
    }

    /**
     * 启动面积测量模式。
     */
    startArea(onComplete?: (result: MeasureResult) => void) {
        this.start('area', onComplete)
    }

    /**
     * 停止当前测量交互。
     */
    stop() {
        this.mode = null
        this.points = []
        this.onComplete = undefined
        this.handler.removeInputAction(ScreenSpaceEventType.LEFT_CLICK)
        this.handler.removeInputAction(ScreenSpaceEventType.RIGHT_CLICK)
        this.handler.removeInputAction(ScreenSpaceEventType.MOUSE_MOVE)
    }

    /**
     * 清空测量产生的临时图元和结果。
     */
    clear() {
        for (const entity of this.tempEntities) {
            this.viewer.entities.remove(entity)
        }
        this.tempEntities = []
        this.results = []
        this.points = []
    }

    /**
     * 获取测量结果快照。
     */
    getResults() {
        return [...this.results]
    }

    /**
     * 销毁测量工具并释放事件资源。
     */
    destroy() {
        this.stop()
        this.clear()
        this.handler.destroy()
    }

    /**
     * 启动指定测量模式并注册鼠标交互。
     */
    private start(mode: MeasureMode, onComplete?: (result: MeasureResult) => void) {
        this.stop()
        this.mode = mode
        this.onComplete = onComplete

        this.handler.setInputAction((event: { position: Cartesian2 }) => {
            this.onLeftClick(event.position)
        }, ScreenSpaceEventType.LEFT_CLICK)

        this.handler.setInputAction(() => {
            this.onRightClick()
        }, ScreenSpaceEventType.RIGHT_CLICK)
    }

    /**
     * 处理左键采点逻辑。
     */
    private onLeftClick(windowPosition: Cartesian2) {
        if (!this.mode) {
            return
        }

        const point = this.pickPosition(windowPosition)
        if (!point) {
            return
        }

        this.points.push(point)
        this.addPointMarker(point)

        if (this.mode === 'distance' && this.points.length === 2) {
            this.finishDistance()
        }
    }

    /**
     * 处理右键结束面积测量逻辑。
     */
    private onRightClick() {
        if (this.mode !== 'area') {
            return
        }

        if (this.points.length < 3) {
            return
        }

        this.finishArea()
    }

    /**
     * 完成距离测量并生成结果图元。
     */
    private finishDistance() {
        const [start, end] = this.points
        const distanceMeters = this.computeDistance([start, end])

        const line = this.viewer.entities.add({
            polyline: {
                positions: [start, end],
                width: 2,
                material: Color.fromCssColorString('#00c8ff'),
            },
        })

        const labelPosition = Cartesian3.midpoint(start, end, new Cartesian3())
        const label = this.createLabel(labelPosition, `${distanceMeters.toFixed(2)} m`)

        this.tempEntities.push(line, label)

        const result: MeasureResult = {
            id: `measure_distance_${Date.now()}`,
            mode: 'distance',
            positions: [start, end],
            distanceMeters,
        }

        this.results.push(result)
        this.onComplete?.(result)
        this.stop()
    }

    /**
     * 完成面积测量并生成结果图元。
     */
    private finishArea() {
        const areaSquareMeters = this.computeArea(this.points)

        const polygon = this.viewer.entities.add({
            polygon: {
                hierarchy: this.points,
                material: Color.fromCssColorString('#00c8ff').withAlpha(0.18),
                outline: true,
                outlineColor: Color.fromCssColorString('#00c8ff'),
            },
        })

        const labelPosition = this.computeCenter(this.points)
        const label = this.createLabel(labelPosition, `${areaSquareMeters.toFixed(2)} m²`)

        this.tempEntities.push(polygon, label)

        const result: MeasureResult = {
            id: `measure_area_${Date.now()}`,
            mode: 'area',
            positions: [...this.points],
            areaSquareMeters,
        }

        this.results.push(result)
        this.onComplete?.(result)
        this.stop()
    }

    /**
     * 添加测量点标记。
     */
    private addPointMarker(position: Cartesian3) {
        const marker = this.viewer.entities.add({
            position,
            point: {
                pixelSize: 7,
                color: Color.fromCssColorString('#ffb020'),
                outlineColor: Color.WHITE,
                outlineWidth: 1,
            },
        })
        this.tempEntities.push(marker)
    }

    /**
     * 创建结果文本标签。
     */
    private createLabel(position: Cartesian3, text: string) {
        return this.viewer.entities.add({
            position,
            label: {
                text,
                font: DEFAULT_MEASURE_LABEL_FONT,
                showBackground: true,
                backgroundColor: Color.fromCssColorString('#0a1628').withAlpha(0.75),
                fillColor: Color.fromCssColorString('#e8f4ff'),
                outlineColor: Color.BLACK,
                outlineWidth: 1,
                style: LabelStyle.FILL_AND_OUTLINE,
                pixelOffset: new Cartesian2(0, -12),
            },
        })
    }

    /**
     * 根据屏幕坐标拾取地表或模型坐标。
     */
    private pickPosition(windowPosition: Cartesian2): Cartesian3 | null {
        const scene = this.viewer.scene

        if (scene.pickPositionSupported) {
            const position = scene.pickPosition(windowPosition)
            if (position) {
                return position
            }
        }

        return this.viewer.camera.pickEllipsoid(windowPosition, scene.globe.ellipsoid) ?? null
    }

    /**
     * 计算折线总距离，包含高差修正。
     */
    private computeDistance(positions: Cartesian3[]) {
        let totalDistance = 0

        for (let index = 1; index < positions.length; index += 1) {
            const previous = Cartographic.fromCartesian(positions[index - 1])
            const current = Cartographic.fromCartesian(positions[index])

            const geodesic = new EllipsoidGeodesic(previous, current)
            const surfaceDistance = geodesic.surfaceDistance
            const heightDelta = current.height - previous.height
            totalDistance += Math.sqrt(surfaceDistance * surfaceDistance + heightDelta * heightDelta)
        }

        return totalDistance
    }

    /**
     * 通过切平面投影计算多边形面积。
     */
    private computeArea(positions: Cartesian3[]) {
        const tangentPlane = new EllipsoidTangentPlane(positions[0])
        const projected = tangentPlane.projectPointsOntoPlane(positions)

        if (!projected || projected.length < 3) {
            return 0
        }

        let area = 0
        for (let index = 0; index < projected.length; index += 1) {
            const current = projected[index]
            const next = projected[(index + 1) % projected.length]
            area += current.x * next.y - next.x * current.y
        }

        return Math.abs(area) * 0.5
    }

    /**
     * 计算点集几何中心。
     */
    private computeCenter(positions: Cartesian3[]) {
        const sum = positions.reduce((acc, point) => Cartesian3.add(acc, point, acc), new Cartesian3())
        return Cartesian3.multiplyByScalar(sum, 1 / positions.length, new Cartesian3())
    }
}
