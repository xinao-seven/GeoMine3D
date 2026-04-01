import * as THREE from 'three'

export class RendererManager {
  readonly renderer: THREE.WebGLRenderer

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      // 开启抗锯齿，减轻模型边缘锯齿感（会带来少量性能开销）
      antialias: true,
      // 不使用透明画布，避免额外的合成成本
      alpha: false,
      logarithmicDepthBuffer: true,  // 解决大尺度模型 z-fighting
    })
    // 适配高 DPI 屏，保证画面清晰度
    this.renderer.setPixelRatio(window.devicePixelRatio)
    // 启用阴影能力，具体投影与接收由材质/光源/物体单独控制
    this.renderer.shadowMap.enabled = true
    // 柔和阴影采样，边缘更平滑
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    // 输出到 sRGB，和大多数贴图/显示设备色域一致
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    // 胶片式色调映射，压缩高亮区域避免过曝
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    // 曝光强度，1.0 表示使用基准曝光
    this.renderer.toneMappingExposure = 1.0
    // 全局裁剪面容器，配合剖切工具动态写入
    this.renderer.clippingPlanes = []
    // 默认关闭局部裁剪，避免影响普通渲染路径
    this.renderer.localClippingEnabled = false
  }

  // 更新渲染器输出尺寸。
  resize(width: number, height: number) {
    this.renderer.setSize(width, height)
  }

  // 执行单帧渲染。
  render(scene: THREE.Scene, camera: THREE.Camera) {
    this.renderer.render(scene, camera)
  }

  // 释放 WebGL 渲染资源。
  dispose() {
    this.renderer.dispose()
  }
}
