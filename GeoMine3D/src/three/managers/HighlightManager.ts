import * as THREE from 'three'
import { HIGHLIGHT_COLOR, SELECTION_COLOR } from '../constants'

export class HighlightManager {
    private highlightedObject: THREE.Object3D | null = null
    private selectedObject: THREE.Object3D | null = null
    private originalMaterials = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>()

    // 材质编辑应作用于业务材质，而不是选中/悬停时的临时高亮材质。
    getEditableMaterials(mesh: THREE.Mesh): THREE.Material[] {
        const source = this.originalMaterials.get(mesh) ?? mesh.material
        return Array.isArray(source) ? source : [source]
    }

    // 设置临时高亮对象，不影响已选中对象的状态优先级。
    highlight(object: THREE.Object3D | null) {
        // 清除之前的高亮
        if (this.highlightedObject && this.highlightedObject !== this.selectedObject) {
            this._restoreMaterials(this.highlightedObject)
        }
        this.highlightedObject = object
        if (object) {
            this._applyColor(object, HIGHLIGHT_COLOR, false)
        }
    }

    // 设置当前选中对象并应用选中材质。
    select(object: THREE.Object3D | null) {
        if (this.selectedObject) {
            this._restoreMaterials(this.selectedObject)
        }
        this.selectedObject = object
        if (object) {
            this._applyColor(object, SELECTION_COLOR, true)
        }
    }

    // 递归替换网格材质为高亮/选中色。
    private _applyColor(object: THREE.Object3D, color: number, isSelected: boolean) {
        object.traverse((child) => {
            if ((child as any).isMesh) {
                const mesh = child as THREE.Mesh
                if (!this.originalMaterials.has(mesh)) {
                    this.originalMaterials.set(mesh, mesh.material)
                }
                const source = this.originalMaterials.get(mesh)

                const tintMaterial = (src: any) => {
                    const mat = new THREE.MeshLambertMaterial({
                        color,
                        transparent: !isSelected,
                        opacity: isSelected ? 1 : 0.82,
                        side: src?.side ?? THREE.FrontSide,
                    })
                    if (src?.map) {
                        mat.map = src.map
                        if (mat.map) {
                            mat.map.colorSpace = THREE.SRGBColorSpace
                        }
                    }
                    return mat
                }

                if (Array.isArray(source)) {
                    mesh.material = source.map((m: any) => tintMaterial(m))
                } else {
                    mesh.material = tintMaterial(source as any)
                }
            }
        })
    }

    // 恢复对象原始材质。
    private _restoreMaterials(object: THREE.Object3D) {
        object.traverse((child) => {
            if ((child as any).isMesh) {
                const mesh = child as THREE.Mesh
                const original = this.originalMaterials.get(mesh)
                if (original) {
                    const temporary = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
                    for (const material of temporary) material.dispose()
                    mesh.material = original
                    this.originalMaterials.delete(mesh)
                }
            }
        })
    }

    // 清理高亮管理器内部缓存。
    dispose() {
        if (this.highlightedObject) this._restoreMaterials(this.highlightedObject)
        if (this.selectedObject && this.selectedObject !== this.highlightedObject) {
            this._restoreMaterials(this.selectedObject)
        }
        this.highlightedObject = null
        this.selectedObject = null
        this.originalMaterials.clear()
    }
}
