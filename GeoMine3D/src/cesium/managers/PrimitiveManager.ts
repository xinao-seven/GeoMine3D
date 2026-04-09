import { Viewer } from 'cesium'

export class PrimitiveManager {
    private readonly viewer: Viewer
    private readonly taggedPrimitives = new Map<string, Set<any>>()

    /**
     * 创建 Primitive 管理器。
     */
    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    /**
     * 添加 Primitive 并按标签归档。
     */
    add<T>(primitive: T, tag = 'default'): T {
        this.viewer.scene.primitives.add(primitive as any)

        if (!this.taggedPrimitives.has(tag)) {
            this.taggedPrimitives.set(tag, new Set())
        }
        this.taggedPrimitives.get(tag)!.add(primitive)

        return primitive
    }

    /**
     * 移除单个 Primitive。
     */
    remove(primitive: any) {
        const removed = this.viewer.scene.primitives.remove(primitive)
        if (!removed) {
            return false
        }

        for (const set of this.taggedPrimitives.values()) {
            set.delete(primitive)
        }
        return true
    }

    /**
     * 按标签批量设置 Primitive 显隐。
     */
    setVisibleByTag(tag: string, visible: boolean) {
        const set = this.taggedPrimitives.get(tag)
        if (!set) {
            return
        }

        for (const primitive of set) {
            if ('show' in primitive) {
                primitive.show = visible
            }
        }
    }

    /**
     * 清理指定标签下全部 Primitive。
     */
    clearTag(tag: string) {
        const set = this.taggedPrimitives.get(tag)
        if (!set) {
            return
        }

        for (const primitive of set) {
            this.viewer.scene.primitives.remove(primitive)
        }
        set.clear()
    }

    /**
     * 清空场景中的全部 Primitive 并重置标签索引。
     */
    clearAll() {
        this.viewer.scene.primitives.removeAll()
        this.taggedPrimitives.clear()
    }
}
