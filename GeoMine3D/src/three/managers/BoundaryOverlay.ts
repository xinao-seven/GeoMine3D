import * as THREE from 'three'
import type { BoundariesPayload } from '@/api/workspace'

/**
 * 矿区边界/工作面范围贴地线框。
 *
 * shp 折线为投影坐标（米），这里换算为场景坐标并绘制在指定基准高程上：
 * 折线不是闭合面要素，因此用 Line 而不是 LineLoop / 填充面。
 */
export class BoundaryOverlay {
    readonly group = new THREE.Group()
    private resources: Array<THREE.BufferGeometry | THREE.Material> = []

    constructor() {
        this.group.name = 'boundaries'
        this.group.userData.overlayHelper = true
        this.group.visible = false
    }

    /** origin 为项目投影原点；yLevel 为叠加层世界高度（一般取钻孔孔口平均高程）。 */
    build(
        data: BoundariesPayload,
        origin: { x: number; y: number },
        yLevel: number,
    ) {
        this.clear()
        const lift = yLevel + 1
        const kinds = [
            { key: 'mine' as const, color: 0xff8c42, opacity: 0.95 },
            { key: 'workingfaces' as const, color: 0x35d0ba, opacity: 0.65 },
        ]
        for (const kind of kinds) {
            for (const line of data[kind.key] ?? []) {
                const points = (line.points || [])
                    .filter((point: number[]) => point.length >= 2)
                    .map(([gx, gy]: number[]) => new THREE.Vector3(gx - origin.x, lift, -(gy - origin.y)))
                if (points.length < 2) continue
                const geometry = new THREE.BufferGeometry().setFromPoints(points)
                const material = new THREE.LineBasicMaterial({
                    color: kind.color,
                    transparent: true,
                    opacity: kind.opacity,
                })
                const lineObject = new THREE.Line(geometry, material)
                lineObject.userData.overlayHelper = true
                this.group.add(lineObject)
                this.resources.push(geometry, material)
            }
        }
    }

    get count() {
        return this.group.children.length
    }

    setVisible(visible: boolean) {
        this.group.visible = visible
    }

    clear() {
        this.group.clear()
        for (const resource of this.resources) resource.dispose()
        this.resources = []
    }

    dispose() {
        this.clear()
        this.group.parent?.remove(this.group)
    }
}
