# 细层化(14层)地质模型交付包 web_package_refined

> 由 `experiments/scripts/chapter05/build_chapter05_web_package_refined.py` 自动生成,与原10层包 `../web_package/` 完全隔离,请勿混用两包的同名文件。

## 层序(自上而下,14层/15界面)

| 代码 | 层名 | 颜色 | 体积(百万m³) |
|---|---|---|---|
| L01 | 风积砂层 | #D9C7A3 | 3,268.9 |
| L02 | 土层 | #CDBB8C | 4,254.5 |
| L03 | 第4旋回泥岩层 | #8C6D5A | 23.6 |
| L04 | 第4旋回砂岩层 | #D98C5F | 385.8 |
| L05 | 第3旋回泥岩层 | #8C6D5A | 37.6 |
| L06 | 第3旋回砂岩层 | #D98C5F | 911.6 |
| L07 | 第2旋回泥岩层 | #8C6D5A | 289.8 |
| L08 | 第2旋回砂岩层 | #D98C5F | 2,777.5 |
| L09 | 第1旋回泥岩层 | #8C6D5A | 648.7 |
| L10 | 第1旋回砂岩层 | #D98C5F | 4,568.1 |
| L11 | 煤顶泥岩层 | #7A8793 | 214.8 |
| L12 | 煤3-1 | #333333 | 516.4 |
| L13 | 直接底层 | #C98E5B | 2,228.9 |
| L14 | 下伏岩层 | #8D7465 | 3,054.6 |

## 来源链(可复现)

1. `experiments/scripts/chapter02/build_refined_strata.py`:原始岩性 → 锚点-旋回-阈值(ACT)细层标准柱(τ=0.5m, K*=4, 截断=4-2煤) → `data/project_data/merge/intervals_refined.csv`;2. `experiments/scripts/chapter04/build_refined_surfaces.py`:第3章共享趋势+逐界面ARD + 第4章逐节点保序投影+0.5m尖灭折叠 → 细层 npz(15界面×16641共享节点,100m方格,与原口径同网格,沉陷偏移场可按节点直接对接);
3. 本脚本:向量化 TIN-GTP 建模 → 分层GLB/LOD/VTU。

## 坐标口径

- 局部米制坐标:`x_global = x_local + 37428072.485`,`y_global = y_local + 4300144.085`,`z_global = z_local + 1149.980`;- 与 `roadways.glb`/`working_faces.glb`(井巷工程,自原包复制)同坐标系,可直接同屏加载。

## 双尺度模型(每次生成,固定产物)

- **原始尺寸**:根目录 `model_combined.glb` 与 `L01.glb`–`L14.glb`(真实高程,米);
- **20倍竖向缩放**:`z20/` 目录(几何 = 真实尺度 z×20,顶点属性不变),展示端直接加载、无需再缩放;
- 井巷两个 GLB 为原始尺寸;与 z20 地层同屏时注意口径(建议显示端统一缩放)。

## 顶点属性(GLB 内嵌)

- `_thickness_m` 顶点处本层厚度;`_interface_std_mean_m` 上下界面GP标准差均值;
- `_node_index` 共享网格节点索引(0..16640,与第4章npz/沉陷偏移场对齐);
- `_pinchout_node` 该节点是否处于数值尖灭候选区。

## 已知事项:尖灭相触非流形边(2026-09-03 决策:不修复)

- 合计 7 个层存在非流形边(尖灭线两侧楔形体厚度收敛到零,上下两张曲面片在脊线上贴合,单边4面共享):
  L03, L05, L06, L07, L08, L09, L14;
- 这是零厚度接触的固有几何,不影响渲染/解析体积/体网格;受影响的仅是 vtk 自动定向下的表面积分(实测在尖灭层不可靠),因此本包的体积闭合校验改用**构建语义定向积分**(顶面朝上、底面朝下、侧面朝棱柱外侧),全部14层与解析体积相对偏差 < 1e-7(断言通过,实测~1e-10),并另验表面网格面片集与去重预期一致;非流形边逐层记录于 catalog.json 的 edge_integrity;
- 完整机理与决策记录见 `experiments/reports/chapters/chapter05/refined_pipeline_report.md`。

## 复现命令

```powershell
conda run -n model_env python experiments/scripts/chapter02/build_refined_strata.py
conda run -n model_env python experiments/scripts/chapter04/build_refined_surfaces.py
conda run -n model_env python experiments/scripts/chapter05/build_chapter05_web_package_refined.py
```