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
  private createMatteMaterial(sourceMat: any): THREE.Material {
    const matte = new THREE.MeshPhongMaterial({
      color: sourceMat?.color ? sourceMat.color.clone() : new THREE.Color(0xf5a623),
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

  // 加载工作面模型并替换为统一材质表现。
  async load(model: ModelItem): Promise<THREE.Group> {
    return new Promise((resolve, reject) => {
      this.loader.load(
        model.fileUrl,
        (gltf) => {
          const group = gltf.scene
          group.name = `workingface_${model.id}`
          group.userData = { id: model.id, name: model.name, type: 'workingface', modelData: model }

          group.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh
              if (Array.isArray(mesh.material)) {
                mesh.material = mesh.material.map((m: any) => this.createMatteMaterial(m))
              } else {
                mesh.material = this.createMatteMaterial(mesh.material as any)
              }
            }
          })

          resolve(group)
        },
        undefined,
        reject
      )
    })
  }
}
