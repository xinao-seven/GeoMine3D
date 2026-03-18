import * as THREE from 'three'
import { HIGHLIGHT_COLOR, SELECTION_COLOR } from '../constants'

export class HighlightManager {
  private highlightedObject: THREE.Object3D | null = null
  private selectedObject: THREE.Object3D | null = null
  private originalMaterials = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>()

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

  select(object: THREE.Object3D | null) {
    if (this.selectedObject) {
      this._restoreMaterials(this.selectedObject)
    }
    this.selectedObject = object
    if (object) {
      this._applyColor(object, SELECTION_COLOR, true)
    }
  }

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

  private _restoreMaterials(object: THREE.Object3D) {
    object.traverse((child) => {
      if ((child as any).isMesh) {
        const mesh = child as THREE.Mesh
        const original = this.originalMaterials.get(mesh)
        if (original) {
          mesh.material = original
          this.originalMaterials.delete(mesh)
        }
      }
    })
  }

  dispose() {
    this.originalMaterials.clear()
  }
}
