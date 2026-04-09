import { Viewer } from 'cesium'

export class PrimitiveManager {
    private readonly viewer: Viewer
    private readonly taggedPrimitives = new Map<string, Set<any>>()

    constructor(viewer: Viewer) {
        this.viewer = viewer
    }

    add<T>(primitive: T, tag = 'default'): T {
        this.viewer.scene.primitives.add(primitive as any)

        if (!this.taggedPrimitives.has(tag)) {
            this.taggedPrimitives.set(tag, new Set())
        }
        this.taggedPrimitives.get(tag)!.add(primitive)

        return primitive
    }

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

    clearAll() {
        this.viewer.scene.primitives.removeAll()
        this.taggedPrimitives.clear()
    }
}
