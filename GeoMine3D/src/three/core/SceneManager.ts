import * as THREE from 'three'
import { SCENE_BACKGROUND_COLOR } from '../constants'
import { GEO_ROOT_ROTATION_X } from './coordinateTransform'

export class SceneManager {
    readonly scene: THREE.Scene
    readonly geoRoot: THREE.Group
    // 网格辅助线用于提供尺度与方向参照
    private grid: THREE.GridHelper
    private geoRootRotationXEnabled = true
    /** 竖向缩放倍率(作用在 geoRoot.scale.z;1 = 保持各模型自带的比例) */
    private verticalScaleMultiplier = 1

    constructor() {
        this.scene = new THREE.Scene()
        // 设置统一背景色，提升深度对比并弱化空白区域干扰
        this.scene.background = new THREE.Color(SCENE_BACKGROUND_COLOR)
        // 参数: 尺寸 2000、分段 40、主次线颜色一致
        this.grid = new THREE.GridHelper(40000, 40, 0x4a5d51, 0x263129)
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

    /**
     * 设置全局竖向缩放倍率。
     *
     * 为什么统一加在 geoRoot 上:本工程的竖向夸张分散在五处——分层/井巷加载时
     * `group.scale.z = metadata.vertical_scale`、钻孔按 `(z-z0)*scale` 摆位、
     * 投影模型对齐、以及沉陷位移(作用在几何空间,会被父节点缩放一起放大)。
     * 它们都已经内置了同一个基准倍数,所以在这里再乘一个倍率,
     * 就能一次性、一致地改变全场景的竖向比例,不会出现双重缩放。
     *
     * geoRoot 带 rotation.x = -90°(局部 z → 世界 y),
     * 而 three.js 的对象矩阵是 T·R·S,缩放先于旋转,因此 scale.z 正好是竖向。
     */
    setVerticalScaleMultiplier(multiplier: number) {
        const m = Number.isFinite(multiplier) ? Math.min(20, Math.max(0.05, multiplier)) : 1
        this.verticalScaleMultiplier = m
        this.geoRoot.scale.z = m
        this.geoRoot.updateMatrixWorld(true)
    }

    getVerticalScaleMultiplier() {
        return this.verticalScaleMultiplier
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
