import * as THREE from 'three'

export interface AnnotationResult {
    id: string
    text: string
    position: THREE.Vector3
    createdAt: number
}

export interface AnnotationEnableOptions {
    onCreate?: (result: AnnotationResult) => void
    resolveText?: (index: number, point: THREE.Vector3) => string | null | undefined
}

interface AnnotationVisual {
    container: THREE.Group
    anchor: THREE.Vector3
    marker: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>
    guide: THREE.Line<THREE.BufferGeometry, THREE.LineBasicMaterial>
    label: THREE.Sprite
    labelAspect: number
}

/**
 * 标注工具 - 单击落点创建文本标注。
 */
export class AnnotationTool {
    private static readonly TARGET_MARKER_PX_RADIUS = 8
    private static readonly TARGET_LABEL_PX_HEIGHT = 36
    private static readonly TARGET_LABEL_LIFT_PX = 52
    private static readonly MIN_MARKER_RADIUS = 2.8
    private static readonly MAX_MARKER_RADIUS = 120
    private static readonly MIN_LABEL_HEIGHT = 26
    private static readonly MAX_LABEL_HEIGHT = 480
    private static readonly MIN_LABEL_LIFT = 14
    private static readonly MAX_LABEL_LIFT = 560

    private scene: THREE.Scene
    private camera: THREE.Camera
    private domElement: HTMLElement
    private raycaster = new THREE.Raycaster()
    private pointer = new THREE.Vector2()
    private enabled = false
    private group = new THREE.Group()
    private results: AnnotationResult[] = []
    private annotationNodes = new Map<string, AnnotationVisual>()
    private onCreate?: (result: AnnotationResult) => void
    private resolveText?: (index: number, point: THREE.Vector3) => string | null | undefined

    constructor(scene: THREE.Scene, camera: THREE.Camera, domElement: HTMLElement) {
        this.scene = scene
        this.camera = camera
        this.domElement = domElement
        this.group.name = 'annotations'
        this.group.userData.annotationHelper = true
        this.scene.add(this.group)
    }

    // 启用标注模式并绑定点击事件。
    enable(options: AnnotationEnableOptions = {}) {
        if (this.enabled) return
        this.enabled = true
        this.onCreate = options.onCreate
        this.resolveText = options.resolveText
        this.domElement.addEventListener('click', this.onClick)
    }

    // 关闭标注模式并解绑点击事件。
    disable() {
        if (!this.enabled) return
        this.enabled = false
        this.domElement.removeEventListener('click', this.onClick)
    }

    // 清空所有标注。
    clear() {
        for (const visual of this.annotationNodes.values()) {
            this.disposeObject(visual.container)
            this.group.remove(visual.container)
        }
        this.annotationNodes.clear()
        this.results = []
    }

    // 删除指定标注。
    remove(id: string) {
        const visual = this.annotationNodes.get(id)
        if (!visual) return false

        this.disposeObject(visual.container)
        this.group.remove(visual.container)
        this.annotationNodes.delete(id)
        this.results = this.results.filter((item) => item.id !== id)
        return true
    }

    // 获取工具是否启用。
    isEnabled() {
        return this.enabled
    }

    // 获取标注结果快照。
    getResults() {
        return [...this.results]
    }

    // 在动画循环中调用，按相机距离刷新标注可读尺寸。
    update() {
        if (!this.annotationNodes.size) return
        for (const visual of this.annotationNodes.values()) {
            this.updateVisualScale(visual)
        }
    }

    // 销毁工具并释放资源。
    dispose() {
        this.disable()
        this.clear()
        this.scene.remove(this.group)
    }

    // 点击场景创建标注。
    private onClick = (event: MouseEvent) => {
        const point = this.pickPoint(event)
        if (!point) return

        const index = this.results.length + 1
        const text = this.getAnnotationText(index, point)
        if (!text) return

        const result = this.createAnnotation(point, text)
        this.results.push(result)
        this.onCreate?.(result)
    }

    // 通过射线拾取获取场景落点。
    private pickPoint(event: MouseEvent) {
        const rect = this.domElement.getBoundingClientRect()
        this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
        this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

        this.raycaster.setFromCamera(this.pointer, this.camera)
        const intersects = this.raycaster.intersectObjects(this.scene.children, true)
        const hit = intersects.find((item) => {
            const data = item.object.userData
            return !data.annotationHelper && !data.measureHelper && !data.clipHelper
        })
        return hit?.point.clone() || null
    }

    // 获取标注文本，优先使用外部解析器，否则回退到默认 prompt。
    private getAnnotationText(index: number, point: THREE.Vector3) {
        const resolved = this.resolveText?.(index, point)
        if (typeof resolved === 'string') {
            const trimmed = resolved.trim()
            return trimmed || null
        }

        if (resolved === null) return null

        if (typeof window !== 'undefined' && typeof window.prompt === 'function') {
            const text = window.prompt('请输入标注内容', `标注 ${index}`)
            const trimmed = text?.trim() || ''
            return trimmed || null
        }

        return `标注 ${index}`
    }

