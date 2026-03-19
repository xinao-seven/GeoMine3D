import * as THREE from 'three'
import { SCENE_BACKGROUND_COLOR } from '../constants'

export class SceneManager {
    readonly scene: THREE.Scene
    // 网格辅助线用于提供尺度与方向参照
    private grid: THREE.GridHelper

    constructor() {
        this.scene = new THREE.Scene()
        // 设置统一背景色，提升深度对比并弱化空白区域干扰
        this.scene.background = new THREE.Color(SCENE_BACKGROUND_COLOR)
        // 参数: 尺寸 2000、分段 40、主次线颜色一致
        this.grid = new THREE.GridHelper(2000, 40, 0x1e3a5f, 0x1e3a5f)
        this._addGrid()
    }

    private _addGrid() {
        // 固定命名，便于外部按名称检索或排除
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
