import * as THREE from 'three'
import { SCENE_BACKGROUND_COLOR } from '../constants'
import { GEO_ROOT_ROTATION_X } from './coordinateTransform'

export class SceneManager {
    readonly scene: THREE.Scene
    readonly geoRoot: THREE.Group
    // 网格辅助线用于提供尺度与方向参照
    private grid: THREE.GridHelper

    constructor() {
        this.scene = new THREE.Scene()
        // 设置统一背景色，提升深度对比并弱化空白区域干扰
        this.scene.background = new THREE.Color(SCENE_BACKGROUND_COLOR)
        // 参数: 尺寸 2000、分段 40、主次线颜色一致
        this.grid = new THREE.GridHelper(2000, 40, 0x1e3a5f, 0x1e3a5f)
        this._addGrid()

        // 统一地学对象根节点，在显示层做一次坐标系适配
        this.geoRoot = new THREE.Group()
        this.geoRoot.name = '__geo_root__'
        this.geoRoot.rotation.x = GEO_ROOT_ROTATION_X
        this.scene.add(this.geoRoot)
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
        this.geoRoot.add(obj)
    }

    removeObject(obj: THREE.Object3D) {
        this.geoRoot.remove(obj)
    }

    getObjectByName(name: string): THREE.Object3D | undefined {
        return this.scene.getObjectByName(name)
    }

    dispose() {
        this.scene.clear()
        this.grid.dispose()
    }
}
