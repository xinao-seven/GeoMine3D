<template>
    <div class="model-viewer" ref="container"></div>
</template>

<script>
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js';
import { markRaw } from 'vue';
import { getApiBaseUrl } from '@/utils/api';

export default {
    name: 'ModelViewer',

    beforeCreate() {

        this._scene = null;
        this._camera = null;
        this._renderer = null;
        this._controls = null;
        this._model = null;
        this._labelRenderer = null;
        this._axesHelper = null;
        this._gridHelper = null;
        this._originalMaterials = new Map();
        this._boundingBox = null;
        this._clippingPlane = null;
        this._clippingHelper = null;
        this._transformControls = null;
        this._coordinateBox = null;
    },
    data() {
        return {

            modelLayers: [],
            wireframeMode: false,
            animationId: null,
            edgeLines: [], // 存储边缘线对象
            edgeColor: 0x000000,
            showEdges: false,
            coordinateLabels: [],
            showCoordinateAxis: false,
            axisColor: 0x333333,
            clippingPlanes: [],
            showClipping: false,
            controlTarget: 'model',
            sectionGeometry: null,
            sectionLines: [],
            currentBlobUrl: null,
            loading: false,
            error: null,
            currentModelPath: null,
            currentModelFileName: null
        }
    },
    mounted() {
        this.initThreeJS();
        this.animate();
        window.addEventListener('resize', this.handleResize);

        // 监听来自控制面板的事件
        this.$eventBus.$on('load-model', this.loadModel);
        this.$eventBus.$on('clear-model', this.clearModel);
        this.$eventBus.$on('reset-camera', this.resetCamera);
        this.$eventBus.$on('toggle-wireframe', this.toggleWireframe);
        this.$eventBus.$on('update-edge-color', this.setEdgeColor);
        this.$eventBus.$on('set-view', this.setView);
        this.$eventBus.$on('toggle-layer-visibility', this.handleToggleLayerVisibility);
        this.$eventBus.$on('update-layer-opacity', this.handleUpdateLayerOpacity);
        this.$eventBus.$on('toggle-coordinate-axis', this.toggleCoordinateAxis);
        this.$eventBus.$on('update-axis-color', this.setAxisColor);
        this.$eventBus.$on('update-layer-color', this.handleUpdateLayerColor);
        // 剖面相关事件
        this.$eventBus.$on('toggle-clipping', this.toggleClipping);
        this.$eventBus.$on('align-clipping-plane', this.alignClippingPlane);
        this.$eventBus.$on('set-transform-mode', this.setTransformMode);
        this.$eventBus.$on('set-control-target', this.setControlTarget);
        this.$eventBus.$on('generate-section', this.generateSection);
        this.$eventBus.$on('export-section', this.exportSection);
    },
    beforeUnmount() {
        window.removeEventListener('resize', this.handleResize);
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }

        // 清理事件监听器
        this.$eventBus.$off('load-model', this.loadModel);
        this.$eventBus.$off('clear-model', this.clearModel);
        this.$eventBus.$off('reset-camera', this.resetCamera);
        this.$eventBus.$off('toggle-wireframe', this.toggleWireframe);
        this.$eventBus.$off('update-edge-color', this.setEdgeColor);
        this.$eventBus.$off('set-view', this.setView);
        this.$eventBus.$off('toggle-layer-visibility', this.handleToggleLayerVisibility);
        this.$eventBus.$off('update-layer-opacity', this.handleUpdateLayerOpacity);
        this.$eventBus.$off('toggle-coordinate-axis', this.toggleCoordinateAxis);
        this.$eventBus.$off('update-axis-color', this.setAxisColor);
        this.$eventBus.$off('update-layer-color', this.handleUpdateLayerColor);
        // 清理剖面相关事件
        this.$eventBus.$off('toggle-clipping', this.toggleClipping);
        this.$eventBus.$off('align-clipping-plane', this.alignClippingPlane);
        this.$eventBus.$off('set-transform-mode', this.setTransformMode);
        this.$eventBus.$off('set-control-target', this.setControlTarget);
        this.$eventBus.$off('generate-section', this.generateSection);
        this.$eventBus.$off('export-section', this.exportSection);

        this.cleanup();
    },
    watch: {
        showEdges(show) {
            this.modelLayers.forEach(layer => {
                if (layer.mesh && layer.mesh.userData.edgeLines) {
                    layer.mesh.userData.edgeLines.visible = show && layer.visible;
                }
            });
        },
        edgeColor(color) {
            this.modelLayers.forEach(layer => {
                if (layer.mesh && layer.mesh.userData.edgeLines && layer.mesh.userData.edgeLines.material) {
                    layer.mesh.userData.edgeLines.material.color.setHex(color);
                }
            });
        },
        showCoordinateAxis(enabled) {
            if (enabled) {
                this.createCoordinateAxis();
            } else {
                this.clearCoordinateAxis();
            }
            this.$eventBus.$emit('coordinate-axis-changed', enabled);
        },
        axisColor(color) {
            if (this._coordinateBox && this._coordinateBox.material) {
                this._coordinateBox.material.color.setHex(color);
            }

            this.coordinateLabels.forEach(label => {
                if (label.element) {
                    label.element.style.color = `#${color.toString(16).padStart(6, '0')}`;
                }
            });
        },
        showClipping(enabled) {
            if (this._clippingHelper) {
                this._clippingHelper.visible = enabled;
            }

            if (!enabled) {
                this.clearSectionLines();
                this.controlTarget = 'model';
                this.$eventBus.$emit('control-target-changed', 'model');
            }

            this.updateControlMode();
            this.$eventBus.$emit('clipping-changed', enabled);
        },
        controlTarget() {
            this.updateControlMode();
        }
    },
    methods: {
        /**
         * 初始化Three.js场景
         */
        initThreeJS() {
            const container = this.$refs.container;
            const width = container.clientWidth;
            const height = container.clientHeight;

            // 创建场景 - 直接赋值给 this._scene（非响应式）
            this._scene = new THREE.Scene();
            this._scene.background = new THREE.Color(0xfafafa);

            // 创建相机
            this._camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
            this._camera.position.set(10, 10, 10);

            // 创建渲染器（添加对数深度缓冲）
            this._renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true });
            this._renderer.setClearColor(0xfafafa);
            this._renderer.setSize(width, height);
            this._renderer.physicallyCorrectLights = true;
            this._renderer.outputColorSpace = THREE.SRGBColorSpace;
            this._renderer.toneMapping = THREE.ACESFilmicToneMapping;
            this._renderer.toneMappingExposure = 1.0;
            this._renderer.shadowMap.enabled = true;
            this._renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            container.appendChild(this._renderer.domElement);

            // 创建CSS2D渲染器用于坐标轴标签
            this._labelRenderer = new CSS2DRenderer();
            this._labelRenderer.setSize(width, height);
            this._labelRenderer.domElement.style.position = 'absolute';
            this._labelRenderer.domElement.style.top = '0px';
            this._labelRenderer.domElement.style.pointerEvents = 'none';
            container.appendChild(this._labelRenderer.domElement);

            // 创建控制器
            this._controls = new OrbitControls(this._camera, this._renderer.domElement);
            this._controls.enableDamping = true;
            this._controls.dampingFactor = 0.2;
            this._controls.screenSpacePanning = false;
            this._controls.minDistance = 1;
            this._controls.maxDistance = 1000;
            this._controls.minPolarAngle = 0;
            this._controls.maxPolarAngle = Math.PI * 2;
            this._controls.enableRotate = true;
            this._controls.rotateSpeed = 1.0;

            // 添加光源
            this.setupLights();

            // 添加坐标轴辅助器
            this._axesHelper = new THREE.AxesHelper(3000);
            this._scene.add(this._axesHelper);

            // 添加网格辅助器
            this._gridHelper = new THREE.GridHelper(2000, 100, 0xdddddd, 0xf0f0f0);
            this._scene.add(this._gridHelper);

            // 初始化剖面功能
            this.initClippingPlane();
        },

        /**
         * 设置光源（参照备份文件 - 使用环境光避免阴影问题）
         */
        setupLights() {
            // 使用强环境光，避免阴影和光照复杂性（参照备份文件）
            const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
            this._scene.add(ambientLight);


        },
        /**
         * 动画循环
         */
        animate() {
            this.animationId = requestAnimationFrame(this.animate);

            if (this._controls) {
                this._controls.update();
            }

            if (this._renderer && this._scene && this._camera) {
                this._renderer.render(this._scene, this._camera);
                // 渲染坐标轴标签
                if (this._labelRenderer) {
                    this._labelRenderer.render(this._scene, this._camera);
                }
            }
        },

        /**
         * 加载GLTF模型
         * @param {string} modelPath - 模型文件路径或API端点，如果不提供则从后端API加载默认模型
         */
        async loadModel(modelPath = null) {
            try {
                this.$eventBus.$emit('loading-start');

                // 创建 GLTFLoader 并配置 DRACOLoader
                const loader = new GLTFLoader();

                // 配置 DRACOLoader（使用 Google CDN）
                const dracoLoader = new DRACOLoader();
                dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.7/');
                dracoLoader.preload();
                loader.setDRACOLoader(dracoLoader);

                // 如果没有指定路径，使用默认的模型API路径
                const apiPath = modelPath || '/api/model';


                // 保存当前模型路径和文件名
                this.currentModelPath = apiPath;
                // 从路径中提取文件名
                this.currentModelFileName = apiPath.split('/').pop() || 'model';

                const gltf = await this.loadGLTF(loader, apiPath);

                // 清除之前的模型
                this.clearModel();

                // 先保存到临时变量，避免直接将 Three.js 对象赋值给响应式属性
                const loadedModel = gltf.scene;

                // 确保模型可见
                loadedModel.visible = true;

                // 计算模型包围盒（在添加到场景前）
                const box = new THREE.Box3().setFromObject(loadedModel);
                console.log('模型包围盒:', {
                    min: box.min,
                    max: box.max,
                    size: box.getSize(new THREE.Vector3()),
                    center: box.getCenter(new THREE.Vector3())
                });

                const size = box.getSize(new THREE.Vector3());
                const maxDimension = Math.max(size.x, size.y, size.z);
                if (maxDimension < 1) {
                    const scale = 10 / maxDimension;
                    loadedModel.scale.setScalar(scale);

                    // 重新计算放大后的包围盒
                    box.setFromObject(loadedModel);
                }

                this._scene.add(loadedModel);

                this._model = markRaw(loadedModel);
                const meshes = [];
                this._model.traverse((child) => {
                    if (child.isMesh) {
                        meshes.push(child);
                    }
                });

                if (meshes.length === 0) {
                    console.warn('GLTF场景中没有找到任何网格对象');
                    return;
                }

                // 为每个网格优化材质和可见性
                meshes.forEach((mesh, index) => {
                    mesh.visible = true;



                    // 优化材质 - 使用MeshBasicMaterial避免光照问题
                    const originalMaterial = mesh.material;
                    const layerColor = this.generateLayerColor(index);

                    const basicMaterial = new THREE.MeshBasicMaterial({
                        color: layerColor,
                        transparent: true,
                        opacity: 1.0,
                        side: THREE.DoubleSide
                    });

                    // 如果原材质有纹理，保留纹理
                    if (originalMaterial && originalMaterial.map) {
                        basicMaterial.map = originalMaterial.map;
                    }

                    mesh.material = basicMaterial;

                    // 为每个网格创建对应的边缘线
                    const edges = new THREE.EdgesGeometry(mesh.geometry);
                    const edgesMaterial = new THREE.LineBasicMaterial({
                        color: this.edgeColor,
                        transparent: true,
                        opacity: 0.8
                    });
                    const edgeLines = new THREE.LineSegments(edges, edgesMaterial);
                    edgeLines.visible = this.showEdges;

                    // 将边缘线存储在网格的userData中，建立关联
                    mesh.userData.edgeLines = edgeLines;

                    // 将边缘线添加到模型中
                    this._model.add(edgeLines);
                    this.edgeLines.push(edgeLines);


                });

                // 解析地层（在材质处理之后）
                this.parseLayers(this._model);

                // 计算包围盒并调整相机
                this.fitCameraToModel();

                // 计算模型信息
                const modelInfo = this.calculateModelInfo();

                this.$eventBus.$emit('model-loaded', {
                    layers: this.modelLayers,
                    modelInfo: modelInfo
                });

                // 如果剖切平面已存在，更新其尺寸
                if (this._clippingHelper) {
                    this.updateClippingHelperSize();
                }
                // 移除初始坐标轴，但保持网格可见
                this._axesHelper.visible = false;

                // 更新网格位置到模型底部
                this.updateGridPosition(box);


            } catch (error) {
                console.error('模型加载失败:', error);
                console.error('错误详情:', error);
                this.$eventBus.$emit('loading-error', `模型加载失败: ${error.message}`);
            } finally {
                this.$eventBus.$emit('loading-end');
            }
        },

        /**
         * 从后端API加载GLTF模型
         * @param {GLTFLoader} loader - GLTF加载器实例
         * @param {string} path - API路径，默认为'/api/model'，也可以是完整的模型文件路径
         * @returns {Promise} GLTF对象
         */
        async loadGLTF(loader, path = '/api/model') {
            try {
                this.loading = true;
                this.error = null;


                let fullUrl;
                if (path.startsWith('http://') || path.startsWith('https://')) {
                    fullUrl = path;
                } else {
                    const baseUrl = getApiBaseUrl();
                    fullUrl = `${baseUrl}${path}`;
                }


                return new Promise((resolve, reject) => {
                    loader.load(
                        fullUrl,
                        (gltf) => {
                            this.loading = false;
                            resolve(gltf);
                        },
                        (progress) => {
                            const percent = progress.total > 0 ? (progress.loaded / progress.total) * 100 : 0;

                            this.$eventBus.$emit('loading-progress', percent);
                        },
                        (error) => {
                            console.error('GLTF加载错误:', error);

                            this.loading = false;
                            this.error = `模型加载失败: ${error.message}`;
                            reject(error);
                        }
                    );
                });

            } catch (error) {
                console.error('从API获取模型失败:', error);
                this.loading = false;
                this.error = `获取模型失败: ${error.message}`;
                throw error;
            }
        },

        /**
         * 解析模型中的地层,向控制控件传递数据用于双向绑定
         * @param {THREE.Object3D} model - 3D模型对象
         */
        parseLayers(model) {
            this.modelLayers = [];
            this._originalMaterials.clear();

            model.traverse((child) => {
                if (child.isMesh) {
                    const layerName = child.name || `Layer_${this.modelLayers.length + 1}`;

                    // 保存原始材质
                    if (child.material) {
                        this._originalMaterials.set(child.uuid, child.material.clone());
                    }

                    // 获取当前材质颜色或生成默认颜色
                    let currentColor = '#ff0000'; // 默认红色
                    if (child.material && child.material.color) {
                        currentColor = `#${child.material.color.getHexString()}`;
                    } else {
                        // 生成基于索引的颜色
                        const hue = (this.modelLayers.length * 137.5) % 360;
                        const color = new THREE.Color().setHSL(hue / 360, 0.7, 0.5);
                        currentColor = `#${color.getHexString()}`;
                    }

                    const layer = {
                        id: child.uuid,
                        name: layerName,
                        mesh: child,
                        visible: true,
                        opacity: 1.0,
                        color: currentColor
                    };

                    this.modelLayers.push(layer);
                }
            });


        },

        /**
         * 计算模型信息
         * @returns {Object} 模型统计信息
         */
        calculateModelInfo() {
            let totalVertices = 0;
            let totalFaces = 0;

            if (this._model) {
                this._model.traverse((child) => {
                    if (child.isMesh && child.geometry) {
                        const geometry = child.geometry;
                        if (geometry.attributes.position) {
                            totalVertices += geometry.attributes.position.count;
                        }
                        if (geometry.index) {
                            totalFaces += geometry.index.count / 3;
                        }
                    }
                });
            }

            return {
                fileName: this.currentModelFileName || 'output_model.gltf',
                vertices: totalVertices.toLocaleString(),
                faces: Math.floor(totalFaces).toLocaleString()
            };
        },

        /**
         * 调整相机以适应模型
         */
        fitCameraToModel() {
            if (!this._model) return;

            // 计算所有网格的包围盒
            const box = new THREE.Box3();

            // 确保每个mesh都计算了包围盒
            this._model.traverse((child) => {
                if (child.isMesh && child.geometry) {
                    child.geometry.computeBoundingBox();
                    box.expandByObject(child);
                }
            });

            this._boundingBox = box;




            if (box.isEmpty()) {
                console.warn('边界框为空，无法调整相机');
                this._camera.position.set(50, 50, 50);
                this._camera.lookAt(0, 0, 0);
                this._controls.target.set(0, 0, 0);
                this._controls.update();
                return;
            }

            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);

            console.log('模型信息:', {
                center: center,
                size: size,
                maxDimension: maxDim
            });

            // 计算相机距离（参照备份文件的计算方式）
            const fov = this._camera.fov * (Math.PI / 180);
            const cameraDistance = Math.abs(maxDim / 2 / Math.tan(fov / 2)) * 2.0;

            // 设置相机位置（默认等轴测视图 - 提供良好的整体视角）
            this._camera.position.set(
                center.x + cameraDistance * 0.7,
                center.y + cameraDistance * 0.7,
                center.z + cameraDistance * 0.7
            );

            // 设置相机目标
            this._controls.target.copy(center);
            this._camera.lookAt(center);

            // 更新相机的near和far平面
            this._camera.near = cameraDistance / 100;
            this._camera.far = cameraDistance * 10;
            this._camera.updateProjectionMatrix();

            // 更新控制器约束
            this._controls.minDistance = cameraDistance * 0.1;
            this._controls.maxDistance = cameraDistance * 5;

            // 更新控制器
            this._controls.update();

            console.log('相机调整完成:', {
                center: center,
                size: size,
                maxDimension: maxDim,
                cameraDistance: cameraDistance,
                cameraPosition: this._camera.position.clone(),
                targetPosition: this._controls.target.clone(),
                near: this._camera.near,
                far: this._camera.far
            });

            // 如果坐标轴开启，则创建坐标轴
            if (this.showCoordinateAxis) {
                this.createCoordinateAxis();
            }

            // 添加延时检查
            setTimeout(() => {
                this.checkModelVisibility();
            }, 100);
        },

        /**
         * 检查模型是否可见
         */
        checkModelVisibility() {
            if (!this._model) return;

            let visibleMeshes = 0;

            this._model.traverse((child) => {
                if (child.isMesh) {
                    if (child.visible) {
                        visibleMeshes++;
                    }
                    console.log('Mesh信息:', {
                        name: child.name,
                        visible: child.visible,
                        position: child.position,
                        scale: child.scale,
                        material: child.material ? child.material.constructor.name : 'no material'
                    });
                }
            });



            if (visibleMeshes === 0) {
                console.warn('没有可见的网格！模型可能存在问题。');
            }
        },

        /**
         * 更新网格位置到模型底部
         * @param {THREE.Box3} box - 模型包围盒
         */
        updateGridPosition(box) {
            if (!this._gridHelper || !box) return;

            // 获取模型的尺寸和中心
            const size = box.getSize(new THREE.Vector3());
            const center = box.getCenter(new THREE.Vector3());

            // 将网格放置在模型的最底部（min.y）
            this._gridHelper.position.y = box.min.y;

            // 根据模型大小调整网格尺寸
            // 使网格略大于模型以提供更好的视觉参考
            const gridSize = Math.max(size.x, size.z) * 1.5;

            // 移除旧的网格并创建新的
            this._scene.remove(this._gridHelper);

            // 创建新的网格，divisions数量根据尺寸调整
            const divisions = Math.min(Math.max(Math.floor(gridSize / 20), 10), 100);
            this._gridHelper = new THREE.GridHelper(gridSize, divisions, 0xdddddd, 0xf0f0f0);
            this._gridHelper.position.y = box.min.y;
            this._scene.add(this._gridHelper);

            console.log('网格已更新到模型底部:', {
                gridY: box.min.y,
                gridSize: gridSize,
                divisions: divisions,
                modelSize: size,
                modelCenter: center
            });
        },

        /**
         * 清除模型
         */
        clearModel() {
            if (this._model) {
                this._scene.remove(this._model);

                // 清理几何体和材质
                this._model.traverse((child) => {
                    if (child.isMesh) {
                        if (child.geometry) {
                            child.geometry.dispose();
                        }
                        if (child.material) {
                            if (Array.isArray(child.material)) {
                                child.material.forEach(material => material.dispose());
                            } else {
                                child.material.dispose();
                            }
                        }
                    }
                });

                this._model = null;
                this.modelLayers = [];
                this._originalMaterials.clear();

                // 清除模型文件名信息
                this.currentModelPath = null;
                this.currentModelFileName = null;

                // 清除边缘线 - 通过地层关联清除
                this.modelLayers.forEach(layer => {
                    if (layer.mesh && layer.mesh.userData.edgeLines) {
                        const edgeLines = layer.mesh.userData.edgeLines;
                        if (edgeLines.geometry) edgeLines.geometry.dispose();
                        if (edgeLines.material) edgeLines.material.dispose();
                    }
                });
                this.edgeLines = [];

                // 重置网格到初始位置和尺寸
                this._scene.remove(this._gridHelper);
                this._gridHelper = new THREE.GridHelper(2000, 100, 0xdddddd, 0xf0f0f0);
                this._gridHelper.position.y = 0;
                this._scene.add(this._gridHelper);



                this.$eventBus.$emit('model-cleared');
            }
        },

        /**
         * 重置相机位置
         */
        resetCamera() {
            if (this._model && this._boundingBox) {
                this.fitCameraToModel();
            } else {
                // 默认位置 - 使用更远的距离
                this._camera.position.set(100, 100, 100);
                this._controls.target.set(0, 0, 0);
                this._controls.update();
            }
        },

        /**
         * 切换边缘线模式
         * @param {boolean} show - 是否显示边缘线
         */
        toggleWireframe(show) {
            this.showEdges = show;
        },

        /**
         * 更改边缘线颜色
         * @param {number} color - 新的颜色值
         */
        setEdgeColor(color) {
            this.edgeColor = color;
        },
        /**
         * 处理地层颜色更新
         * @param {Object} data - {layerId: string, color: number}
         */
        handleUpdateLayerColor(data) {
            const layer = this.modelLayers.find(l => l.id === data.layerId);
            if (layer && layer.mesh && layer.mesh.material) {
                layer.mesh.material.color.setHex(data.color);
                layer.color = `#${data.color.toString(16).padStart(6, '0')}`;
            }
        },

        /**
         * 设置视角
         * @param {string} viewType - 视角类型
         */
        setView(viewType) {
            if (!this._model || !this._boundingBox) {
                this.setDefaultViewAngle(viewType);
                return;
            }

            if (this._boundingBox.isEmpty()) {
                this.setDefaultViewAngle(viewType);
                return;
            }

            const center = this._boundingBox.getCenter(new THREE.Vector3());
            const size = this._boundingBox.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            const distance = maxDim * 2;

            let cameraPosition = new THREE.Vector3();

            switch (viewType) {
                case 'front':
                    // 前视图：从Z轴负方向看向正方向（看模型正面）
                    cameraPosition.set(center.x, center.y, center.z - distance);
                    break;
                case 'back':
                    // 后视图：从Z轴正方向看向负方向（看模型背面）
                    cameraPosition.set(center.x, center.y, center.z + distance);
                    break;
                case 'left':
                    // 左视图：从X轴负方向看向正方向（看模型左侧）
                    cameraPosition.set(center.x - distance, center.y, center.z);
                    break;
                case 'right':
                    // 右视图：从X轴正方向看向负方向（看模型右侧）
                    cameraPosition.set(center.x + distance, center.y, center.z);
                    break;
                case 'top':
                    // 顶视图：从Y轴正方向看向负方向（看模型顶部）
                    cameraPosition.set(center.x, center.y + distance, center.z);
                    break;
                case 'bottom':
                    // 底视图：从Y轴负方向看向正方向（看模型底部）
                    cameraPosition.set(center.x, center.y - distance, center.z);
                    break;
                case 'isometric':
                    // 等轴测视图：提供立体感的观察角度
                    cameraPosition.set(
                        center.x + distance * 0.7,
                        center.y + distance * 0.7,
                        center.z + distance * 0.7
                    );
                    break;
                default:
                    // 默认等轴测视图
                    cameraPosition.set(
                        center.x + distance * 0.7,
                        center.y - distance * 0.7,
                        center.z + distance * 0.7
                    );
            }

            // 使用动画移动相机
            this.animateCameraTo(cameraPosition, center);
        },

        /**
         * 设置默认视角（当没有模型时）
         * @param {string} viewType - 视角类型
         */
        setDefaultViewAngle(viewType) {
            const distance = 50;
            let cameraPosition = new THREE.Vector3();
            const center = new THREE.Vector3(0, 0, 0);

            switch (viewType) {
                case 'front':
                    // 前视图：从Z轴负方向看向正方向
                    cameraPosition.set(0, 0, -distance);
                    break;
                case 'back':
                    // 后视图：从Z轴正方向看向负方向
                    cameraPosition.set(0, 0, distance);
                    break;
                case 'left':
                    // 左视图：从X轴负方向看向正方向
                    cameraPosition.set(-distance, 0, 0);
                    break;
                case 'right':
                    // 右视图：从X轴正方向看向负方向
                    cameraPosition.set(distance, 0, 0);
                    break;
                case 'top':
                    // 顶视图：从Y轴正方向看向负方向
                    cameraPosition.set(0, distance, 0);
                    break;
                case 'bottom':
                    // 底视图：从Y轴负方向看向正方向
                    cameraPosition.set(0, -distance, 0);
                    break;
                case 'isometric':
                    // 等轴测视图
                    cameraPosition.set(distance * 0.7, distance * 0.7, distance * 0.7);
                    break;
                default:
                    // 默认等轴测视图
                    cameraPosition.set(distance * 0.7, distance * 0.7, distance * 0.7);
            }

            this.animateCameraTo(cameraPosition, center);
        },

        /**
         * 动画移动相机到目标位置
         * @param {THREE.Vector3} targetPosition - 目标位置
         * @param {THREE.Vector3} targetLookAt - 目标观察点
         */
        animateCameraTo(targetPosition, targetLookAt) {
            const startPosition = this._camera.position.clone();
            const startTarget = this._controls.target.clone();

            const duration = 1000; // 1秒动画
            const startTime = Date.now();

            const animate = () => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);

                // 使用easeInOutQuad缓动函数
                const easeProgress = progress < 0.5
                    ? 2 * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 2) / 2;

                // 插值相机位置
                this._camera.position.lerpVectors(startPosition, targetPosition, easeProgress);
                this._controls.target.lerpVectors(startTarget, targetLookAt, easeProgress);

                this._camera.lookAt(this._controls.target);
                this._controls.update();

                if (progress < 1) {
                    requestAnimationFrame(animate);
                }
            };

            animate();
        },

        /**
         * 生成地层颜色
         * @param {number} index - 地层索引
         * @returns {number} 颜色值
         */
        generateLayerColor(index) {
            const colors = [
                0x8B4513, // 马鞍棕色
                0xDAA520, // 金麦色
                0x2E8B57, // 海绿色
                0x4682B4, // 钢蓝色
                0xD2691E, // 巧克力色
                0x9ACD32, // 黄绿色
                0xCD853F, // 秘鲁色
                0x20B2AA, // 浅海绿色
                0x778899, // 浅石板灰
                0xF0E68C  // 卡其色
            ];
            return colors[index % colors.length];
        },

        /**
         * 切换地层可见性
         * @param {string} layerId - 地层ID
         * @param {boolean} visible - 是否可见
         */
        toggleLayerVisibility(layerId, visible) {
            const layer = this.modelLayers.find(l => l.id === layerId);
            if (layer && layer.mesh) {
                // 设置网格可见性
                layer.mesh.visible = visible;
                layer.visible = visible;

                // 同时设置对应边缘线的可见性
                if (layer.mesh.userData.edgeLines) {
                    // 边缘线的可见性取决于：地层可见 AND 边缘线开关打开
                    layer.mesh.userData.edgeLines.visible = visible && this.showEdges;
                }
            }
        },

        /**
         * 更新地层透明度
         * @param {string} layerId - 地层ID
         * @param {number} opacity - 透明度值 (0-1)
         */
        updateLayerOpacity(layerId, opacity) {
            const layer = this.modelLayers.find(l => l.id === layerId);
            if (layer && layer.mesh && layer.mesh.material) {
                const material = layer.mesh.material;

                // 设置透明度
                if (opacity < 1) {
                    material.transparent = true;
                    material.opacity = opacity;
                } else {
                    material.transparent = false;
                    material.opacity = 1;
                }

                // 同时更新边缘线的透明度
                if (layer.mesh.userData.edgeLines && layer.mesh.userData.edgeLines.material) {
                    layer.mesh.userData.edgeLines.material.opacity = Math.min(opacity + 0.2, 1.0);
                }

                layer.opacity = opacity;
                material.needsUpdate = true;
            }
        },

        /**
         * 处理窗口大小变化
         */
        handleResize() {
            const container = this.$refs.container;
            const width = container.clientWidth;
            const height = container.clientHeight;

            this._camera.aspect = width / height;
            this._camera.updateProjectionMatrix();

            this._renderer.setSize(width, height);

            if (this._labelRenderer) {
                this._labelRenderer.setSize(width, height);
            }
        },

        /**
         * 创建坐标轴包围盒和标签
         */
        createCoordinateAxis() {
            if (!this._model || !this._boundingBox) {
                console.warn('无法创建坐标轴：模型或包围盒不存在');
                return;
            }

            this.clearCoordinateAxis();

            const box = this._boundingBox;
            const min = box.min;
            const max = box.max;
            const size = box.getSize(new THREE.Vector3());

            // 创建包围盒线框
            const boxGeometry = new THREE.BoxGeometry(size.x, size.y, size.z);
            const boxEdges = new THREE.EdgesGeometry(boxGeometry);
            const boxMaterial = new THREE.LineBasicMaterial({
                color: this.axisColor,
                transparent: true,
                opacity: 0.8
            });

            this._coordinateBox = markRaw(new THREE.LineSegments(boxEdges, boxMaterial));
            this._coordinateBox.position.copy(box.getCenter(new THREE.Vector3()));
            this._scene.add(this._coordinateBox);

            // 创建坐标标签
            this.createAxisLabels(min, max, size);
        },

        /**
         * 创建坐标轴标签
         */
        createAxisLabels(min, max, size) {
            // 计算合适的刻度间隔
            const getTickInterval = (dimension) => {
                const magnitude = Math.floor(Math.log10(dimension));
                const normalized = dimension / Math.pow(10, magnitude);

                let interval;
                if (normalized <= 2) interval = 0.5;
                else if (normalized <= 5) interval = 1;
                else interval = 2;

                return interval * Math.pow(10, magnitude);
            };

            const xInterval = getTickInterval(size.x);
            const yInterval = getTickInterval(size.y);
            const zInterval = getTickInterval(size.z);

            // X轴标签 (沿着底部前边)
            this.createAxisTickLabels('x', min.x, max.x, xInterval, min.y, min.z);

            // Y轴标签 (沿着左侧前边)
            this.createAxisTickLabels('y', min.y, max.y, yInterval, min.x, min.z);

            // Z轴标签 (沿着左侧底边)
            this.createAxisTickLabels('z', min.z, max.z, zInterval, min.x, min.y);
        },

        /**
         * 创建单个轴的刻度标签
         */
        createAxisTickLabels(axis, minValue, maxValue, interval, fixedCoord1, fixedCoord2) {
            const start = Math.ceil(minValue / interval) * interval;
            const end = Math.floor(maxValue / interval) * interval;

            for (let value = start; value <= end; value += interval) {
                // 避免浮点数精度问题
                const roundedValue = Math.round(value / interval) * interval;

                const labelDiv = document.createElement('div');
                labelDiv.className = 'coordinate-label';
                labelDiv.textContent = roundedValue.toFixed(2);
                labelDiv.style.color = `#${this.axisColor.toString(16).padStart(6, '0')}`;
                labelDiv.style.fontSize = '12px';
                labelDiv.style.fontFamily = 'Arial, sans-serif';
                labelDiv.style.padding = '2px 4px';
                labelDiv.style.backgroundColor = 'rgba(0,0,0, 0)';
                labelDiv.style.borderRadius = '3px';
                labelDiv.style.pointerEvents = 'none';

                const label = new CSS2DObject(labelDiv);

                // 根据轴设置位置
                switch (axis) {
                    case 'x':
                        label.position.set(roundedValue, fixedCoord1, fixedCoord2);
                        break;
                    case 'y':
                        label.position.set(fixedCoord1, roundedValue, fixedCoord2);
                        break;
                    case 'z':
                        label.position.set(fixedCoord1, fixedCoord2, roundedValue);
                        break;
                }

                this.coordinateLabels.push(label);
                this._scene.add(label);
            }
        },

        /**
         * 切换坐标轴显示
         */
        toggleCoordinateAxis() {
            this.showCoordinateAxis = !this.showCoordinateAxis;
        },

        /**
         * 设置坐标轴颜色
         */
        setAxisColor(color) {
            this.axisColor = color;
        },

        /**
         * 清除坐标轴
         */
        clearCoordinateAxis() {
            // 清除包围盒
            if (this._coordinateBox) {
                this._scene.remove(this._coordinateBox);
                this._coordinateBox.geometry.dispose();
                this._coordinateBox.material.dispose();
                this._coordinateBox = null;
            }

            // 清除标签
            this.coordinateLabels.forEach(label => {
                this._scene.remove(label);
                if (label.element && label.element.parentNode) {
                    label.element.parentNode.removeChild(label.element);
                }
            });
            this.coordinateLabels = [];
        },

        /**
         * 处理地层可见性切换事件
         */
        handleToggleLayerVisibility(data) {
            this.toggleLayerVisibility(data.layerId, data.visible);
        },

        /**
         * 处理地层透明度更新事件
         */
        handleUpdateLayerOpacity(data) {
            this.updateLayerOpacity(data.layerId, data.opacity);
        },

        /**
         * 初始化裁剪平面
         */
        initClippingPlane() {
            // 创建裁剪平面 (初始位置在模型中心，法线朝上)
            this._clippingPlane = markRaw(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0));
            this.clippingPlanes = [this._clippingPlane];

            // 创建平面助手 (可视化裁剪平面)
            this.createClippingHelper();

            // 创建变换控制器
            this.createTransformControls();


        },

        /**
         * 创建裁剪平面可视化助手
         */
        createClippingHelper() {
            // 根据包围盒计算合适的平面尺寸
            let planeSize = 100; // 默认尺寸
            if (this._model) {
                const box = new THREE.Box3().setFromObject(this._model);
                const size = box.getSize(new THREE.Vector3());
                const maxDimension = Math.max(size.x, size.y, size.z);
                planeSize = maxDimension * 1.5; // 平面尺寸为模型最大尺寸的1.5倍

            } else if (this._boundingBox) {
                const size = this._boundingBox.getSize(new THREE.Vector3());
                const maxDimension = Math.max(size.x, size.y, size.z);
                planeSize = maxDimension * 1.5;

            }

            const geometry = new THREE.PlaneGeometry(planeSize, planeSize);
            const material = new THREE.MeshBasicMaterial({
                color: 0xff9800,
                transparent: true,
                opacity: 0.3,
                side: THREE.DoubleSide,
                wireframe: false
            });

            this._clippingHelper = markRaw(new THREE.Mesh(geometry, material));
            this._clippingHelper.name = 'clippingHelper';
            this._clippingHelper.visible = false;
            this._scene.add(this._clippingHelper);

            // 更新助手位置以匹配裁剪平面
            this.updateClippingHelperFromPlane();
        },

        /**
         * 更新裁剪平面尺寸
         */
        updateClippingHelperSize() {
            if (!this._clippingHelper || !this._model) return;

            const box = new THREE.Box3().setFromObject(this._model);
            const size = box.getSize(new THREE.Vector3());
            const maxDimension = Math.max(size.x, size.y, size.z);
            const planeSize = maxDimension * 1.5;

            // 更新几何体尺寸
            this._clippingHelper.geometry.dispose();
            this._clippingHelper.geometry = new THREE.PlaneGeometry(planeSize, planeSize);



            // 同时调整位置确保可见
            this.adjustClippingHelperPosition();
        },

        /**
         * 调整剖切平面位置，确保在模型外部可见
         */
        adjustClippingHelperPosition() {
            if (!this._clippingHelper || !this._model) return;

            const box = new THREE.Box3().setFromObject(this._model);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            // 将剖切平面放置在模型上方，距离为模型高度的30%
            const position = center.clone();
            position.y += size.y * 0.3;

            this._clippingHelper.position.copy(position);

            // 确保朝向正确（法线向下）
            this._clippingHelper.lookAt(
                position.x,
                position.y - 1,
                position.z
            );

            // 同步更新剖切平面
            this.updateClippingPlaneFromHelper();


        },
        /**
         * 创建变换控制器
         */
        createTransformControls() {
            this._transformControls = markRaw(new TransformControls(this._camera, this._renderer.domElement));
            this._transformControls.size = 1.2;
            this._transformControls.visible = false;
            this._scene.add(this._transformControls.getHelper());

            // 当变换控制器激活时，禁用轨道控制器
            this._transformControls.addEventListener('dragging-changed', (event) => {
                this._controls.enabled = !event.value;
            });

            // 当变换发生时，更新裁剪平面
            this._transformControls.addEventListener('change', () => {
                if (this._clippingHelper && this._transformControls.object === this._clippingHelper) {
                    this.updateClippingPlaneFromHelper();
                }
            });
        },

        /**
         * 根据裁剪平面更新助手位置
         */
        updateClippingHelperFromPlane() {
            if (!this._clippingHelper || !this._clippingPlane) return;

            const plane = this._clippingPlane;
            const normal = plane.normal.clone();
            const distance = -plane.constant; // Three.js plane constant 是负距离

            // 设置助手位置在平面上
            this._clippingHelper.position.copy(normal.multiplyScalar(distance));

            // 设置助手朝向
            this._clippingHelper.lookAt(
                this._clippingHelper.position.x + normal.x,
                this._clippingHelper.position.y + normal.y,
                this._clippingHelper.position.z + normal.z
            );
        },

        /**
         * 根据助手位置更新裁剪平面
         */
        updateClippingPlaneFromHelper() {
            if (!this._clippingHelper || !this._clippingPlane) return;

            // 从助手的变换矩阵获取法线和位置
            const normal = new THREE.Vector3(0, 0, 1);
            normal.applyMatrix3(new THREE.Matrix3().getNormalMatrix(this._clippingHelper.matrixWorld));
            normal.normalize();

            const position = this._clippingHelper.position;

            // 更新裁剪平面
            this._clippingPlane.setFromNormalAndCoplanarPoint(normal, position);


        },
        /**
         * 切换剖面显示
         */
        toggleClipping() {
            this.showClipping = !this.showClipping;
        },
        /**
         * 对齐裁剪平面
         */
        alignClippingPlane(direction) {
            if (!this._clippingHelper || !this._boundingBox) return;

            const center = this._boundingBox.getCenter(new THREE.Vector3());
            let normal, position;

            switch (direction) {
                case 'XY':
                    normal = new THREE.Vector3(0, 0, 1);
                    position = center;
                    break;
                case 'YZ':
                    normal = new THREE.Vector3(1, 0, 0);
                    position = center;
                    break;
                case 'XZ':
                    normal = new THREE.Vector3(0, 1, 0);
                    position = center;
                    break;
                case 'camera': {
                    // 对齐到相机视角
                    const cameraDirection = new THREE.Vector3();
                    this._camera.getWorldDirection(cameraDirection);
                    normal = cameraDirection.negate();
                    position = center;
                    break;
                }
                default:
                    return;
            }

            // 更新助手位置和朝向
            this._clippingHelper.position.copy(position);
            this._clippingHelper.lookAt(
                position.x + normal.x,
                position.y + normal.y,
                position.z + normal.z
            );

            // 更新裁剪平面
            this.updateClippingPlaneFromHelper();
        },

        /**
         * 设置变换模式
         */
        setTransformMode(mode) {
            if (!this._transformControls) return;

            switch (mode) {
                case 'translate':
                    this._transformControls.setMode('translate');
                    break;
                case 'rotate':
                    this._transformControls.setMode('rotate');
                    break;
                default:
                    break;
            }
        },

        /**
         * 设置控制目标
         */
        setControlTarget(target) {
            this.controlTarget = target;
        },

        /**
         * 更新控制模式
         */
        updateControlMode() {
            if (!this._controls || !this._transformControls) return;

            if (this.controlTarget === 'model') {
                // 控制模型：启用OrbitControls，隐藏TransformControls
                this._controls.enabled = true;
                if (this._transformControls.visible) {
                    this._transformControls.detach();
                    this._transformControls.visible = false;
                }
            } else if (this.controlTarget === 'plane' && this.showClipping) {
                // 控制剖面平面：禁用OrbitControls，显示TransformControls
                this._controls.enabled = false;
                if (this._clippingHelper) {
                    this._transformControls.attach(this._clippingHelper);
                    this._transformControls.visible = true;
                }
            }
        },

        /**
         * 生成剖面几何
         */
        generateSection() {
            if (!this._model || !this._clippingPlane) {
                console.warn('无法生成剖面：缺少模型或裁剪平面');
                this.$eventBus.$emit('section-data-ready', null);
                return;
            }



            // 确保使用当前剖面：同步助手矩阵并刷新裁剪平面
            if (this._clippingHelper) {
                this._clippingHelper.updateMatrixWorld(true);
                this.updateClippingPlaneFromHelper();
            }

            // 清除之前的剖面线条
            this.clearSectionLines();

            const intersectionSegments = [];
            const plane = this._clippingPlane;

            // 遍历模型中的所有网格
            this._model.traverse((child) => {
                if (child.isMesh && child.geometry) {
                    const segments = this.calculateMeshPlaneIntersection(child, plane);
                    intersectionSegments.push(...segments);
                }
            });

            // 创建剖面线条可视化
            if (intersectionSegments.length > 0) {
                this.createSectionLines(intersectionSegments);

            }

            // 生成SVG剖面图
            const svgData = this.generateSectionSVG(intersectionSegments);

            // 创建完整的剖面数据
            const sectionData = {
                svg: svgData.svg,
                svgColored: svgData.svgColored,
                segments: intersectionSegments,
                position: `(${this._clippingHelper.position.x.toFixed(2)}, ${this._clippingHelper.position.y.toFixed(2)}, ${this._clippingHelper.position.z.toFixed(2)})`,
                normal: `(${plane.normal.x.toFixed(3)}, ${plane.normal.y.toFixed(3)}, ${plane.normal.z.toFixed(3)})`,
                intersectionCount: intersectionSegments.length,
                timestamp: new Date().toLocaleString('zh-CN')
            };

            // 发送剖面数据到模态窗口

            this.$eventBus.$emit('section-data-ready', sectionData);
        },

        /**
         * 计算网格与平面的交线
         */
        calculateMeshPlaneIntersection(mesh, plane) {
            const segments = [];
            const geometry = mesh.geometry;

            if (!geometry.attributes.position) return segments;

            // 获取位置属性和材质信息
            const positions = geometry.attributes.position.array;
            const worldMatrix = mesh.matrixWorld;

            // 获取材质信息
            const materialInfo = this.getMaterialInfo(mesh);

            // 如果有索引，使用索引访问三角形
            if (geometry.index) {
                const indices = geometry.index.array;

                for (let i = 0; i < indices.length; i += 3) {
                    const a = indices[i] * 3;
                    const b = indices[i + 1] * 3;
                    const c = indices[i + 2] * 3;

                    const segment = this.calculateTrianglePlaneIntersection(
                        positions, a, b, c, plane, worldMatrix, materialInfo
                    );

                    if (segment) {
                        segments.push(segment);
                    }
                }
            } else {
                // 直接访问三角形
                for (let i = 0; i < positions.length; i += 9) {
                    const segment = this.calculateTrianglePlaneIntersection(
                        positions, i, i + 3, i + 6, plane, worldMatrix, materialInfo
                    );

                    if (segment) {
                        segments.push(segment);
                    }
                }
            }

            return segments;
        },

        /**
         * 获取网格的材质信息
         */
        getMaterialInfo(mesh) {
            let materialId = 'default';
            let materialName = 'Default';
            let material = null;

            if (mesh.material) {
                material = mesh.material;
                materialName = mesh.material.name || mesh.name || 'Unknown';
                materialId = mesh.material.uuid || mesh.uuid || 'default';
            }

            // 尝试从网格名称中提取地层信息
            if (mesh.name) {
                materialName = mesh.name;
            }

            return {
                id: materialId,
                name: materialName,
                material: material
            };
        },

        /**
         * 计算三角形与平面的交线
         */
        calculateTrianglePlaneIntersection(positions, aIndex, bIndex, cIndex, plane, worldMatrix, materialInfo = null) {
            // 获取三角形顶点
            const v1 = new THREE.Vector3(
                positions[aIndex], positions[aIndex + 1], positions[aIndex + 2]
            );
            const v2 = new THREE.Vector3(
                positions[bIndex], positions[bIndex + 1], positions[bIndex + 2]
            );
            const v3 = new THREE.Vector3(
                positions[cIndex], positions[cIndex + 1], positions[cIndex + 2]
            );

            // 转换到世界坐标
            v1.applyMatrix4(worldMatrix);
            v2.applyMatrix4(worldMatrix);
            v3.applyMatrix4(worldMatrix);

            // 计算每个顶点到平面的距离
            const d1 = plane.distanceToPoint(v1);
            const d2 = plane.distanceToPoint(v2);
            const d3 = plane.distanceToPoint(v3);

            const intersectionPoints = [];

            // 检查边与平面的交点
            const checkEdgeIntersection = (p1, p2, dist1, dist2) => {
                if ((dist1 > 0 && dist2 < 0) || (dist1 < 0 && dist2 > 0)) {
                    // 边跨越平面，计算交点
                    const t = Math.abs(dist1) / (Math.abs(dist1) + Math.abs(dist2));
                    const intersection = p1.clone().lerp(p2, t);
                    return intersection;
                }
                return null;
            };

            // 检查三条边
            const int1 = checkEdgeIntersection(v1, v2, d1, d2);
            const int2 = checkEdgeIntersection(v2, v3, d2, d3);
            const int3 = checkEdgeIntersection(v3, v1, d3, d1);

            if (int1) intersectionPoints.push(int1);
            if (int2) intersectionPoints.push(int2);
            if (int3) intersectionPoints.push(int3);

            // 如果有两个交点，返回线段
            if (intersectionPoints.length === 2) {
                const segment = {
                    start: intersectionPoints[0],
                    end: intersectionPoints[1]
                };

                // 添加材质信息
                if (materialInfo) {
                    segment.materialId = materialInfo.id;
                    segment.materialName = materialInfo.name;
                    segment.material = materialInfo.material;
                }

                return segment;
            }

            return null;
        },

        /**
         * 创建剖面线条可视化
         */
        createSectionLines(segments) {
            const points = [];

            segments.forEach(segment => {
                points.push(segment.start, segment.end);
            });

            if (points.length === 0) return;

            // 创建线条几何
            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            const material = new THREE.LineBasicMaterial({
                color: 0xff0000,
                linewidth: 2,
                transparent: true,
                opacity: 0.8
            });

            const lines = new THREE.LineSegments(geometry, material);
            lines.name = 'sectionLines';
            this._scene.add(lines);
            this.sectionLines.push(lines);
        },

        /**
         * 清除剖面线条
         */
        clearSectionLines() {
            this.sectionLines.forEach(line => {
                this._scene.remove(line);
                line.geometry.dispose();
                line.material.dispose();
            });
            this.sectionLines = [];
        },

        /**
         * 生成剖面的SVG数据
         */
        generateSectionSVG(intersectionSegments) {
            if (!intersectionSegments || intersectionSegments.length === 0) {
                return {
                    svg: '<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg"><text x="200" y="150" text-anchor="middle" font-family="Arial" font-size="16" fill="#666">无剖面数据</text></svg>',
                    svgColored: '<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg"><text x="200" y="150" text-anchor="middle" font-family="Arial" font-size="16" fill="#666">无剖面数据</text></svg>'
                };
            }

            // 将3D线条投影到裁剪平面的2D坐标系，并获取材质信息
            const projectedData = this.projectIntersectionSegmentsToPlaneWithMaterials(intersectionSegments);

            // 创建SVG内容（线框版本和彩色版本）
            const svgWireframe = this.createSVGContent(projectedData.lines, false);
            const svgColored = this.createSVGContent(projectedData.lines, true, projectedData.materials);

            return {
                svg: svgWireframe,
                svgColored: svgColored
            };
        },

        /**
         * 将交线段投影到2D平面
         */
        projectIntersectionSegmentsToPlane(segments) {
            const projectedLines = [];
            const plane = this._clippingPlane;

            // 获取平面的局部坐标系
            const normal = plane.normal.clone().normalize();
            const up = new THREE.Vector3(0, 1, 0);
            const right = new THREE.Vector3().crossVectors(up, normal).normalize();
            const actualUp = new THREE.Vector3().crossVectors(normal, right).normalize();

            segments.forEach(segment => {
                const startProjected = this.projectPointToPlane2D(segment.start, plane, right, actualUp);
                const endProjected = this.projectPointToPlane2D(segment.end, plane, right, actualUp);

                projectedLines.push({
                    start: startProjected,
                    end: endProjected
                });
            });

            return projectedLines;
        },

        /**
         * 将交线段投影到2D平面，并获取材质信息
         */
        projectIntersectionSegmentsToPlaneWithMaterials(segments) {
            const projectedLines = [];
            const materials = new Map();
            const plane = this._clippingPlane;

            // 获取平面的局部坐标系
            const normal = plane.normal.clone().normalize();
            const up = new THREE.Vector3(0, 1, 0);
            const right = new THREE.Vector3().crossVectors(up, normal).normalize();
            const actualUp = new THREE.Vector3().crossVectors(normal, right).normalize();

            segments.forEach((segment, index) => {
                const startProjected = this.projectPointToPlane2D(segment.start, plane, right, actualUp);
                const endProjected = this.projectPointToPlane2D(segment.end, plane, right, actualUp);

                // 获取材质颜色信息
                let materialColor = '#333333'; // 默认颜色
                if (segment.material) {
                    if (segment.material.color) {
                        materialColor = `#${segment.material.color.getHexString()}`;
                    } else if (segment.materialName) {
                        // 根据材质名称分配颜色
                        materialColor = this.getLayerColorByName(segment.materialName);
                    }
                }

                projectedLines.push({
                    start: startProjected,
                    end: endProjected,
                    materialId: segment.materialId || index,
                    color: materialColor
                });

                // 存储材质信息
                if (segment.materialId) {
                    materials.set(segment.materialId, {
                        color: materialColor,
                        name: segment.materialName || `Material_${segment.materialId}`
                    });
                }
            });

            return {
                lines: projectedLines,
                materials: materials
            };
        },

        /**
         * 根据材质名称获取地层颜色
         */
        getLayerColorByName(materialName) {
            // 地层颜色映射表
            const layerColors = {
                'coal': '#2c2c2c',           // 煤层 - 深灰色
                'sandstone': '#daa520',      // 砂岩 - 金色
                'mudstone': '#8b4513',       // 泥岩 - 棕色
                'limestone': '#f5f5dc',      // 石灰岩 - 米色
                'shale': '#696969',          // 页岩 - 暗灰色
                'gravel': '#a0522d',         // 砾岩 - 褐色
                'loose': '#deb887'           // 松散层 - 浅棕色
            };

            // 简单匹配材质名称
            const lowerName = (materialName || '').toLowerCase();
            for (const [key, color] of Object.entries(layerColors)) {
                if (lowerName.includes(key)) {
                    return color;
                }
            }

            // 如果没有匹配，根据名称生成一致的颜色
            return this.generateColorFromString(materialName || 'default');
        },

        /**
         * 根据字符串生成一致的颜色
         */
        generateColorFromString(str) {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                hash = str.charCodeAt(i) + ((hash << 5) - hash);
            }

            const hue = Math.abs(hash % 360);
            const saturation = 50 + (Math.abs(hash) % 30); // 50-80%
            const lightness = 40 + (Math.abs(hash >> 8) % 20); // 40-60%

            return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
        },

        /**
         * 导出剖面
         */
        exportSection(exportData) {

            const { format, data } = exportData;
            switch (format) {
                case 'png':
                    this.exportPNGFromData(data);
                    break;
                case 'svg':
                    this.exportSVGFromData(data);
                    break;
                case 'json':
                    this.exportJSONFromData(data);
                    break;
                default:
                    console.warn('不支持的导出格式:', format);
            }

        },

        /**
         * 导出PNG截图
         */
        exportPNG() {
            if (!this._renderer) return;

            this._renderer.render(this._scene, this._camera);
            const dataURL = this._renderer.domElement.toDataURL('image/png');

            const link = document.createElement('a');
            link.download = 'section-screenshot.png';
            link.href = dataURL;
            link.click();
        },

        /**
         * 导出SVG (2D剖面线)
         */
        exportSVG() {
            if (!this.sectionLines.length) {
                alert('请先生成剖面');
                return;
            }

            // 将3D线条投影到裁剪平面的2D坐标系
            const projectedLines = this.projectSectionLinesToPlane();

            // 创建SVG内容
            const svgContent = this.createSVGContent(projectedLines);

            // 下载SVG文件
            const blob = new Blob([svgContent], { type: 'image/svg+xml' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.download = 'section-profile.svg';
            link.href = url;
            link.click();
            URL.revokeObjectURL(url);
        },

        /**
         * 将剖面线投影到2D平面
         */
        projectSectionLinesToPlane() {
            const projectedLines = [];
            const plane = this._clippingPlane;

            // 获取平面的局部坐标系
            const normal = plane.normal.clone().normalize();
            const up = new THREE.Vector3(0, 1, 0);
            const right = new THREE.Vector3().crossVectors(up, normal).normalize();
            const actualUp = new THREE.Vector3().crossVectors(normal, right).normalize();

            this.sectionLines.forEach(lineObj => {
                const positions = lineObj.geometry.attributes.position.array;

                for (let i = 0; i < positions.length; i += 6) {
                    const start = new THREE.Vector3(positions[i], positions[i + 1], positions[i + 2]);
                    const end = new THREE.Vector3(positions[i + 3], positions[i + 4], positions[i + 5]);

                    // 投影到平面2D坐标
                    const startProjected = this.projectPointToPlane2D(start, plane, right, actualUp);
                    const endProjected = this.projectPointToPlane2D(end, plane, right, actualUp);

                    projectedLines.push({
                        start: startProjected,
                        end: endProjected
                    });
                }
            });

            return projectedLines;
        },

        /**
         * 将3D点投影到平面2D坐标
         */
        projectPointToPlane2D(point, plane, rightVec, upVec) {
            // 将点投影到平面上
            const planePoint = point.clone();
            const distance = plane.distanceToPoint(planePoint);
            planePoint.addScaledVector(plane.normal, -distance);

            // 获得参考点（平面上的原点）
            const planeOrigin = plane.normal.clone().multiplyScalar(-plane.constant);

            // 计算相对于平面原点的向量
            const relative = planePoint.sub(planeOrigin);

            // 投影到2D坐标系
            return {
                x: relative.dot(rightVec),
                y: relative.dot(upVec)
            };
        },

        /**
         * 创建SVG内容
         */
        createSVGContent(projectedLines, showColors = false, materials = null) {
            if (projectedLines.length === 0) return '';

            // 计算边界框
            let minX = Infinity, maxX = -Infinity;
            let minY = Infinity, maxY = -Infinity;

            projectedLines.forEach(line => {
                minX = Math.min(minX, line.start.x, line.end.x);
                maxX = Math.max(maxX, line.start.x, line.end.x);
                minY = Math.min(minY, line.start.y, line.end.y);
                maxY = Math.max(maxY, line.start.y, line.end.y);
            });

            // 优化尺寸：减少空白区域
            const dataWidth = maxX - minX;
            const dataHeight = maxY - minY;

            // 根据数据的宽高比决定padding
            const aspectRatio = dataWidth / dataHeight;
            let padding;

            if (aspectRatio > 2) {
                // 数据很宽，减少水平padding
                padding = Math.min(dataHeight * 0.05, dataWidth * 0.02);
            } else if (aspectRatio < 0.5) {
                // 数据很高，减少垂直padding
                padding = Math.min(dataWidth * 0.05, dataHeight * 0.02);
            } else {
                // 比例适中
                padding = Math.min(dataWidth, dataHeight) * 0.05;
            }

            const width = dataWidth + 2 * padding;
            const height = dataHeight + 2 * padding;

            // 创建SVG内容
            let svgContent = `<?xml version="1.0" encoding="UTF-8"?>
<svg width="${width.toFixed(0)}" height="${height.toFixed(0)}" 
         viewBox="0 0 ${width.toFixed(0)} ${height.toFixed(0)}"
         xmlns="http://www.w3.org/2000/svg">
    <style>
        .section-line { stroke-width: 1.5; fill: none; }
        .wireframe-line { stroke: #333333; }
        .colored-line { opacity: 0.9; }
        .fill-shape { fill-opacity: 0.65; stroke: #333333; stroke-width: 0.6; }
    </style>`;

            if (showColors && materials) {
                // 彩色版本：按材质分组绘制
                const linesByMaterial = new Map();

                projectedLines.forEach(line => {
                    const materialId = line.materialId || 'default';
                    if (!linesByMaterial.has(materialId)) {
                        linesByMaterial.set(materialId, []);
                    }
                    linesByMaterial.get(materialId).push(line);
                });

                linesByMaterial.forEach((lines) => {
                    const color = lines[0]?.color || '#333333';

                    // 先绘制填充形状
                    const polygons = this.buildPolygonsFromLines(lines, padding, minX, maxY);
                    polygons.forEach(poly => {
                        const d = poly.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ') + ' Z';
                        svgContent += `
  <path d="${d}" class="fill-shape" fill="${color}" fill-rule="evenodd"/>`;
                    });

                    // 再叠加线条
                    let pathData = '';
                    lines.forEach(line => {
                        const x1 = line.start.x - minX + padding;
                        const y1 = maxY - line.start.y + padding;
                        const x2 = line.end.x - minX + padding;
                        const y2 = maxY - line.end.y + padding;
                        pathData += `M ${x1.toFixed(2)} ${y1.toFixed(2)} L ${x2.toFixed(2)} ${y2.toFixed(2)} `;
                    });

                    svgContent += `
  <path d="${pathData}" 
        class="section-line colored-line" 
        stroke="${color}"/>`;
                });
            } else {
                // 线框版本：统一样式
                let pathData = '';
                projectedLines.forEach(line => {
                    const x1 = line.start.x - minX + padding;
                    const y1 = maxY - line.start.y + padding;
                    const x2 = line.end.x - minX + padding;
                    const y2 = maxY - line.end.y + padding;

                    pathData += `M ${x1.toFixed(2)} ${y1.toFixed(2)} L ${x2.toFixed(2)} ${y2.toFixed(2)} `;
                });

                svgContent += `
  <path d="${pathData}" 
        class="section-line wireframe-line"/>`;
            }

            svgContent += `
</svg>`;

            return svgContent;
        },

        /**
         * 将线段集合拼接为闭合多边形（贪心 + 容差）并返回屏幕坐标点序列
         * lines: Array<{ start:{x,y}, end:{x,y} }>
         */
        buildPolygonsFromLines(lines, padding, minX, maxY) {
            const toScreen = (pt) => ({
                x: pt.x - minX + padding,
                y: maxY - pt.y + padding
            });

            const segs = lines.map(l => ({ a: toScreen(l.start), b: toScreen(l.end), used: false }));

            let minSX = Infinity, maxSX = -Infinity, minSY = Infinity, maxSY = -Infinity;
            segs.forEach(s => {
                minSX = Math.min(minSX, s.a.x, s.b.x);
                maxSX = Math.max(maxSX, s.a.x, s.b.x);
                minSY = Math.min(minSY, s.a.y, s.b.y);
                maxSY = Math.max(maxSY, s.a.y, s.b.y);
            });
            const diag = Math.hypot(maxSX - minSX, maxSY - minSY) || 1;
            const EPS = Math.max(1e-3, diag * 1e-3);

            const keyOf = (p) => `${Math.round(p.x / EPS)}_${Math.round(p.y / EPS)}`;
            const equalP = (p1, p2) => (Math.hypot(p1.x - p2.x, p1.y - p2.y) <= EPS);

            const adjacency = new Map();
            const addAdj = (k, i, point) => {
                if (!adjacency.has(k)) adjacency.set(k, []);
                adjacency.get(k).push({ segIndex: i, point });
            };
            segs.forEach((s, i) => {
                addAdj(keyOf(s.a), i, s.a);
                addAdj(keyOf(s.b), i, s.b);
            });

            const polygons = [];
            for (let i = 0; i < segs.length; i++) {
                if (segs[i].used) continue;
                const start = segs[i].a;
                let current = segs[i].b;
                let currentKey = keyOf(current);
                const loop = [start];
                segs[i].used = true;

                let safety = 0;
                while (safety++ < segs.length * 2) {
                    loop.push(current);
                    if (equalP(current, start)) {
                        if (loop.length >= 4) polygons.push(loop.slice());
                        break;
                    }
                    const neighbors = adjacency.get(currentKey) || [];
                    let advanced = false;
                    for (const nb of neighbors) {
                        const seg = segs[nb.segIndex];
                        if (seg.used) continue;
                        let nextPoint = null;
                        if (equalP(seg.a, current)) nextPoint = seg.b;
                        else if (equalP(seg.b, current)) nextPoint = seg.a;
                        if (nextPoint) {
                            seg.used = true;
                            current = nextPoint;
                            currentKey = keyOf(current);
                            advanced = true;
                            break;
                        }
                    }
                    if (!advanced) break;
                }
            }

            const area = (poly) => {
                let s = 0;
                for (let i = 0; i < poly.length; i++) {
                    const p = poly[i];
                    const q = poly[(i + 1) % poly.length];
                    s += p.x * q.y - p.y * q.x;
                }
                return Math.abs(s) / 2;
            };
            return polygons.filter(poly => area(poly) > EPS * EPS);
        },

        /**
         * 导出GLB (3D模型)
         */
        exportGLB() {
            if (!this.sectionLines.length) {
                alert('请先生成剖面');
                return;
            }

            // 这里需要GLTFExporter，暂时提供基础实现


            // 创建可导出的几何数据
            const exportData = {
                type: 'SectionModel',
                lines: this.sectionLines.length,
                clippingPlane: {
                    normal: this._clippingPlane.normal.toArray(),
                    constant: this._clippingPlane.constant
                }
            };

            // 以JSON格式下载（作为GLB的替代）
            const dataStr = JSON.stringify(exportData, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.download = 'section-data.json';
            link.href = url;
            link.click();
            URL.revokeObjectURL(url);
        },

        /**
         * 从剖面数据导出SVG
         */
        exportSVGFromData(sectionData) {
            if (!sectionData || !sectionData.svg) {
                alert('无效的剖面数据');
                return;
            }

            // 创建SVG文件
            const svgContent = sectionData.svg;
            const blob = new Blob([svgContent], { type: 'image/svg+xml' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.download = `section-profile-${Date.now()}.svg`;
            link.href = url;
            link.click();
            URL.revokeObjectURL(url);
        },

        /**
         * 从剖面SVG导出PNG
         */
        exportPNGFromData(sectionData) {
            if (!sectionData || (!sectionData.svg && !sectionData.svgColored)) {
                alert('无效的剖面数据');
                return;
            }

            const svgContent = sectionData.svgColored || sectionData.svg;
            const sizeMatch = svgContent.match(/viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"/);
            let w = 1024, h = 768;
            if (sizeMatch) {
                w = Math.max(1, Math.floor(parseFloat(sizeMatch[1])));
                h = Math.max(1, Math.floor(parseFloat(sizeMatch[2])));
            }

            const svgBlob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' });
            const url = URL.createObjectURL(svgBlob);
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);
                URL.revokeObjectURL(url);

                canvas.toBlob((blob) => {
                    if (!blob) return;
                    const dlUrl = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = dlUrl;
                    a.download = `section-${Date.now()}.png`;
                    a.click();
                    URL.revokeObjectURL(dlUrl);
                }, 'image/png');
            };
            img.onerror = () => {
                URL.revokeObjectURL(url);
                alert('导出PNG失败：SVG图像加载错误');
            };
            img.src = url;
        },

        /**
         * 从剖面数据导出JSON
         */
        exportJSONFromData(sectionData) {
            if (!sectionData) {
                alert('无效的剖面数据');
                return;
            }

            // 创建完整的导出数据
            const exportData = {
                type: 'SectionData',
                timestamp: sectionData.timestamp,
                position: sectionData.position,
                normal: sectionData.normal,
                intersectionCount: sectionData.intersectionCount,
                segments: sectionData.segments
            };

            const dataStr = JSON.stringify(exportData, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.download = `section-data-${Date.now()}.json`;
            link.href = url;
            link.click();
            URL.revokeObjectURL(url);
        },

        /**
         * 导出JSON格式（兼容旧接口）
         */
        exportJSON() {
            if (!this._clippingPlane) {
                alert('请先启用剖面工具');
                return;
            }

            const exportData = {
                type: 'SectionModel',
                timestamp: new Date().toLocaleString('zh-CN'),
                position: this._clippingHelper ? this._clippingHelper.position.toArray() : [0, 0, 0],
                normal: this._clippingPlane.normal.toArray(),
                constant: this._clippingPlane.constant,
                sectionLines: this.sectionLines.length
            };

            const dataStr = JSON.stringify(exportData, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.download = `section-info-${Date.now()}.json`;
            link.href = url;
            link.click();
            URL.revokeObjectURL(url);
        },

        /**
         * 清理剖面相关资源
         */
        clearClipping() {
            // 清理助手
            if (this._clippingHelper) {
                this._scene.remove(this._clippingHelper);
                this._clippingHelper.geometry.dispose();
                this._clippingHelper.material.dispose();
                this._clippingHelper = null;
            }

            // 清理变换控制器
            if (this._transformControls) {
                this._scene.remove(this._transformControls);
                this._transformControls.dispose();
                this._transformControls = null;
            }

            // 清理剖面线条
            this.sectionLines.forEach(line => {
                this._scene.remove(line);
                line.geometry.dispose();
                line.material.dispose();
            });
            this.sectionLines = [];

            // 清理剖面几何
            if (this.sectionGeometry) {
                this.sectionGeometry.dispose();
                this.sectionGeometry = null;
            }

            // 重置裁剪平面
            this.clippingPlanes = [];
            this._clippingPlane = null;
            this.showClipping = false;

            // 移除所有材质的裁剪平面
            if (this._model) {
                this._model.traverse((child) => {
                    if (child.isMesh && child.material) {
                        const materials = Array.isArray(child.material) ? child.material : [child.material];
                        materials.forEach(material => {
                            material.clippingPlanes = [];
                            material.needsUpdate = true;
                        });
                    }
                });
            }
        },

        /**
         * 清理资源
         */
        cleanup() {
            if (this._renderer) {
                this._renderer.dispose();
            }

            if (this._labelRenderer && this._labelRenderer.domElement && this._labelRenderer.domElement.parentNode) {
                this._labelRenderer.domElement.parentNode.removeChild(this._labelRenderer.domElement);
            }

            if (this._model) {
                this.clearModel();
            }

            this.clearCoordinateAxis();
            this.clearClipping();

            // 清理 blob URL
            if (this.currentBlobUrl) {
                URL.revokeObjectURL(this.currentBlobUrl);
                this.currentBlobUrl = null;
            }

            // 清理几何体和材质
            this._originalMaterials.forEach(material => material.dispose());
            this._originalMaterials.clear();
        }
    }
}
</script>

<style scoped>
.model-viewer {
    width: 100%;
    height: 100%;
    position: relative;
    background-color: #f5f5f5;
}

.model-viewer canvas {
    display: block;
    width: 100% !important;
    height: 100% !important;
}
</style>

<style>
/* 坐标轴标签样式 - 不使用 scoped，因为这些是动态创建的 DOM 元素 */
.coordinate-label {
    font-family: Arial, sans-serif;
    font-size: 12px;
    font-weight: 500;
    text-align: center;
    white-space: nowrap;
    user-select: none;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(0, 0, 0, 0.1);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.coordinate-label:hover {
    transform: scale(1.1);
    transition: transform 0.2s ease;
}
</style>