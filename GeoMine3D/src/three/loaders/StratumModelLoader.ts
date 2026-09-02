import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader'
import type { ModelItem } from '@/types'

// DRACO 解码器路径（CDN，支持 Draco 压缩的 GLB 文件）
const DRACO_DECODER_PATH = 'https://www.gstatic.com/draco/versioned/decoders/1.5.7/'

// 创建带 DRACO 支持的 GLTF 加载器。
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

    // 为地层分层按索引生成稳定颜色。
    private generateLayerColor(index: number): number {
        const colors = [
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
        return colors[index % colors.length]
    }

    // 加载地层模型并为每个网格注入渲染样式与业务元数据。
    // catalog 交付包模型携带 color_hex / local_coordinates / vertical_scale 元数据:
    // 单层模型直接使用地层配色与名称,局部高程按建议比例做竖向夸张(仅显示);
    // 合并模型通过 layer_colors / layer_names 按 mesh 名(L01…)映射每层样式。
    async load(model: ModelItem): Promise<THREE.Group> {
        const meta: Record<string, any> = model.metadata ?? {}
        const catalogColor = typeof meta.color_hex === 'string' && meta.color_hex
            ? new THREE.Color(meta.color_hex)
            : null
        const layerColors: Record<string, string> = meta.layer_colors ?? {}
        const layerNames: Record<string, string> = meta.layer_names ?? {}
        const verticalScale = typeof meta.vertical_scale === 'number' ? meta.vertical_scale : 1

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
                        const meshCode = (mesh.name || '').trim().toUpperCase()
                        const mappedColor = typeof layerColors[meshCode] === 'string' && layerColors[meshCode]
                            ? new THREE.Color(layerColors[meshCode])
                            : null
                        const layerColor = mappedColor ?? catalogColor ?? this.generateLayerColor(index)

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

                        const layerName = layerNames[meshCode]
                            || (meshes.length === 1
                                ? model.name
                                : (mesh.name?.trim() || `${model.name}_layer_${meshIndex + 1}`))
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

                    if (meta.local_coordinates && verticalScale !== 1) {
                        group.scale.z = verticalScale
                    }

                    resolve(group)
                },
                undefined,
                reject
            )
        })
    }
}
