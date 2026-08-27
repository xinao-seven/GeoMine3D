import * as THREE from 'three'

type DisposableResource = THREE.BufferGeometry | THREE.Material | THREE.Texture

export class ResourceTracker {
    private referenceCounts = new Map<DisposableResource, number>()
    private objectResources = new WeakMap<THREE.Object3D, Set<DisposableResource>>()

    trackObject(root: THREE.Object3D) {
        if (this.objectResources.has(root)) return
        const resources = this.collectResources(root)
        this.objectResources.set(root, resources)
        for (const resource of resources) {
            this.referenceCounts.set(resource, (this.referenceCounts.get(resource) ?? 0) + 1)
        }
    }

    releaseObject(root: THREE.Object3D) {
        const resources = this.objectResources.get(root) ?? this.collectResources(root)
        for (const resource of resources) {
            const nextCount = (this.referenceCounts.get(resource) ?? 1) - 1
            if (nextCount <= 0) {
                resource.dispose()
                this.referenceCounts.delete(resource)
            } else {
                this.referenceCounts.set(resource, nextCount)
            }
        }
        this.objectResources.delete(root)
    }

    disposeAll() {
        for (const resource of this.referenceCounts.keys()) resource.dispose()
        this.referenceCounts.clear()
        this.objectResources = new WeakMap()
    }

    get trackedResourceCount() {
        return this.referenceCounts.size
    }

    private collectResources(root: THREE.Object3D) {
        const resources = new Set<DisposableResource>()
        root.traverse((object) => {
            const mesh = object as THREE.Mesh
            if (mesh.geometry?.isBufferGeometry) resources.add(mesh.geometry)
            if (!mesh.material) return
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
            for (const material of materials) {
                resources.add(material)
                this.collectMaterialTextures(material, resources)
            }
        })
        return resources
    }

    private collectMaterialTextures(material: THREE.Material, resources: Set<DisposableResource>) {
        for (const value of Object.values(material)) {
            if ((value as THREE.Texture)?.isTexture) resources.add(value as THREE.Texture)
        }
        const uniforms = (material as THREE.ShaderMaterial).uniforms
        if (!uniforms) return
        for (const uniform of Object.values(uniforms)) {
            const value = uniform?.value
            if ((value as THREE.Texture)?.isTexture) resources.add(value as THREE.Texture)
            if (Array.isArray(value)) {
                for (const item of value) {
                    if ((item as THREE.Texture)?.isTexture) resources.add(item as THREE.Texture)
                }
            }
        }
    }
}