    // 创建单个标注（点位 + 引导线 + 文本精灵）。
    private createAnnotation(position: THREE.Vector3, text: string): AnnotationResult {
        const id = `annotation_${Date.now()}_${this.results.length + 1}`
        const createdAt = Date.now()

        const container = new THREE.Group()
        container.userData.annotationHelper = true
        container.userData.annotationId = id

        const marker = new THREE.Mesh(
            new THREE.SphereGeometry(1, 12, 12),
            new THREE.MeshBasicMaterial({ color: 0xffcc33 })
        )
        marker.position.copy(position)
        marker.userData.annotationHelper = true
        container.add(marker)

        const labelPos = position.clone().add(new THREE.Vector3(0, AnnotationTool.MIN_LABEL_LIFT, 0))
        const guideGeometry = new THREE.BufferGeometry().setFromPoints([position, labelPos])
        const guideMaterial = new THREE.LineBasicMaterial({ color: 0xffd56b, transparent: true, opacity: 0.75 })
        const guideLine = new THREE.Line(guideGeometry, guideMaterial)
        guideLine.userData.annotationHelper = true
        container.add(guideLine)

        const { sprite: label, aspect: labelAspect } = this.createLabelSprite(text)
        label.position.copy(labelPos)
        label.userData.annotationHelper = true
        container.add(label)

        const visual: AnnotationVisual = {
            container,
            anchor: position.clone(),
            marker,
            guide: guideLine,
            label,
            labelAspect,
        }

        this.group.add(container)
        this.annotationNodes.set(id, visual)
        this.updateVisualScale(visual)

        return {
            id,
            text,
            position: position.clone(),
            createdAt,
        }
    }

    // 生成标注文本精灵。
    private createLabelSprite(text: string) {
        const charCount = Math.max(6, text.length)
        const width = Math.min(512, Math.max(220, charCount * 22))
        const height = 72

        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        if (ctx) {
            ctx.fillStyle = 'rgba(36, 29, 14, 0.92)'
            ctx.strokeStyle = 'rgba(255, 213, 107, 0.9)'
            ctx.lineWidth = 2
            ctx.fillRect(0, 0, canvas.width, canvas.height)
            ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2)
            ctx.fillStyle = '#fff2d0'
            ctx.font = 'bold 26px Microsoft YaHei'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.fillText(text, canvas.width / 2, canvas.height / 2)
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
        return { sprite, aspect: width / height }
    }

    // 以“目标像素尺寸”换算到世界坐标，保证远距离仍可读。
    private updateVisualScale(visual: AnnotationVisual) {
        const worldPerPixel = this.getWorldUnitsPerPixel(visual.anchor)

        const markerRadius = this.clamp(
            worldPerPixel * AnnotationTool.TARGET_MARKER_PX_RADIUS,
            AnnotationTool.MIN_MARKER_RADIUS,
            AnnotationTool.MAX_MARKER_RADIUS
        )
        visual.marker.scale.setScalar(markerRadius)

        const labelHeight = this.clamp(
            worldPerPixel * AnnotationTool.TARGET_LABEL_PX_HEIGHT,
            AnnotationTool.MIN_LABEL_HEIGHT,
            AnnotationTool.MAX_LABEL_HEIGHT
        )

        const lift = this.clamp(
            worldPerPixel * AnnotationTool.TARGET_LABEL_LIFT_PX,
            AnnotationTool.MIN_LABEL_LIFT,
            AnnotationTool.MAX_LABEL_LIFT
        )

        const labelPos = visual.anchor.clone().add(new THREE.Vector3(0, lift, 0))
        visual.label.position.copy(labelPos)
        visual.label.scale.set(labelHeight * visual.labelAspect, labelHeight, 1)

        const pos = visual.guide.geometry.attributes.position
        pos.setXYZ(0, visual.anchor.x, visual.anchor.y, visual.anchor.z)
        pos.setXYZ(1, labelPos.x, labelPos.y, labelPos.z)
        pos.needsUpdate = true
        visual.guide.geometry.computeBoundingSphere()
    }

    // 计算锚点处“每像素对应世界长度”。
    private getWorldUnitsPerPixel(anchor: THREE.Vector3) {
        const viewportHeight = Math.max(this.domElement.clientHeight || this.domElement.getBoundingClientRect().height, 1)

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

    // 数值夹紧。
    private clamp(value: number, min: number, max: number) {
        return Math.min(max, Math.max(min, value))
    }

    // 释放对象下挂载的几何、材质与纹理资源。
    private disposeObject(object: THREE.Object3D) {
        object.traverse((child) => {
            const mesh = child as THREE.Mesh
            if (mesh.geometry) {
                mesh.geometry.dispose()
            }

            const material = (mesh as any).material
            if (Array.isArray(material)) {
                for (const mat of material) {
                    const map = (mat as any).map
                    if (map) map.dispose()
                    mat.dispose?.()
                }
                return
            }

            if (material) {
                const map = (material as any).map
                if (map) map.dispose()
                material.dispose?.()
            }
        })
    }
}
