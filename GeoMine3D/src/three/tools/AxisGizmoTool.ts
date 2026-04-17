import * as THREE from 'three'

interface AxisGizmoToolOptions {
    size?: number
    padding?: number
}

export class AxisGizmoTool {
    private readonly renderer: THREE.WebGLRenderer
    private readonly mainCamera: THREE.Camera
    private readonly geoRoot: THREE.Object3D
    private readonly size: number
    private readonly padding: number

    private readonly scene: THREE.Scene
    private readonly camera: THREE.PerspectiveCamera
    private readonly root: THREE.Group
    private readonly cameraInvQuat = new THREE.Quaternion()
    private readonly geoRootQuat = new THREE.Quaternion()
    private resources: Array<THREE.Material | THREE.Texture> = []

    constructor(
        renderer: THREE.WebGLRenderer,
        mainCamera: THREE.Camera,
        geoRoot: THREE.Object3D,
        options: AxisGizmoToolOptions = {}
    ) {
        this.renderer = renderer
        this.mainCamera = mainCamera
        this.geoRoot = geoRoot
        this.size = options.size ?? 110
        this.padding = options.padding ?? 12

        this.scene = new THREE.Scene()
        this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200)
        this.camera.position.set(0, 0, 80)
        this.camera.lookAt(0, 0, 0)

        const ambient = new THREE.AmbientLight(0xffffff, 0.9)
        const directional = new THREE.DirectionalLight(0xffffff, 0.6)
        directional.position.set(20, 30, 40)
        this.scene.add(ambient, directional)

        this.root = new THREE.Group()
        this.scene.add(this.root)

        const axes = new THREE.AxesHelper(24)
        this.root.add(axes)

        const xLabel = this.createAxisLabelSprite('X', '#ff5e5e')
        const yLabel = this.createAxisLabelSprite('Y', '#52d273')
        const zLabel = this.createAxisLabelSprite('Z', '#4e90ff')

        if (xLabel) {
            xLabel.position.set(30, 0, 0)
            this.root.add(xLabel)
        }
        if (yLabel) {
            yLabel.position.set(0, 30, 0)
            this.root.add(yLabel)
        }
        if (zLabel) {
            zLabel.position.set(0, 0, 30)
            this.root.add(zLabel)
        }
    }

    render() {
        this.cameraInvQuat.copy(this.mainCamera.quaternion).invert()
        this.geoRoot.getWorldQuaternion(this.geoRootQuat)
        this.root.quaternion.copy(this.cameraInvQuat).multiply(this.geoRootQuat)

        const rendererSize = this.renderer.getSize(new THREE.Vector2())
        const viewportSize = Math.min(this.size, Math.floor(Math.min(rendererSize.x, rendererSize.y) * 0.26))
        const viewportX = this.padding
        const viewportY = this.padding

        const previousAutoClear = this.renderer.autoClear
        this.renderer.autoClear = false
        this.renderer.clearDepth()

        this.renderer.setScissorTest(true)
        this.renderer.setViewport(viewportX, viewportY, viewportSize, viewportSize)
        this.renderer.setScissor(viewportX, viewportY, viewportSize, viewportSize)
        this.renderer.render(this.scene, this.camera)
        this.renderer.setScissorTest(false)

        this.renderer.setViewport(0, 0, rendererSize.x, rendererSize.y)
        this.renderer.autoClear = previousAutoClear
    }

    dispose() {
        for (const resource of this.resources) {
            resource.dispose()
        }
        this.resources = []
        this.scene.clear()
    }

    private createAxisLabelSprite(text: string, color: string) {
        const canvas = document.createElement('canvas')
        canvas.width = 128
        canvas.height = 128
        const ctx = canvas.getContext('2d')
        if (!ctx) return null

        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.font = 'bold 72px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillStyle = color
        ctx.fillText(text, canvas.width / 2, canvas.height / 2)

        const texture = new THREE.CanvasTexture(canvas)
        texture.needsUpdate = true
        const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false })
        const sprite = new THREE.Sprite(material)
        sprite.scale.set(12, 12, 12)

        this.resources.push(texture, material)
        return sprite
    }
}
