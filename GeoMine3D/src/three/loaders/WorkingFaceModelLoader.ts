import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader'
import type { ModelItem } from '@/types'

const DRACO_DECODER_PATH = 'https://www.gstatic.com/draco/versioned/decoders/1.5.7/'

// 创建带 DRACO 解码能力的 GLTF 加载器。
function createLoader(): GLTFLoader {
  const loader = new GLTFLoader()
  const dracoLoader = new DRACOLoader()
  dracoLoader.setDecoderPath(DRACO_DECODER_PATH)
  dracoLoader.preload()
  loader.setDRACOLoader(dracoLoader)
  return loader
}

export class WorkingFaceModelLoader {
  private loader = createLoader()

  // 将来源材质转换为偏哑光的统一材质风格。
  // overrideColor 用于 catalog 指定的整体配色(如巷道 #1F3A5F);
  // 顶点色(工作面按回采年份分组)原样保留。
  private createMatteMaterial(sourceMat: any, overrideColor?: THREE.Color): THREE.Material {
    const matte = new THREE.MeshPhongMaterial({
      color: overrideColor ?? (sourceMat?.color ? sourceMat.color.clone() : new THREE.Color(0xf5a623)),
      vertexColors: !!sourceMat?.vertexColors,
      transparent: !!sourceMat?.transparent,
      opacity: typeof sourceMat?.opacity === 'number' ? sourceMat.opacity : 1,
      side: sourceMat?.side ?? THREE.FrontSide,
      shininess: 10,
      specular: new THREE.Color(0x1a1a1a),
      clipShadows: true,
    })
    matte.clippingPlanes = []

    if (sourceMat?.map) {
      matte.map = sourceMat.map
      if (matte.map) {
        matte.map.colorSpace = THREE.SRGBColorSpace
      }
    }

    return matte
  }

  // 加载井巷工程模型(工作面/巷道)并替换为统一材质表现。
  // catalog 交付包模型为局部米制坐标,按建议比例做竖向夸张(仅显示)。
  async load(model: ModelItem): Promise<THREE.Group> {
    const meta: Record<string, any> = model.metadata ?? {}
    const overrideColor = typeof meta.color_hex === 'string' && meta.color_hex
      ? new THREE.Color(meta.color_hex)
      : undefined
    const verticalScale = typeof meta.vertical_scale === 'number' ? meta.vertical_scale : 1

    return new Promise((resolve, reject) => {
      this.loader.load(
        model.fileUrl,
        (gltf) => {
          const group = gltf.scene
          group.name = `workingface_${model.id}`
          group.userData = { id: model.id, name: model.name, type: model.type, modelData: model }

          let meshIndex = 0
          group.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh
              if (Array.isArray(mesh.material)) {
                mesh.material = mesh.material.map((m: any) => this.createMatteMaterial(m, overrideColor))
              } else {
                mesh.material = this.createMatteMaterial(mesh.material as any, overrideColor)
              }
              const meshName = mesh.name?.trim() || `${model.name}_${meshIndex + 1}`
              mesh.userData = {
                id: `${model.id}::${meshName}`,
                name: meshName,
                type: model.type,
                modelData: model,
                modelId: model.id,
              }
              meshIndex += 1
            }
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
