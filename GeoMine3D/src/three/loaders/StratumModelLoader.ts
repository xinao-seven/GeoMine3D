import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader'
import type { ModelItem } from '@/types'

// DRACO 解码器路径（CDN，支持 Draco 压缩的 GLB 文件）
const DRACO_DECODER_PATH = 'https://www.gstatic.com/draco/versioned/decoders/1.5.7/'

function createLoader(): GLTFLoader {
    const loader = new GLTFLoader()
    const dracoLoader = new DRACOLoader()
    dracoLoader.setDecoderPath(DRACO_DECODER_PATH)
    dracoLoader.preload()
    loader.setDRACOLoader(dracoLoader)
    return loader
}

export class StratumModelLoader {
    private loader = createLoader()

    private generateLayerColor(index: number): number {
        const colors = [
            0x8b4513,
            0xdaa520,
            0x2e8b57,
            0x4682b4,
            0xd2691e,
            0x9acd32,
            0xcd853f,
            0x20b2aa,
            0x778899,
            0xf0e68c,
        ]
        return colors[index % colors.length]
    }

    async load(model: ModelItem): Promise<THREE.Group> {
        return new Promise((resolve, reject) => {
            this.loader.load(
                model.fileUrl,
                (gltf) => {
                    const group = gltf.scene
                    group.name = `stratum_${model.id}`
                    // 根节点保留模型信息，但不作为选中目标，避免一选全亮
                    group.userData = { id: model.id, name: model.name, modelData: model }

                    const meshes: THREE.Mesh[] = []
                    group.traverse((child) => {
                        if ((child as THREE.Mesh).isMesh) {
                            meshes.push(child as THREE.Mesh)
                        }
                    })

                    let meshIndex = 0

                    meshes.forEach((mesh, index) => {
                        mesh.visible = true

                        const originalMaterial = Array.isArray(mesh.material)
                            ? mesh.material[0]
                            : mesh.material
                        const layerColor = this.generateLayerColor(index)

                        const lambertMaterial = new THREE.MeshLambertMaterial({
                            color: layerColor,
                            transparent: true,
                            opacity: 0.95,
                            side: THREE.DoubleSide,
                            emissive: 0x0d121f,
                            emissiveIntensity: 0.08,
                            clipShadows: true,
                        })
                        lambertMaterial.clippingPlanes = []

                        if ((originalMaterial as any)?.map) {
                            lambertMaterial.map = (originalMaterial as any).map
                            if (lambertMaterial.map) lambertMaterial.map.colorSpace = THREE.SRGBColorSpace
                        }

                        mesh.material = lambertMaterial

                        const edges = new THREE.EdgesGeometry(mesh.geometry)
                        const edgesMaterial = new THREE.LineBasicMaterial({
                            color: 0x000000,
                            transparent: true,
                            opacity: 0.8,
                        })
                        const edgeLines = new THREE.LineSegments(edges, edgesMaterial)
                        edgeLines.visible = false
                        mesh.add(edgeLines)

                        const layerName = mesh.name?.trim() || `${model.name}_layer_${meshIndex + 1}`
                        mesh.userData = {
                            id: `${model.id}::${meshIndex}`,
                            name: layerName,
                            type: 'stratum',
                            modelData: model,
                            modelId: model.id,
                            layerIndex: meshIndex,
                            layerName,
                            edgeLines,
                        }

                        meshIndex += 1
                    })
                    resolve(group)
                },
                undefined,
                reject
            )
        })
    }
}
