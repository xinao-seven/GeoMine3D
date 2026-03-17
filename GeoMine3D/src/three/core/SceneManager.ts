import * as THREE from 'three'
import { SCENE_BACKGROUND_COLOR } from '../constants'

export class SceneManager {
    readonly scene: THREE.Scene
    private grid: THREE.GridHelper

    constructor() {
        this.scene = new THREE.Scene()
        this.scene.background = new THREE.Color(SCENE_BACKGROUND_COLOR)
        this.grid = new THREE.GridHelper(2000, 40, 0x1e3a5f, 0x1e3a5f)
        this._addGrid()
    }

    private _addGrid() {
        this.grid.name = '__grid__'
        this.scene.add(this.grid)
    }
    removeGrid() {
        this.scene.remove(this.grid)
    }

    addObject(obj: THREE.Object3D) {
        this.scene.add(obj)
    }

    removeObject(obj: THREE.Object3D) {
        this.scene.remove(obj)
    }

    getObjectByName(name: string): THREE.Object3D | undefined {
        return this.scene.getObjectByName(name)
    }

    dispose() {
        this.scene.clear()
        this.grid.dispose()
    }
}
