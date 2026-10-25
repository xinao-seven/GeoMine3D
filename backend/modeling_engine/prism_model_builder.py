"""
向量化 TIN-广义三棱柱(GTP)建模核心。

与既有正式实现 src/modeling/build_block_pyvista.py 保持相同建模语义:
- 统一平面 Delaunay 剖分复用于全部界面(本模块只做一次剖分);
- 逐地层将相邻界面的同名三角形连接为广义三棱柱;
- 三个顶点厚度均低于阈值的完全尖灭单元删除;
- 一个或两个顶点重合的单元保留为过渡体;
- 相邻体元之间的内部共享面按无向顶点集合去重;
- 退化侧面:剩三个唯一顶点折叠为三角面,只剩两个唯一顶点不写入。

区别在于核心步骤全部 NumPy 向量化(批量体元生成、np.unique 顶点与面去重),
并额外产出第6章可视化系统需要的内容:
1. 分层表面网格(PolyData,与旧实现逐点逐面一致);
2. 分层显式体网格(UnstructuredGrid: wedge/pyramid/tetra)及单元属性;
3. 逐层解析体积、体元分类计数等统计。

长度单位为米;高程使用真实值,Z 向夸张只应发生在显示端。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pyvista as pv
from scipy.spatial import Delaunay

VERTEX_ROUND_DECIMALS = 6
NEGATIVE_TOL = -1e-8

ELEMENT_CODES = {1: "wedge", 2: "pyramid", 3: "tetra"}


@dataclass
class LayerResult:
    """单个地层体的建模结果。"""

    layer_index: int                    # 自1起
    top_interface: int                  # 上界面索引(0起)
    candidate_prisms: int
    deleted_prisms: int                 # 完全尖灭(三顶点厚度均低于阈值)
    negative_prisms: int                # 负厚度异常(正常流程应为0)
    retained_prisms: int
    partial_pinchout_prisms: int        # 一个或两个顶点重合的过渡体
    element_counts: dict                # {"wedge": n, "pyramid": n, "tetra": n}
    analytic_volume_m3: float           # 式(5-11)解析体积
    surface_mesh: pv.PolyData
    volume_grid: pv.UnstructuredGrid
    vertex_node_index: np.ndarray       # 表面顶点 → 共享网格节点索引
    vertex_interface_index: np.ndarray  # 表面顶点 → 所属界面索引(逐顶点属性对齐用)
    build_seconds: float = 0.0
    # 水平位移过大导致保留体元的平面三角形翻转(负面积)的数量;正常应为 0
    flipped_prisms: int = 0


def _triangle_areas(xy: np.ndarray, simplices: np.ndarray) -> np.ndarray:
    return np.abs(_signed_triangle_areas(xy, simplices))


def _signed_triangle_areas(xy: np.ndarray, simplices: np.ndarray) -> np.ndarray:
    """带符号三角形面积(逆时针为正);水平位移过大导致翻转时会出现非正值。"""
    p = xy[simplices]
    return 0.5 * (
        (p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
        - (p[:, 1, 1] - p[:, 0, 1]) * (p[:, 2, 0] - p[:, 0, 0])
    )


def _hexa_volumes(top: np.ndarray, bot: np.ndarray) -> np.ndarray:
    """六面体(顶三角 + 底三角)的精确体积,向量化。

    分解为 3 个互不重叠的四面体 (t0,t1,t2,b0) / (t1,t2,b0,b1) / (t2,b0,b1,b2),
    各取绝对体积后求和。上下三角形 XY 一致(侧面竖直)时与 A·(h1+h2+h3)/3
    数学等价;逐界面水平位移导致侧面扭曲时,后者失效,必须用本函数。
    """
    t0, t1, t2 = top[:, 0], top[:, 1], top[:, 2]
    b0, b1, b2 = bot[:, 0], bot[:, 1], bot[:, 2]

    def _tet(p, q, r, s):
        return np.abs(
            np.einsum("ij,ij->i", q - p, np.cross(r - p, s - p))
        ) / 6.0

    return _tet(t0, t1, t2, b0) + _tet(t1, t2, b0, b1) + _tet(t2, b0, b1, b2)


def _lex_view(a: np.ndarray) -> np.ndarray:
    """把 (n,2) 坐标数组转成可按字典序比较的一维结构化视图。"""
    return np.ascontiguousarray(a).view([("x", np.float64), ("y", np.float64)]).ravel()


def edge_diagnostics(mesh: pv.PolyData) -> tuple[int, int, bool]:
    """返回(开放边数, 非流形边数, 是否严格流形)。"""
    boundary = mesh.extract_feature_edges(
        boundary_edges=True, feature_edges=False,
        manifold_edges=False, non_manifold_edges=False,
    )
    non_manifold = mesh.extract_feature_edges(
        boundary_edges=False, feature_edges=False,
        manifold_edges=False, non_manifold_edges=True,
    )
    return int(boundary.n_cells), int(non_manifold.n_cells), bool(mesh.is_manifold)


def surface_integral_volume(mesh: pv.PolyData) -> float | None:
    """
    用散度定理对封闭表面独立计算体积,作为解析体积之外的第二个来源。
    面片绕序不一致时先做一致化+自动朝外;失败返回 None。
    """
    try:
        oriented = mesh.copy()
        # vtkPolyDataNormals 要求至少输出一种法线;这里只要它做绕序一致化与朝外定向
        oriented.compute_normals(
            cell_normals=True, point_normals=False, split_vertices=False,
            consistent_normals=True, auto_orient_normals=True, inplace=True,
        )
        tri = oriented.triangulate()
        faces = tri.faces.reshape(-1, 4)[:, 1:]
        p = tri.points[faces]
        signed = np.einsum(
            "ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])
        ).sum() / 6.0
        return abs(float(signed))
    except Exception:
        return None


class PrismModel:
    """共享平面拓扑的多地层广义三棱柱模型(向量化实现)。"""

    def __init__(
        self,
        xy,
        surfaces,
        pinchout_threshold_m: float = 0.5,
        latent_std=None,
        pinchout_masks=None,
        simplices=None,
        xy_per_interface=None,
    ):
        """
        simplices : (N,3) int, 可选
            显式给定平面剖分。给定则**不再执行 Delaunay**(变形复用模式)。
            这是保拓扑的唯一正确做法:拓扑由索引定义,与坐标无关。
            注意正方形规则网格的 Delaunay 是退化问题,顶点被轻微扰动即会
            连锁翻转对角线(实测 12 m/100 m 水平位移可换掉 39% 的三角形)。
        xy_per_interface : (界面数, 节点数, 2) float, 可选
            逐界面水平位移后的 XY。不传时全部界面共用 `xy`(侧面竖直,
            此时体积用 A·(h1+h2+h3)/3);传了则改用六面体四面体分解求积。
        """
        self.xy = np.ascontiguousarray(xy, dtype=float)
        self.surfaces = np.ascontiguousarray(surfaces, dtype=float)
        if self.surfaces.ndim != 2 or self.surfaces.shape[1] != len(self.xy):
            raise ValueError("surfaces 形状应为 (界面数, 共享节点数)")
        if self.surfaces.shape[0] < 2:
            raise ValueError("至少需要两个界面")
        self.n_interfaces = self.surfaces.shape[0]
        self.n_layers = self.surfaces.shape[0] - 1
        self.pinchout_threshold_m = float(pinchout_threshold_m)
        self.latent_std = None if latent_std is None else np.asarray(latent_std, float)
        self.pinchout_masks = (
            None if pinchout_masks is None else np.asarray(pinchout_masks, bool)
        )

        # ---- 各界面使用的 XY ----
        self._uniform_xy = xy_per_interface is None
        if self._uniform_xy:
            self.xy_per_interface = None
            self.xy_if = [self.xy] * self.n_interfaces
        else:
            arr = np.asarray(xy_per_interface, dtype=float)
            expect = (self.n_interfaces, len(self.xy), 2)
            if arr.shape != expect:
                raise ValueError(f"xy_per_interface 形状应为 {expect}，实际 {arr.shape}")
            self.xy_per_interface = np.ascontiguousarray(arr)
            self.xy_if = [self.xy_per_interface[i] for i in range(self.n_interfaces)]

        # ---- 平面剖分:复用或新建 ----
        t0 = time.perf_counter()
        if simplices is None:
            self.triangulation = Delaunay(self.xy)
            self.simplices = self.triangulation.simplices.astype(np.int64)
        else:
            tri = np.asarray(simplices, dtype=np.int64)
            if tri.ndim != 2 or tri.shape[1] != 3:
                raise ValueError(f"simplices 形状应为 (N,3)，实际 {tri.shape}")
            if tri.size and (tri.min() < 0 or tri.max() >= len(self.xy)):
                raise ValueError("simplices 顶点索引越界")
            self.triangulation = None
            self.simplices = np.ascontiguousarray(tri)
        self.t_delaunay = time.perf_counter() - t0
        self.triangle_areas_m2 = _triangle_areas(self.xy, self.simplices)

        # ---- 平面三角形翻转检测(仅逐界面水平位移时可能出现) ----
        if self._uniform_xy:
            self.simplices_flipped = _signed_triangle_areas(
                self.xy, self.simplices
            ) <= 0.0
        else:
            flipped = np.zeros(len(self.simplices), dtype=bool)
            for xy_i in self.xy_if:
                flipped |= _signed_triangle_areas(xy_i, self.simplices) <= 0.0
            self.simplices_flipped = flipped

        self.layers: list[LayerResult] = []
        self.t_build = 0.0
        self._build_layers()

    # ------------------------------------------------------------------
    def _build_layers(self) -> None:
        z = self.surfaces
        corner_thickness = z[:-1][:, self.simplices] - z[1:][:, self.simplices]
        negative = (corner_thickness < NEGATIVE_TOL).any(axis=2)
        deleted = (corner_thickness < self.pinchout_threshold_m).all(axis=2)
        retained = ~(negative | deleted)

        t0 = time.perf_counter()
        for li in range(self.n_layers):
            self.layers.append(
                self._build_layer(li, corner_thickness[li], negative[li],
                                  deleted[li], retained[li])
            )
        self.t_build = time.perf_counter() - t0

    # ------------------------------------------------------------------
    def _build_layer(self, layer_index, d, negative, deleted, retained) -> LayerResult:
        t0 = time.perf_counter()
        T = self.simplices
        node_idx = T[retained]                       # (P,3) 保留体元的节点索引
        zt = self.surfaces[layer_index][node_idx][..., None]    # (P,3,1)
        zb = self.surfaces[layer_index + 1][node_idx][..., None]
        xyt = self.xy_if[layer_index][node_idx]      # 逐界面水平位移支持
        xyb = self.xy_if[layer_index + 1][node_idx]
        corners = np.concatenate(
            [
                np.concatenate([xyt, zt], axis=2),
                np.concatenate([xyb, zb], axis=2),
            ],
            axis=1,
        )                                            # (P,6,3): [t0,t1,t2,b0,b1,b2]

        # 顶点→共享节点索引:随装配直接携带。
        # (旧实现用 _node_index_of_points 由 XY 反查,逐界面 XY 下会失效)
        node_ids = np.concatenate([node_idx, node_idx], axis=1).reshape(-1)

        rounded = np.round(corners.reshape(-1, 3), VERTEX_ROUND_DECIMALS)
        uniq, first_idx, inverse = np.unique(
            rounded, axis=0, return_index=True, return_inverse=True
        )
        ids = inverse.reshape(-1, 6)
        node_of_vertex = node_ids[first_idx]
        # 顶点属于哪个界面:corners 沿 axis=1 为 [t0,t1,t2,b0,b1,b2],
        # 扁平化后第 j 个分量 j<3 为顶面(本层上界面),否则底面。
        # 注意:扁平索引步长是 6 不是 3。
        iface_of_vertex = np.where(
            (first_idx % 6) < 3, layer_index, layer_index + 1
        ).astype(np.int32)
        t = ids[:, :3]
        b = ids[:, 3:]
        collapsed = t == b                           # (P,3) 上下顶点重合
        n_collapsed = collapsed.sum(axis=1)
        if n_collapsed.max() > 2:
            raise RuntimeError("保留体元出现三个重合顶点,与完全尖灭删除规则矛盾")

        d_ret = d[retained]
        if self._uniform_xy:
            # 上下三角形 XY 一致(侧面竖直): A·(h1+h2+h3)/3 精确
            cell_volume = self.triangle_areas_m2[retained] * d_ret.sum(axis=1) / 3.0
        else:
            # 逐界面水平位移:侧面扭曲,必须按六面体分解求积
            cell_volume = _hexa_volumes(corners[:, :3], corners[:, 3:])
        analytic_volume = float(cell_volume.sum())

        surface, node_of_vertex = self._assemble_surface(
            uniq, t, b, layer_index, node_of_vertex
        )
        grid, elem_counts = self._assemble_volume_grid(
            uniq, t, b, collapsed, d_ret, cell_volume, layer_index, node_idx
        )

        n_ret = int(retained.sum())
        result = LayerResult(
            layer_index=layer_index + 1,
            top_interface=layer_index,
            candidate_prisms=int(len(T)),
            deleted_prisms=int(deleted.sum()),
            negative_prisms=int(negative.sum()),
            retained_prisms=n_ret,
            partial_pinchout_prisms=int((n_collapsed > 0).sum()),
            flipped_prisms=int((self.simplices_flipped[retained]).sum()),
            element_counts=elem_counts,
            analytic_volume_m3=analytic_volume,
            surface_mesh=surface,
            volume_grid=grid,
            vertex_node_index=node_of_vertex,
            vertex_interface_index=iface_of_vertex,
            build_seconds=0.0,
        )
        result.build_seconds = time.perf_counter() - t0
        return result

    # ------------------------------------------------------------------
    def _node_index_of_points(self, points_xy: np.ndarray) -> np.ndarray:
        """把唯一顶点的 XY 匹配回共享网格节点索引。"""
        node_keys = np.round(self.xy, VERTEX_ROUND_DECIMALS)
        node_u, node_inv = np.unique(node_keys, axis=0, return_inverse=True)
        node_inv = node_inv.reshape(-1)
        order = np.lexsort((node_u[:, 1], node_u[:, 0]))
        pos = np.searchsorted(
            _lex_view(node_u[order]), _lex_view(points_xy)
        )
        pos = np.clip(pos, 0, len(node_u) - 1)
        matched = node_u[order][pos]
        if not np.array_equal(matched, points_xy):
            raise RuntimeError("顶点 XY 无法匹配回共享网格节点")
        return node_inv[order][pos]

    # ------------------------------------------------------------------
    def _assemble_surface(self, uniq, t, b, layer_index, node_of_vertex=None):
        """分层表面网格:顶/底三角 + 侧面(退化折叠) + 无向键去重。"""
        # 侧面四边形 (t_a, t_b, b_b, b_a)
        sides = np.stack(
            [
                np.stack([t[:, 0], t[:, 1], b[:, 1], b[:, 0]], axis=1),
                np.stack([t[:, 1], t[:, 2], b[:, 2], b[:, 1]], axis=1),
                np.stack([t[:, 2], t[:, 0], b[:, 0], b[:, 2]], axis=1),
            ],
            axis=1,
        )                                            # (P,3,4)
        ta, tb, bb, ba = (sides[:, :, k] for k in range(4))
        m_a = ta == ba                               # t_a==b_a 重合
        m_b = tb == bb                               # t_b==b_b 重合

        keep_quad = ~(m_a | m_b)
        tri_b = np.stack([ta[m_b & ~m_a], tb[m_b & ~m_a], ba[m_b & ~m_a]], axis=1)
        tri_a = np.stack([ta[m_a & ~m_b], tb[m_a & ~m_b], bb[m_a & ~m_b]], axis=1)

        all3 = np.vstack([t, b, tri_b, tri_a])
        all4 = sides[keep_quad]

        n3 = len(all3)
        keys = np.full((n3 + len(all4), 4), -1, dtype=np.int64)
        keys[:n3, :3] = np.sort(all3, axis=1)
        keys[n3:] = np.sort(all4, axis=1)
        _, inverse, counts = np.unique(keys, axis=0, return_inverse=True,
                                       return_counts=True)
        inverse = inverse.reshape(-1)
        keep = counts[inverse] == 1
        kept3 = all3[keep[:n3]]
        kept4 = all4[keep[n3:]]

        f3 = np.hstack([np.full((len(kept3), 1), 3, dtype=np.int64), kept3]).ravel()
        f4 = np.hstack([np.full((len(kept4), 1), 4, dtype=np.int64), kept4]).ravel()
        faces = np.concatenate([f3, f4])
        mesh = pv.PolyData(uniq, faces)

        # ---- 逐顶点属性(供第6章 Three.js 主题着色与点选查询) ----
        if node_of_vertex is None:
            node_of_vertex = self._node_index_of_points(uniq[:, :2])
        h = self.surfaces[layer_index] - self.surfaces[layer_index + 1]
        mesh.point_data["_thickness_m"] = h[node_of_vertex].astype(np.float32)
        mesh.point_data["_node_index"] = node_of_vertex.astype(np.float32)
        if self.latent_std is not None:
            std_mean = 0.5 * (
                self.latent_std[layer_index] + self.latent_std[layer_index + 1]
            )
            mesh.point_data["_interface_std_mean_m"] = std_mean[
                node_of_vertex
            ].astype(np.float32)
        if self.pinchout_masks is not None:
            mesh.point_data["_pinchout_node"] = self.pinchout_masks[layer_index][
                node_of_vertex
            ].astype(np.float32)
        return mesh, node_of_vertex

    # ------------------------------------------------------------------
    def _assemble_volume_grid(self, uniq, t, b, collapsed, d_ret, cell_volume,
                              layer_index, retained_nodes):
        """显式体网格:0重合→wedge,1重合→pyramid,2重合→tetra。"""
        n_collapsed = collapsed.sum(axis=1)

        wedge_mask = n_collapsed == 0
        pyr_mask = n_collapsed == 1
        tet_mask = n_collapsed == 2

        cells = []
        celltypes = []
        elem_counts = {"wedge": 0, "pyramid": 0, "tetra": 0}

        if wedge_mask.any():
            w = np.hstack([
                np.full((int(wedge_mask.sum()), 1), 6, dtype=np.int64),
                b[wedge_mask], t[wedge_mask],
            ])
            cells.append(w)
            celltypes.append(np.full(len(w), pv.CellType.WEDGE, dtype=np.uint8))
            elem_counts["wedge"] = int(wedge_mask.sum())

        if pyr_mask.any():
            c = np.argmax(collapsed[pyr_mask], axis=1)
            i_idx = np.select([c == 0, c == 1, c == 2], [1, 0, 0])
            j_idx = np.select([c == 0, c == 1, c == 2], [2, 2, 1])
            tp = t[pyr_mask]
            bp = b[pyr_mask]
            rows_p = np.arange(len(tp))
            base = np.stack(
                [tp[rows_p, i_idx], tp[rows_p, j_idx],
                 bp[rows_p, j_idx], bp[rows_p, i_idx]],
                axis=1,
            )
            p = np.hstack([
                np.full((len(base), 1), 5, dtype=np.int64),
                base,
                tp[rows_p, c][:, None],
            ])
            cells.append(p)
            celltypes.append(np.full(len(p), pv.CellType.PYRAMID, dtype=np.uint8))
            elem_counts["pyramid"] = int(pyr_mask.sum())

        if tet_mask.any():
            r = np.argmin(collapsed[tet_mask], axis=1)
            c1 = np.argmax(collapsed[tet_mask], axis=1)
            c2 = 3 - r - c1
            tt = t[tet_mask]
            bt = b[tet_mask]
            tet = np.stack(
                [
                    tt[np.arange(len(tt)), r],
                    tt[np.arange(len(tt)), c1],
                    tt[np.arange(len(tt)), c2],
                    bt[np.arange(len(bt)), r],
                ],
                axis=1,
            )
            cells.append(np.hstack([
                np.full((len(tet), 1), 4, dtype=np.int64), tet
            ]))
            celltypes.append(np.full(len(tet), pv.CellType.TETRA, dtype=np.uint8))
            elem_counts["tetra"] = int(tet_mask.sum())

        # 各单元块行宽不同([n,ids...]格式),逐块展平后拼接为 VTK 单元数组
        cells_flat = np.concatenate([block.ravel() for block in cells])
        types = np.concatenate(celltypes)
        grid = pv.UnstructuredGrid(cells_flat, types, uniq)

        n = len(t)
        grid.cell_data["layer_index"] = np.full(n, layer_index + 1, dtype=np.int32)
        grid.cell_data["element_type"] = np.select(
            [n_collapsed == 0, n_collapsed == 1, n_collapsed == 2], [1, 2, 3]
        ).astype(np.int32)
        grid.cell_data["volume_m3"] = cell_volume.astype(np.float64)
        grid.cell_data["thickness_mean_m"] = d_ret.mean(axis=1).astype(np.float32)
        grid.cell_data["thickness_max_m"] = d_ret.max(axis=1).astype(np.float32)
        grid.cell_data["thickness_min_m"] = d_ret.min(axis=1).astype(np.float32)
        if self.latent_std is not None:
            # 三个角点处上下界面标准差均值的平均
            std_node_mean = 0.5 * (
                self.latent_std[layer_index] + self.latent_std[layer_index + 1]
            )
            grid.cell_data["interface_std_mean_m"] = std_node_mean[
                retained_nodes
            ].mean(axis=1).astype(np.float32)
        return grid, elem_counts
