import * as THREE from 'three'
import type { ModelManager } from '../managers/ModelManager'

interface AxisLabel {
    sprite: THREE.Sprite
    aspect: number
}

export interface SceneCoordinateOrigin {
    x: number
    y: number
    z: number
    verticalScale: number
}

// 场景局部坐标 -> 原始投影坐标的取值函数（旋转X开启时：world.x=东向偏移, world.y=夸张高程偏移, world.z=-北向偏移）
export type CoordinateOriginGetter = () => SceneCoordinateOrigin | null

export class BoundingBoxTool {
    private static readonly TARGET_PX_HEIGHT = 34
    private static readonly MIN_HEIGHT = 18
    private static readonly MAX_HEIGHT = 480
    private static readonly TICK_COUNT = 5

    private scene: THREE.Scene
    private modelManager: ModelManager
    private camera: THREE.Camera
    private domElement: HTMLElement
    private getOrigin: CoordinateOriginGetter | null
    private group: THREE.Group
    private enabled = false
    private resources: Array<THREE.Material | THREE.Texture | THREE.BufferGeometry> = []
    private labels: AxisLabel[] = []

    constructor(
        scene: THREE.Scene,
        modelManager: ModelManager,
        camera: THREE.Camera,
        domElement: HTMLElement,
        getOrigin?: CoordinateOriginGetter,
    ) {
        this.scene = scene
        this.modelManager = modelManager
        this.camera = camera
        this.domElement = domElement
        this.getOrigin = getOrigin ?? null
        this.group = new THREE.Group()
        this.group.name = 'boundingBox'
        this.group.visible = false
        this.scene.add(this.group)
    }

    enable() {
        if (this.enabled) return
        this.enabled = true
        this.rebuild()
    }

    disable() {
        if (!this.enabled) return
        this.enabled = false
        this.group.visible = false
    }

    toggle() {
        this.enabled ? this.disable() : this.enable()
        return this.enabled
    }

    // 项目原点变化后重建刻度，让标签换算到新的原始坐标。
    refresh() {
        if (this.enabled) this.rebuild()
    }

    isEnabled() {
        return this.enabled
    }

    update() {
        if (!this.enabled || !this.labels.length) return
        for (const item of this.labels) {
            this.scaleSprite(item)
        }
    }

    dispose() {
        this.disable()
        this.group.clear()
        for (const res of this.resources) res.dispose()
        this.resources = []
        this.labels = []
        this.scene.remove(this.group)
    }

