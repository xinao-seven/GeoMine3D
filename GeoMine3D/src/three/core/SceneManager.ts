import * as THREE from 'three'
import { SCENE_BACKGROUND_COLOR } from '../constants'
import { GEO_ROOT_ROTATION_X } from './coordinateTransform'

export class SceneManager {
    readonly scene: THREE.Scene
    readonly geoRoot: THREE.Group
    // 网格辅助线用于提供尺度与方向参照
    private grid: THREE.GridHelper
    private geoRootRotationXEnabled = true

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

    // 移除场景网格辅助线。
    removeGrid() {
        this.scene.remove(this.grid)
    }

    // 将对象添加到地学根节点，统一受坐标映射控制。
    addObject(obj: THREE.Object3D) {
        this.geoRoot.add(obj)
    }

    // 从地学根节点移除对象。
    removeObject(obj: THREE.Object3D) {
        this.geoRoot.remove(obj)
    }

    // 开关地学根节点的 X 轴旋转映射。
    setGeoRootRotationXEnabled(enabled: boolean) {
        this.geoRootRotationXEnabled = enabled
        this.geoRoot.rotation.x = enabled ? GEO_ROOT_ROTATION_X : 0
        this.geoRoot.updateMatrixWorld(true)
    }

    // 获取当前是否启用坐标映射旋转。
    isGeoRootRotationXEnabled() {
        return this.geoRootRotationXEnabled
    }

    // 按名称查询场景对象。
    getObjectByName(name: string): THREE.Object3D | undefined {
        return this.scene.getObjectByName(name)
    }

    // 释放场景资源。
    dispose() {
        this.scene.clear()
        this.grid.dispose()
    }
}
