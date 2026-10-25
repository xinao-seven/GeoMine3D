import * as THREE from 'three'
import type { BasemapMeta } from '@/api/workspace'

/**
 * GeoTIFF 预处理底图（地形灰度图）平面纹理。
 * 元数据由 scripts/preprocess_basemap.py 生成；bounds 为投影坐标（米），
 * 平面 1 单位 = 1 米，铺在基准高程附近（略低于边界/等值线叠加层）。
 */
export class BasemapOverlay {
    readonly group = new THREE.Group()
    private mesh: THREE.Mesh | null = null
    private material: THREE.MeshBasicMaterial | null = null
    private geometry: THREE.BufferGeometry | null = null
    private texture: THREE.Texture | null = null

    constructor() {
        this.group.name = 'basemap'
        this.group.userData.overlayHelper = true
        this.group.visible = false
    }

    async build(meta: BasemapMeta, origin: { x: number; y: number }, yLevel: number) {
        this.clear()
        const loader = new THREE.TextureLoader()
        const texture = await loader.loadAsync(`/static/models/basemap/${meta.image || 'basemap.jpg'}`)
        texture.colorSpace = THREE.SRGBColorSpace

        const width = meta.bounds.xmax - meta.bounds.xmin
        const height = meta.bounds.ymax - meta.bounds.ymin
        if (width <= 0 || height <= 0) {
            texture.dispose()
            return false
        }
        const centerX = (meta.bounds.xmin + meta.bounds.xmax) / 2 - origin.x
        // 北向 y → 场景 -z
        const centerZ = -((meta.bounds.ymin + meta.bounds.ymax) / 2 - origin.y)

        const geometry = new THREE.PlaneGeometry(width, height)
        geometry.rotateX(-Math.PI / 2)
        const material = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            opacity: 0.8,
            depthWrite: false,
            side: THREE.DoubleSide,
        })
        const mesh = new THREE.Mesh(geometry, material)
        mesh.position.set(centerX, yLevel - 1, centerZ)
        mesh.renderOrder = 0
        mesh.userData.overlayHelper = true

        this.group.add(mesh)
        this.mesh = mesh
        this.geometry = geometry
        this.material = material
        this.texture = texture
        return true
    }

    setOpacity(value: number) {
        if (this.material) {
            this.material.opacity = Math.min(1, Math.max(0.05, value))
        }
    }

    setVisible(visible: boolean) {
        this.group.visible = visible
    }

    get ready() {
        return this.mesh !== null
    }

    clear() {
        this.group.clear()
        this.mesh = null
        this.geometry?.dispose()
        this.material?.dispose()
        this.texture?.dispose()
        this.geometry = null
        this.material = null
        this.texture = null
    }

    dispose() {
        this.clear()
        this.group.parent?.remove(this.group)
    }
}
