import * as THREE from 'three'

/**
 * 远程控制桥：把场景引擎的关键能力暴露到 `window.__geomine`，
 * 供浏览器控制台、自动化截图脚本和演示工具调用。
 *
 * 安装条件：开发环境，或 URL 显式带 `?remote=1`（生产构建下默认不安装）。
 *
 * 典型用法（浏览器控制台）：
 *   __geomine.setView({ azimuth: 45, elevation: 35, distanceFactor: 1.2 })
 *   __geomine.setStrataColors({ '煤3-1': '#333333' })
 *   __geomine.enableClip({ axis: 'x', position: 0, keepLower: true })
 *   const dataUrl = __geomine.capture({ background: '#ffffff', pixelRatio: 2 })
 */
export interface RemoteControlOptions {
    sceneManager: any
    cameraManager: any
    rendererManager: any
    controlsManager: any
    modelManager: any
    getClipTool: () => any
    getExplodeTool: () => any
    getGizmoTool: () => any
    getSceneStore: () => any
    getSettlementStore?: () => any
    getSettlementManager?: () => any
}

export function installRemoteControl(options: RemoteControlOptions) {
    const enabled = import.meta.env.DEV ||
        new URLSearchParams(window.location.search).has('remote')
    if (!enabled) return

    const { sceneManager, cameraManager, rendererManager, controlsManager, modelManager } = options

    const scene = () => sceneManager.scene as THREE.Scene
    const camera = () => cameraManager.camera as THREE.PerspectiveCamera
    const store = () => options.getSceneStore()

    function modelBox(): THREE.Box3 {
        const box = new THREE.Box3()
        for (const m of modelManager.getAllModels()) box.expandByObject(m.object)
        return box
    }

    function fitParams(box: THREE.Box3, factor: number) {
        const center = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        const maxDim = Math.max(size.x, size.y, size.z)
        const fov = THREE.MathUtils.degToRad(camera().fov)
        const fitDistance = Math.max(Math.abs(maxDim / 2 / Math.tan(fov / 2)) * 2.0, 300) * factor
        return { center, fitDistance }
    }

    function applyPose(position: THREE.Vector3, target: THREE.Vector3) {
        const box = modelBox()
        if (!box.isEmpty()) {
            const fit = cameraManager.fitToBox(box)
            if (fit) {
                camera().near = fit.near
                camera().far = fit.far
            }
        }
        camera().position.copy(position)
        camera().updateProjectionMatrix()
        controlsManager.controls.target.copy(target)
        controlsManager.controls.update()
    }

    const api = {
        /** 场景概况：已加载模型、地层控制项、相机与坐标原点 */
        info() {
            const box = modelBox()
            return {
                models: modelManager.getAllModels().map((m: any) => ({ id: m.id, name: m.name, type: m.type })),
                strata: api.listStrata(),
                camera: {
                    position: camera().position.toArray(),
                    target: controlsManager.controls.target.toArray(),
                    fov: camera().fov,
                },
                box: box.isEmpty() ? null : {
                    min: box.min.toArray(), max: box.max.toArray(),
                    center: box.getCenter(new THREE.Vector3()).toArray(),
                    size: box.getSize(new THREE.Vector3()).toArray(),
                },
                origin: store().coordinateOrigin,
                verticalScale: store().verticalScale,
            }
        },

        /** 当前地层单元控制项（key/layerName/颜色/透明度/显隐） */
        listStrata() {
            return (store().stratumLayers || []).map((l: any) => ({
                key: l.key, layerName: l.layerName, visible: l.visible, opacity: l.opacity, color: l.color,
            }))
        },

        /**
         * 球坐标设置相机。azimuth 为绕世界竖轴的方位角（度），
         * elevation 为仰角（度，0 = 平视，90 = 正俯视），distanceFactor 相对“适配全场景”距离的倍数。
         */
        setView(opts: { azimuth?: number; elevation?: number; distanceFactor?: number; target?: number[] } = {}) {
            const { azimuth = 45, elevation = 35, distanceFactor = 1.15, target } = opts
            const box = modelBox()
            if (box.isEmpty()) return { error: 'no models loaded' }
            const { center, fitDistance } = fitParams(box, distanceFactor)
            const t = target ? new THREE.Vector3(...target) : center
            const az = THREE.MathUtils.degToRad(azimuth)
            const el = THREE.MathUtils.degToRad(THREE.MathUtils.clamp(elevation, -89, 89))
            const position = new THREE.Vector3(
                t.x + fitDistance * Math.cos(el) * Math.cos(az),
                t.y + fitDistance * Math.sin(el),
                t.z + fitDistance * Math.cos(el) * Math.sin(az),
            )
            applyPose(position, t)
            return { position: position.toArray(), target: t.toArray(), fitDistance }
        },

        /** 适配全场景（factor>1 更远，<1 更近） */
        fitView(factor = 1) {
            const box = modelBox()
            if (box.isEmpty()) return { error: 'no models loaded' }
            const { center, fitDistance } = fitParams(box, factor)
            const dir = camera().position.clone().sub(center).normalize()
            applyPose(center.clone().add(dir.multiplyScalar(fitDistance)), center)
            return { position: camera().position.toArray(), target: center.toArray() }
        },

        /** 读取当前相机位姿（可用 setCamera 恢复） */
        getView() {
            return {
                position: camera().position.toArray(),
                target: controlsManager.controls.target.toArray(),
            }
        },

        /** 直接设置相机位置与观察点 */
        setCamera(position: number[], target: number[]) {
            applyPose(new THREE.Vector3(...position), new THREE.Vector3(...target))
            return api.getView()
        },

        /** 场景背景色（hex）；传 null 恢复默认 */
        setBackground(hex: string | null) {
            const prev = scene().background
            scene().background = hex ? new THREE.Color(hex) : null
            return prev
        },

        /** 色调映射曝光（1 = 默认） */
        setExposure(value: number) {
            rendererManager.renderer.toneMappingExposure = value
        },

        /**
         * 渲染一帧并导出 PNG dataURL。
         * background/pixelRatio/exposure/hideGizmo 仅在本帧生效，调用后恢复。
         */
        capture(opts: { background?: string | null; pixelRatio?: number; exposure?: number; hideGizmo?: boolean } = {}) {
            const { background = null, pixelRatio = 0, exposure = 0, hideGizmo = true } = opts
            const renderer = rendererManager.renderer
            const prevBg = scene().background
            const prevExposure = renderer.toneMappingExposure
            const prevRatio = renderer.getPixelRatio()
            const gizmo = options.getGizmoTool()
            const gizmoSupportsHide = gizmo && typeof gizmo.setHidden === 'function'

            if (background) scene().background = new THREE.Color(background)
            if (exposure) renderer.toneMappingExposure = exposure
            if (gizmoSupportsHide && hideGizmo) gizmo.setHidden(true)

            const size = renderer.getSize(new THREE.Vector2())
            if (pixelRatio && pixelRatio !== prevRatio) {
                renderer.setPixelRatio(pixelRatio)
                rendererManager.resize(size.x, size.y)
            }

            rendererManager.render(scene(), camera())
            const url = renderer.domElement.toDataURL('image/png')

            if (pixelRatio && pixelRatio !== prevRatio) {
                renderer.setPixelRatio(prevRatio)
                rendererManager.resize(size.x, size.y)
            }
            scene().background = prevBg
            renderer.toneMappingExposure = prevExposure
            if (gizmoSupportsHide && hideGizmo) gizmo.setHidden(false)
            return url
        },

        /** 批量设置地层颜色：{ 层名子串: '#rrggbb' } */
        setStrataColors(map: Record<string, string>) {
            for (const [name, color] of Object.entries(map)) {
                api.setStratumColor(name, color)
            }
            return api.listStrata()
        },

        /** 按层名/key 子串匹配（不区分大小写）设置单个地层颜色 */
        setStratumColor(match: string, color: string) {
            for (const key of findLayerKeys(match)) store().updateStratumLayer(key, { color })
        },

        setStratumOpacity(match: string, opacity: number) {
            for (const key of findLayerKeys(match)) store().updateStratumLayer(key, { opacity })
        },

        setStratumVisible(match: string, visible: boolean) {
            for (const key of findLayerKeys(match)) store().updateStratumLayer(key, { visible })
        },

        /** 一级图层显隐：type ∈ stratum | borehole | workingface | roadway */
        setLayerVisible(type: string, visible: boolean) {
            store().setLayerVisible(type, visible)
        },

        /** 一级图层整体透明度系数（0.05~1） */
        setGroupOpacity(type: string, value: number) {
            store().setGroupOpacity(type, value)
        },

        /** 地层边缘线 */
        setShowEdges(visible: boolean) {
            store().setShowEdges(visible)
        },

        /** 全场景竖向夸张倍数（基准值见 info().origin.verticalScale） */
        setVerticalScale(value: number) {
            store().setVerticalScale(value)
        },

        /** 启用三轴剖切；position 为场景局部坐标（y 轴为夸张后高程） */
        enableClip(opts: { axis?: 'x' | 'y' | 'z'; position?: number; keepLower?: boolean } = {}) {
            const { axis = 'x', position = 0, keepLower = true } = opts
            store().activateTool('clip')
            store().setClipAxis(axis)
            store().setClipHeight(position)
            store().setClipKeepLower(keepLower)
            return store().toolState
        },

        disableClip() {
            store().activateTool(null)
            return store().toolState
        },

        /** 地层炸开（gap 为世界显示单位） */
        setExplode(on?: boolean, gap?: number) {
            const tool = options.getExplodeTool()
            if (!tool) return { error: 'explode tool not ready' }
            if (gap !== undefined) tool.setGap(Number(gap))
            if (on !== undefined && tool.isExploded() !== Boolean(on)) tool.toggle()
            return { exploded: tool.isExploded(), gap: tool.gap }
        },

        /** 选中一个地层（属性检查器 + 描边高亮） */
        selectByLayer(match: string) {
            const key = findLayerKeys(match)[0]
            if (!key) return { error: `layer not found: ${match}` }
            let found: THREE.Mesh | null = null
            for (const m of modelManager.getModelsByType('stratum')) {
                m.object.traverse((child: any) => {
                    if (!found && child.isMesh && String(child.userData?.id) === key) found = child
                })
            }
            if (!found) return { error: `mesh not found for key: ${key}` }
            const mesh = found as unknown as THREE.Mesh
            store().selectObject({
                id: mesh.userData.id,
                name: String(mesh.userData.name ?? mesh.userData.layerName ?? key),
                type: 'stratum',
                data: mesh.userData.modelData ?? {},
            })
            rendererManager.setOutlineEnabled(true)
            rendererManager.setOutlineSelectedObjects([mesh])
            return { id: key, name: String(mesh.userData.name ?? key) }
        },

        clearSelection() {
            store().selectObject(null)
            rendererManager.setOutlineSelectedObjects([])
        },

        /** 求某地层包围盒中心的屏幕坐标（配合外部坐标点击） */
        projectLayer(match: string) {
            const key = findLayerKeys(match)[0]
            if (!key) return null
            let found: THREE.Mesh | null = null
            for (const m of modelManager.getModelsByType('stratum')) {
                m.object.traverse((child: any) => {
                    if (!found && child.isMesh && String(child.userData?.id) === key) found = child
                })
            }
            if (!found) return null
            const mesh = found as unknown as THREE.Mesh
            const center = new THREE.Box3().setFromObject(mesh).getCenter(new THREE.Vector3())
            const p = center.clone().project(camera())
            const size = rendererManager.renderer.getSize(new THREE.Vector2())
            return {
                x: (p.x + 1) / 2 * size.x,
                y: (1 - p.y) / 2 * size.y,
                world: center.toArray(),
            }
        },

        /** 引擎原始句柄（调试用） */
        handles: {
            sceneManager, cameraManager, rendererManager, controlsManager, modelManager,
            get store() { return store() },
            get clipTool() { return options.getClipTool() },
            get explodeTool() { return options.getExplodeTool() },
            get gizmoTool() { return options.getGizmoTool() },
            get settlementStore() { return options.getSettlementStore?.() },
            get settlementManager() { return options.getSettlementManager?.() },
        },

        /** 沉陷位移场对比控制 */
        settlement: {
            enable(on: boolean) {
                const s = options.getSettlementStore?.()
                if (!s) return { error: 'settlement store not ready' }
                s.enabled = Boolean(on)
                return { enabled: s.enabled }
            },
            /** time: 0=沉陷前, 1=沉陷后; exaggeration: 纯显示端夸大; colorMode: original|dz|magnitude */
            set(opts: { time?: number; exaggeration?: number; colorMode?: 'original' | 'dz' | 'magnitude' } = {}) {
                const s = options.getSettlementStore?.()
                if (!s) return { error: 'settlement store not ready' }
                if (opts.time !== undefined) s.time = Math.min(1, Math.max(0, opts.time))
                if (opts.exaggeration !== undefined) s.exaggeration = opts.exaggeration
                if (opts.colorMode) s.colorMode = opts.colorMode
                return api.settlement.info()
            },
            info() {
                const s = options.getSettlementStore?.()
                if (!s) return { error: 'settlement store not ready' }
                return {
                    enabled: s.enabled, time: s.time, exaggeration: s.exaggeration, colorMode: s.colorMode,
                    maxSubsidenceM: s.maxSubsidenceM, maxHorizontalM: s.maxHorizontalM,
                    displayZScale: s.displayZScale, workingsFollow: s.workingsFollow,
                    boundLayers: s.boundLayers, boundVertices: s.boundVertices,
                    appliedMaxDz: s.appliedMaxDz, loadError: s.loadError,
                    bindIssues: s.bindIssues,
                }
            },
        },
    }

    function findLayerKeys(match: string): string[] {
        const needle = String(match).toLowerCase()
        return (store().stratumLayers || [])
            .filter((l: any) =>
                String(l.layerName).toLowerCase().includes(needle) ||
                String(l.key).toLowerCase().includes(needle))
            .map((l: any) => l.key)
    }

    ;(window as any).__geomine = api
    console.info('[GeoMine3D] 远程控制桥已安装：window.__geomine')
}