    private rebuild() {
        this.group.clear()
        for (const res of this.resources) res.dispose()
        this.resources = []
        this.labels = []

        const models = this.modelManager.getAllModels()
        if (models.length === 0) return

        const box = new THREE.Box3()
        models.forEach((m) => box.expandByObject(m.object))
        if (box.isEmpty()) return

        const size = box.getSize(new THREE.Vector3())
        const center = box.getCenter(new THREE.Vector3())
        const { min, max } = box

        // 白色线框包围盒
        const boxGeo = new THREE.BoxGeometry(size.x, size.y, size.z)
        const edgesGeo = new THREE.EdgesGeometry(boxGeo)
        const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff })
        const wireframe = new THREE.LineSegments(edgesGeo, lineMat)
        wireframe.position.copy(center)
        wireframe.userData.boundingBoxHelper = true
        this.group.add(wireframe)
        this.resources.push(lineMat, boxGeo, edgesGeo)

        // 三条边，汇交于 min 角点
        const origin = new THREE.Vector3(min.x, min.y, min.z)

        // 每条边向外偏移的方向（垂直于该边，指向盒外）
        const xEdgeOff = new THREE.Vector3(0, min.y - center.y, min.z - center.z).normalize()
        const yEdgeOff = new THREE.Vector3(min.x - center.x, 0, min.z - center.z).normalize()
        const zEdgeOff = new THREE.Vector3(min.x - center.x, min.y - center.y, 0).normalize()

        const tickLen = Math.max(size.x, size.y, size.z) * 0.018 + 14
        const spriteGap = tickLen + 8

        interface EdgeConfig {
            end: THREE.Vector3
            off: THREE.Vector3
            axis: string
            divisor: number
        }

        const edges: EdgeConfig[] = [
            { end: new THREE.Vector3(max.x, min.y, min.z), off: xEdgeOff, axis: 'X', divisor: 1 },
            { end: new THREE.Vector3(min.x, max.y, min.z), off: yEdgeOff, axis: 'Y', divisor: 1 },
            { end: new THREE.Vector3(min.x, min.y, max.z), off: zEdgeOff, axis: 'Z', divisor: 20 },
        ]

        // 为每个轴坐标分量建立提取函数：有项目原点时直接换算成原始投影坐标
        // X 轴 = 东向；Y 边 = 高程（场景值已含 20 倍夸张）；Z 边 = 北向（场景内取反）
        const projOrigin = this.getOrigin?.() ?? null
        const getters: Array<(v: THREE.Vector3) => number> = [
            (v) => (projOrigin ? projOrigin.x + v.x : v.x),
            (v) => (projOrigin ? projOrigin.z + v.y / 20 : v.y / 20),
            (v) => (projOrigin ? projOrigin.y - v.z : Math.abs(v.z)),
        ]

        for (let ei = 0; ei < edges.length; ei++) {
            const edge = edges[ei]
            const getVal = getters[ei]

            for (let i = 0; i < BoundingBoxTool.TICK_COUNT; i++) {
                const t = i / (BoundingBoxTool.TICK_COUNT - 1)
                const point = new THREE.Vector3().lerpVectors(origin, edge.end, t)

                // 刻度短线
                const tickStart = point.clone().addScaledVector(edge.off, tickLen * 0.15)
                const tickEnd = point.clone().addScaledVector(edge.off, tickLen)
                const tickGeo = new THREE.BufferGeometry().setFromPoints([tickStart, tickEnd])
                const tickLine = new THREE.Line(tickGeo, lineMat)
                tickLine.userData.boundingBoxHelper = true
                this.group.add(tickLine)
                this.resources.push(tickGeo)

                // 精灵标签，放在刻度线末端（跳过 origin 角点避免三轴文字重叠）
                if (i > 0) {
                    const value = getVal(point)
                    const labelPos = point.clone().addScaledVector(edge.off, spriteGap)
                    const { sprite, aspect } = this.makeSprite(edge.axis, value)
                    sprite.position.copy(labelPos)
                    sprite.userData.boundingBoxHelper = true
                    this.group.add(sprite)
                    this.labels.push({ sprite, aspect })
                }
            }
        }

        this.group.visible = true
    }

    private fmt(value: number): string {
        if (Math.abs(value) >= 1e6) return Number(value.toFixed(0)).toLocaleString()
        if (Math.abs(value) >= 1e3) return value.toFixed(1)
        if (Math.abs(value) >= 1) return value.toFixed(2)
        if (Math.abs(value) >= 0.01) return value.toFixed(4)
        return value.toExponential(3)
    }

    private makeSprite(axis: string, value: number) {
        // 显示 Z 值（高程）的轴加注"高"
        let label :string
        if(axis === 'X') {
            label = `${axis}: ${this.fmt(value)}`
        } else {
            label = axis ==='Y' ? `Z: ${this.fmt(value)}` : `Y: ${this.fmt(value)}`
        }
        const charCount = Math.max(6, label.length)
        const width = Math.min(512, Math.max(180, charCount * 22))
        const height = 68

        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        if (ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height)
            ctx.fillStyle = '#ffffff'
            ctx.font = 'bold 40px Microsoft YaHei'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.75)'
            ctx.lineWidth = 4
            ctx.strokeText(label, canvas.width / 2, canvas.height / 2)
            ctx.fillText(label, canvas.width / 2, canvas.height / 2)
        }

        const texture = new THREE.CanvasTexture(canvas)
        texture.needsUpdate = true
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: false,
            depthWrite: false,
        })
        const sprite = new THREE.Sprite(material)
        sprite.scale.set(1, 1, 1)

        this.resources.push(texture, material)
        return { sprite, aspect: width / height }
    }

    private scaleSprite(item: AxisLabel) {
        const pos = item.sprite.position
        const worldPerPixel = this.getWorldUnitsPerPixel(pos)
        const targetHeight = THREE.MathUtils.clamp(
            worldPerPixel * BoundingBoxTool.TARGET_PX_HEIGHT,
            BoundingBoxTool.MIN_HEIGHT,
            BoundingBoxTool.MAX_HEIGHT,
        )
        item.sprite.scale.set(targetHeight * item.aspect, targetHeight, 1)
    }

    private getWorldUnitsPerPixel(anchor: THREE.Vector3) {
        const viewportHeight = Math.max(
            this.domElement.clientHeight || this.domElement.getBoundingClientRect().height,
            1,
        )

        if ((this.camera as THREE.PerspectiveCamera).isPerspectiveCamera) {
            const perspective = this.camera as THREE.PerspectiveCamera
            const distance = perspective.position.distanceTo(anchor)
            const fov = THREE.MathUtils.degToRad(perspective.fov)
            return (2 * distance * Math.tan(fov / 2)) / viewportHeight
        }

        if ((this.camera as THREE.OrthographicCamera).isOrthographicCamera) {
            const ortho = this.camera as THREE.OrthographicCamera
            return ((ortho.top - ortho.bottom) / ortho.zoom) / viewportHeight
        }

        return 1
    }
}
