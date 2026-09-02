# 第5章模型交付包(Three.js 接入说明)

由 `experiments/scripts/chapter05/build_chapter05_web_package.py` 生成,几何与论文正式模型逐数一致
(体元分类、表面规模、非流形分布、总体积均通过回归断言)。所有顶点为**局部米制坐标,不含任何旋转**:
X=东向、Y=北向、Z=局部高程(真实高程 − z_origin_m)。全局坐标恢复与竖向夸张参数见
`catalog.json` 的 `origin_restore` 字段。

## 文件清单

- `L01.glb` … `L10.glb`:分层表面网格。顶点带自定义属性(`_thickness_m`、
  `_interface_std_mean_m`、`_node_index`、`_pinchout_node`)与顶点色,three.js 可直接用于主题着色与点选查询。
- `lods/L*_lod50.glb`、`L*_lod80.glb`:减面 50% / 80% 的视觉 LOD,仅带顶点色,不携带属性。
- `vtu/L*.vtu`:显式体网格(wedge/pyramid/tetra + 单元属性 volume_m3、thickness_* 等),
  供 ParaView 或体网格消费,three.js 不直接使用。
- `model_combined.glb`:10 层合并场景(节点名 L01–L10),便于快速预览。
- `catalog.json`:元数据总表——坐标恢复公式、逐层名称/配色/统计/包围盒、属性字典、LOD 清单、
  回归断言结果与构建耗时。前端应数据驱动地读取本文件组织场景。

## three.js 最小接入示例

```js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { CatalogLoader } from './catalogReader.js'; // 自行实现 fetch catalog.json

const loader = new GLTFLoader();
// 若未来启用 Draco: loader.setDRACOLoader(new DRACOLoader().setDecoderPath('...'));

const catalog = await fetch('./catalog.json').then(r => r.json());
for (const layer of catalog.layers) {
  loader.load(layer.glb.path, (gltf) => {
    const mesh = gltf.scene.children[0];
    mesh.name = layer.code;                 // L01…
    mesh.userData = { name_cn: layer.name_cn, color: layer.color_hex, stats: layer.stats };
    // 竖向夸张(仅显示): mesh.scale.z = catalog.origin_restore.display_recommendation.z_scale;
    scene.add(mesh);
  });
}
```

## 坐标恢复

- `x_global = x_local + x_origin_m`,`y_global = y_local + y_origin_m`,`z_global = z_local + z_origin_m`(数值见 catalog);
- 显示端竖向夸张:`mesh.scale.z = 20`(GLB 内为局部高程,绕原点缩放不会产生整体抬升;恢复真实比例时除回);
- **three.js 轴向约定**:数据为 Z 轴向上(glTF 规范默认 Y-up),两种处理任选其一——
  `camera.up.set(0, 0, 1)`(不改数据,最简单),或把模型放入 `group.rotation.x = -Math.PI / 2` 的父组转换为 Y-up 世界。

## 已知限制

- Draco 压缩未启用(编码器在当前平台无法安装);单层 GLB 约 1.3–1.9 MB,加载无压力。
  如需启用,three.js 端挂载 DRACOLoader 即可,导出端需换支持 KHR_draco_mesh_compression 的写出口。
- L02/L03/L04 存在尖灭相触导致的非流形边(与论文表5-4一致),渲染正常,
  但布尔运算与网格修复类处理前建议先做节点分裂修复(见 5.7.2 的改进计划)。
- LOD 文件经减面处理,顶点属性不保留,仅用于远视角视觉分级。
