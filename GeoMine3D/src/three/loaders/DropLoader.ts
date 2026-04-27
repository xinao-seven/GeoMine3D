import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader'
import type { StratumLayerControl } from '@/types'

const DRACO_DECODER_PATH = 'https://www.gstatic.com/draco/versioned/decoders/1.5.7/'

const DROP_PALETTE = [
    0x2e8b57,
    0xdaa520,
    0x2e8b57,
    0x000000,
    0xd2691e,
    0x20b2aa,
    0xcd853f,
    0x20b2aa,
    0x778899,
    0xf0e68c,
]

function createLoader(): GLTFLoader {
    const loader = new GLTFLoader()
    const dracoLoader = new DRACOLoader()
    dracoLoader.setDecoderPath(DRACO_DECODER_PATH)
    dracoLoader.preload()
    loader.setDRACOLoader(dracoLoader)
    return loader
}

export interface DropLoadResult {
    group: THREE.Group
    modelId: string
    modelName: string
    controls: StratumLayerControl[]
}

export class DropLoader {
    private loader = createLoader()

    async loadFromFile(file: File): Promise<DropLoadResult> {
        const url = URL.createObjectURL(file)
        const modelName = file.name.replace(/\.glb$/i, '')
        const modelId = `dropped_${modelName}_${Date.now()}`

        try {
            const group = await new Promise<THREE.Group>((resolve, reject) => {
                this.loader.load(url, (g) => resolve(g.scene), undefined, (e) => reject(e))
            })

            group.name = `dropped_${modelId}`
            group.userData = { id: modelId, name: modelName, type: 'custom' }

            const meshes: THREE.Mesh[] = []
            group.traverse((child) => {
                if ((child as THREE.Mesh).isMesh) {
                    meshes.push(child as THREE.Mesh)
                }
            })

            meshes.forEach((mesh, index) => {
                mesh.visible = true

                const color = DROP_PALETTE[index % DROP_PALETTE.length]
                const lambertMaterial = new THREE.MeshLambertMaterial({
                    color,
                    transparent: true,
                    opacity: 0.95,
                    side: THREE.DoubleSide,
                    emissive: 0x0d121f,
                    emissiveIntensity: 0.08,
                    clipShadows: true,
                })
                lambertMaterial.clippingPlanes = []

                const origMat = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material
                if ((origMat as any)?.map) {
                    lambertMaterial.map = (origMat as any).map
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

                mesh.userData = {
                    id: `${modelId}::${index}`,
                    name: `${modelName}_${index + 1}`,
                    type: 'custom',
                    modelId,
                    layerIndex: index,
                    edgeLines,
                }
            })

            const controls = extractStratumControls(group, modelId, modelName)

            return { group, modelId, modelName, controls }
        } finally {
            URL.revokeObjectURL(url)
        }
    }
}

function toHexColor(color?: THREE.Color): string {
    if (!color) return '#5a8a9a'
    return `#${color.getHexString()}`
}

function extractStratumControls(object: THREE.Object3D, modelId: string, modelName: string): StratumLayerControl[] {
    const controls: StratumLayerControl[] = []
    object.traverse((child) => {
        if (!(child as THREE.Mesh).isMesh) return
        const mesh = child as THREE.Mesh
        const key = String(mesh.userData?.id || `${modelId}::${mesh.uuid}`)
        const layerName = String(mesh.userData?.layerName || mesh.name || `${modelName}_layer`)
        const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material
        const color = material && (material as any).color ? toHexColor((material as any).color) : '#5a8a9a'
        const opacity = typeof (material as any)?.opacity === 'number' ? (material as any).opacity : 1
        controls.push({
            key,
            modelId,
            modelName,
            layerName,
            visible: mesh.visible,
            opacity,
            color,
        })
    })
    return controls
}
