import * as THREE from 'three'
import type { ContoursResponse } from '@/api/workspace'

/** 埋深等值线配色：浅埋（蓝）→ 深埋（红） */
export function contourColor(normalized: number): THREE.Color {
    const hue = 0.62 * (1 - Math.min(1, Math.max(0, normalized)))
    return new THREE.Color().setHSL(hue, 0.72, 0.52)
}

/**
 * 地层顶板埋深等值线叠加层。
 * 后端返回投影坐标线段（[ax,ay,bx,by,...]），这里换算为场景坐标
 * 绘制在基准高程上方，每个等级一条 LineSegments。
 */
export class ContourOverlay {
    readonly group = new THREE.Group()
    private resources: Array<THREE.BufferGeometry | THREE.Material> = []
    minLevel = 0
    maxLevel = 0

    constructor() {
        this.group.name = 'contours'
        this.group.userData.overlayHelper = true
        this.group.visible = false
    }

    build(data: ContoursResponse, origin: { x: number; y: number }, yLevel: number) {
        this.clear()
        const levels = data.levels ?? []
        this.minLevel = levels.length ? levels[0] : 0
        this.maxLevel = levels.length ? levels[levels.length - 1] : 1
        const span = Math.max(this.maxLevel - this.minLevel, 1e-6)
        const lift = yLevel + 3

        for (const line of data.lines ?? []) {
            const normalized = (line.level - this.minLevel) / span
            const positions = new Float32Array((line.segments.length / 4) * 6)
            let offset = 0
            for (let i = 0; i + 3 < line.segments.length; i += 4) {
                const ax = line.segments[i] - origin.x
                const ay = line.segments[i + 1] - origin.y
                const bx = line.segments[i + 2] - origin.x
                const by = line.segments[i + 3] - origin.y
                positions[offset] = ax
                positions[offset + 1] = lift
                positions[offset + 2] = -ay
                positions[offset + 3] = bx
                positions[offset + 4] = lift
                positions[offset + 5] = -by
                offset += 6
            }
            const geometry = new THREE.BufferGeometry()
            geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
            const material = new THREE.LineBasicMaterial({
                color: contourColor(normalized),
                transparent: true,
                opacity: 0.85,
            })
            const object = new THREE.LineSegments(geometry, material)
            object.userData.overlayHelper = true
            this.group.add(object)
            this.resources.push(geometry, material)
        }
    }

    get levelCount() {
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
