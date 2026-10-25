"""web 交付包构建(移植自论文 chapter05 build_chapter05_web_package_refined.py)。

向量化 TIN-GTP 建模(PrismModel) + 自洽断言 + 分层 GLB/LOD/VTU + 20 倍竖向
缩放副本 + catalog.json。与论文实现的差异:目录/参数全部入参,层名颜色由
层名推导,不复制井巷 GLB(锦界专属数据),catalog 不含绝对路径。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from modeling_engine.model_package_export import (
    export_layer_glb,
    export_lods,
    export_vtu,
    layer_to_trimesh,
    vertex_attribute_arrays,
    write_catalog,
)
from modeling_engine.prism_model_builder import (
    VERTEX_ROUND_DECIMALS,
    PrismModel,
    edge_diagnostics,
)

# 与锦界包一致的按岩性类别配色;未识别层名回退中性色。
_COLOR_BY_KIND = {
    "风积砂层": "#D9C7A3", "土层": "#CDBB8C",
    "泥岩槽": "#8C6D5A", "砂岩槽": "#D98C5F",
    "煤顶泥岩层": "#7A8793", "煤3-1": "#333333",
    "直接底层": "#C98E5B", "下伏岩层": "#8D7465",
}


def layer_color(name: str) -> str:
    if name in _COLOR_BY_KIND:
        return _COLOR_BY_KIND[name]
    if "旋回泥岩" in name:
        return _COLOR_BY_KIND["泥岩槽"]
    if "旋回砂岩" in name:
        return _COLOR_BY_KIND["砂岩槽"]
    return "#B0A48F"


def layer_codes(n_layers: int) -> list[str]:
    return [f"L{i + 1:02d}" for i in range(n_layers)]


def _rebuild_layer_topology(model: PrismModel, layer_index: int):
    """复现构建器内部的焊接拓扑(与 prism_model_builder._build_layer 前半一致)。"""
    T = model.simplices
    z = model.surfaces
    corner_thickness = z[:-1][:, T] - z[1:][:, T]
    negative = (corner_thickness < -1e-8).any(axis=2)
    deleted = (corner_thickness < model.pinchout_threshold_m).all(axis=2)
    retained = ~(negative | deleted)
    node_idx = T[retained[layer_index]]
    zt = z[layer_index][node_idx][..., None]
    zb = z[layer_index + 1][node_idx][..., None]
    corners = np.concatenate(
        [np.concatenate([model.xy[node_idx], zt], axis=2),
         np.concatenate([model.xy[node_idx], zb], axis=2)],
        axis=1,
    )
    rounded = np.round(corners.reshape(-1, 3), VERTEX_ROUND_DECIMALS)
    uniq, inverse = np.unique(rounded, axis=0, return_inverse=True)
    ids = inverse.reshape(-1, 6)
    return uniq, ids[:, :3], ids[:, 3:], corner_thickness[layer_index], negative[layer_index], deleted[layer_index], retained


def _semantic_volume_and_expected_keys(model: PrismModel, layer_index: int):
    """按构建语义定向的第二体积源 + 预期去重面片键集(不依赖 vtk 定向)。"""
    uniq, t, b, d, negative, deleted, retained = _rebuild_layer_topology(model, layer_index)
    pts3 = uniq[:, :]

    def signed_vol(tri):
        p = pts3[tri]
        return np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])) / 6.0

    vol = signed_vol(t).sum() - signed_vol(b).sum()

    sides = np.stack(
        [np.stack([t[:, 0], t[:, 1], b[:, 1], b[:, 0]], axis=1),
         np.stack([t[:, 1], t[:, 2], b[:, 2], b[:, 1]], axis=1),
         np.stack([t[:, 2], t[:, 0], b[:, 0], b[:, 2]], axis=1)], axis=1)
    ta, tb, bb, ba = (sides[:, :, k] for k in range(4))
    m_a, m_b = ta == ba, tb == bb
    centroid = pts3[np.concatenate([t, b], axis=1)].mean(axis=1)

    idx_b = np.where(m_b & ~m_a)[0]
    tri_b = np.stack([ta[m_b & ~m_a], tb[m_b & ~m_a], ba[m_b & ~m_a]], axis=1)
    idx_a = np.where(m_a & ~m_b)[0]
    tri_a = np.stack([ta[m_a & ~m_b], tb[m_a & ~m_b], bb[m_a & ~m_b]], axis=1)

    def oriented_sum(tri, prism_idx):
        sv = signed_vol(tri)
        fc = pts3[tri].mean(axis=1)
        n = np.cross(pts3[tri][:, 1] - pts3[tri][:, 0], pts3[tri][:, 2] - pts3[tri][:, 0])
        flip = np.einsum("ij,ij->i", n, fc - centroid[prism_idx]) < 0
        return np.where(flip, -sv, sv).sum()

    vol += oriented_sum(tri_b, idx_b) + oriented_sum(tri_a, idx_a)

    mask_q = ~(m_a | m_b)
    pj = np.argwhere(mask_q)
    quads = sides[mask_q]
    if len(quads):
        qtri = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]], axis=0)
        vol += oriented_sum(qtri, np.concatenate([pj[:, 0], pj[:, 0]]))

    all3 = np.vstack([t, b, tri_b, tri_a])
    all4 = sides[~(m_a | m_b)]
    n3 = len(all3)
    keys = np.full((n3 + len(all4), 4), -1, dtype=np.int64)
    keys[:n3, :3] = np.sort(all3, axis=1)
    keys[n3:] = np.sort(all4, axis=1)
    uk, _, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    expected = set()
    for k in uk[counts == 1]:
        expected.add(tuple(int(x) for x in k[:3]) if k[3] == -1 else tuple(int(x) for x in k))
    return float(vol), expected


def _mesh_face_keys(mesh) -> set:
    raw = mesh.faces
    out = set()
    i = 0
    while i < len(raw):
        n = int(raw[i])
        out.add(tuple(sorted(int(v) for v in raw[i + 1:i + 1 + n])))
        i += 1 + n
    return out


def consistency_check(model: PrismModel, layer_names: list[str], total_volume: float) -> dict:
    """自洽断言:水密/负厚/单元守恒恒断言;体积闭合用构建语义定向积分。"""
    codes = layer_codes(len(layer_names))
    problems, records = [], []
    for li, layer in enumerate(model.layers):
        code = codes[li]
        boundary, non_manifold, manifold = edge_diagnostics(layer.surface_mesh)
        if boundary != 0:
            problems.append(f"{code} 开放边 {boundary} ≠ 0")
        if layer.retained_prisms + layer.deleted_prisms + layer.negative_prisms != layer.candidate_prisms:
            problems.append(f"{code} 棱柱守恒不成立")
        if sum(layer.element_counts.values()) != layer.retained_prisms:
            problems.append(f"{code} 单元数≠保留棱柱数")
        sem_vol, expected_keys = _semantic_volume_and_expected_keys(model, li)
        rel = abs(sem_vol - layer.analytic_volume_m3) / layer.analytic_volume_m3
        if rel > 1e-7:
            problems.append(f"{code} 语义积分与解析体积偏差过大: rel={rel:.3e}")
        if _mesh_face_keys(layer.surface_mesh) != expected_keys:
            problems.append(f"{code} 表面网格面片集与去重预期不一致(装配校验失败)")
        records.append({
            "layer": code,
            "boundary_edges": boundary,
            "non_manifold_edges": non_manifold,
            "is_manifold": manifold,
            "semantic_integral_rel_dev": rel,
            "note": ("尖灭相触(上下片零厚度贴合)非流形边,不做拓扑修复;"
                     "体积以解析公式与语义定向积分双重校验" if non_manifold else ""),
        })
    if abs(total_volume - sum(l.analytic_volume_m3 for l in model.layers)) > 1e-3:
        problems.append("总体积与逐层和不一致")
    if problems:
        raise RuntimeError("自洽断言失败:\n" + "\n".join(problems))
    return {
        "pass": True,
        "total_points": int(sum(l.surface_mesh.n_points for l in model.layers)),
        "total_cells": int(sum(l.surface_mesh.n_cells for l in model.layers)),
        "total_volume_m3": total_volume,
        "edge_integrity": records,
        "manifold_layers": int(sum(1 for r in records if r["non_manifold_edges"] == 0)),
        "pinch_contact_layers": int(sum(1 for r in records if r["non_manifold_edges"] > 0)),
    }


def write_readme(catalog: dict, package_dir: Path) -> None:
    totals = catalog["totals"]
    contact = [r["layer"] for r in catalog["edge_integrity"] if r["non_manifold_edges"] > 0]
    lines = [
        "# 钻孔地质模型交付包",
        "",
        "> 由 GeoMine3D 建模引擎(modeling_engine)自动生成。",
        "",
        "## 层序(自上而下)",
        "",
        "| 代码 | 层名 | 颜色 | 体积(百万m³) |",
        "|---|---|---|---|",
    ]
    for entry in catalog["layers"]:
        lines.append(f"| {entry['code']} | {entry['name_cn']} | {entry['color_hex']} "
                     f"| {entry['stats']['volume_m3'] / 1e6:,.1f} |")
    lines += [
        "",
        "## 坐标口径",
        "",
        f"- 局部米制坐标:`x_global = x_local + {catalog['origin_restore']['x_origin_m']:.3f}`,"
        f"`y_global = y_local + {catalog['origin_restore']['y_origin_m']:.3f}`,"
        f"`z_global = z_local + {catalog['origin_restore']['z_origin_m']:.3f}`;",
        "",
        "## 双尺度模型",
        "",
        "- **原始尺寸**:根目录 `model_combined.glb` 与分层 `L*.glb`(真实高程,米);",
        f"- **{catalog['z20_models']['scale_z']:.0f}倍竖向缩放**:`z20/` 目录(几何 = 真实尺度 z×"
        f"{catalog['z20_models']['scale_z']:.0f},顶点属性不变),展示端直接加载、无需再缩放;",
        "",
        "## 顶点属性(GLB 内嵌)",
        "",
        "- `_thickness_m` 顶点处本层厚度;`_interface_std_mean_m` 上下界面GP标准差均值;",
        "- `_node_index` 共享网格节点索引;`_pinchout_node` 该节点是否处于数值尖灭候选区。",
        "",
        "## 已知事项:尖灭相触非流形边",
        "",
        f"- 合计 {totals['pinch_contact_layers']} 个层存在非流形边(尖灭线两侧楔形体厚度收敛到零,"
        "上下两张曲面片在脊线上贴合):",
        f"  {', '.join(contact) if contact else '无'};",
        "- 这是零厚度接触的固有几何,不影响渲染/解析体积/体网格;体积闭合校验采用"
        "**构建语义定向积分**(顶面朝上、底面朝下、侧面朝棱柱外侧),非流形边逐层记录于 catalog.json 的 edge_integrity。",
    ]
    (package_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def build_web_package(
    xy_global: np.ndarray,
    surfaces: np.ndarray,
    pinchout_masks: np.ndarray,
    latent_std_arr: np.ndarray,
    pinchout_threshold_m: float,
    layer_names: list[str],
    package_dir: Path,
    z_scale: float = 20.0,
    source_meta: dict[str, Any] | None = None,
    progress: callable | None = None,
) -> dict[str, Any]:
    """由校正后曲面构建完整交付包,返回 {catalog, model, summary}。"""
    t_start = time.time()
    if surfaces.ndim != 2 or surfaces.shape[0] != len(layer_names) + 1:
        raise ValueError(
            f"曲面形状异常: {surfaces.shape}, 应为 ({len(layer_names) + 1}, 节点数)"
        )
    if surfaces.shape[1] != len(xy_global):
        raise ValueError("曲面节点数与共享网格不一致")
    if pinchout_masks.shape != (len(layer_names), len(xy_global)):
        raise ValueError("尖灭掩膜形状与层数/节点数不一致")

    for sub in ("lods", "vtu", "attributes"):
        (package_dir / sub).mkdir(parents=True, exist_ok=True)

    origin = np.array([xy_global[:, 0].mean(), xy_global[:, 1].mean(), surfaces.mean()])
    xy_local = xy_global - origin[:2]
    surfaces_local = surfaces - origin[2]

    if progress is not None:
        progress("向量化 TIN-GTP 建模中")
    t0 = time.time()
    model = PrismModel(
        xy_local, surfaces_local,
        pinchout_threshold_m=pinchout_threshold_m,
        latent_std=latent_std_arr,
        pinchout_masks=pinchout_masks,
    )
    t_build = time.time() - t0

    codes = layer_codes(len(layer_names))
    colors = [layer_color(name) for name in layer_names]
    total_volume = sum(l.analytic_volume_m3 for l in model.layers)
    if progress is not None:
        progress("自洽断言校验中")
    regression = consistency_check(model, layer_names, total_volume)

    layer_entries, attrs_in_glb_all, layer_meshes = [], True, {}
    for li, layer in enumerate(model.layers):
        code = codes[li]
        color = tuple(int(colors[li][k:k + 2], 16) for k in (1, 3, 5))
        attrs = vertex_attribute_arrays(layer)
        tm = layer_to_trimesh(layer.surface_mesh, color, attrs)
        layer_meshes[code] = tm
        glb_info = export_layer_glb(tm, package_dir / f"{code}.glb")
        if not glb_info["vertex_attributes_kept"]:
            attrs_in_glb_all = False
            np.savez_compressed(package_dir / "attributes" / f"{code}_attributes.npz", **attrs)
        lods = export_lods(layer.surface_mesh, package_dir / "lods", code)
        vtu_info = export_vtu(layer.volume_grid, package_dir / "vtu" / f"{code}.vtu")
        h = surfaces[li] - surfaces[li + 1]
        pts = layer.surface_mesh.points
        layer_entries.append({
            "index": li + 1, "code": code, "name_cn": layer_names[li],
            "color_hex": colors[li], "glb": glb_info, "lods": lods, "vtu": vtu_info,
            "vertex_attributes_in_glb": glb_info["vertex_attributes_kept"],
            "bounds_local": {"min": pts.min(axis=0).tolist(), "max": pts.max(axis=0).tolist()},
            "stats": {
                "candidate_prisms": layer.candidate_prisms,
                "retained_prisms": layer.retained_prisms,
                "deleted_prisms": layer.deleted_prisms,
                "partial_pinchout_prisms": layer.partial_pinchout_prisms,
                "elements": layer.element_counts,
                "volume_m3": layer.analytic_volume_m3,
                "mean_thickness_m": float(h.mean()),
                "surface_points": int(layer.surface_mesh.n_points),
                "surface_cells": int(layer.surface_mesh.n_cells),
            },
        })
        if progress is not None:
            progress(f"导出 {code} {layer_names[li]}")

    combined_path = package_dir / "model_combined.glb"
    if combined_path.exists():
        combined_path.unlink()
    scene = trimesh.Scene()
    for code in codes:
        scene.add_geometry(layer_meshes[code], node_name=code)
    scene.export(str(combined_path), file_type="glb")

    # 双尺度固定产物:z 顶点预乘缩放系数的副本(显示端直接加载免缩放)。
    z20_dir = package_dir / "z20"
    z20_dir.mkdir(exist_ok=True)
    z20_files: dict[str, int] = {}
    scene20 = trimesh.Scene()
    for code in codes:
        tm20 = layer_meshes[code].copy()
        tm20.vertices = tm20.vertices * np.array([1.0, 1.0, z_scale])
        info20 = export_layer_glb(tm20, z20_dir / f"{code}_z20.glb")
        z20_files[f"{code}_z20.glb"] = info20["bytes"]
        scene20.add_geometry(tm20, node_name=code)
    combined20_path = z20_dir / "model_combined_z20.glb"
    scene20.export(str(combined20_path), file_type="glb")
    z20_files["model_combined_z20.glb"] = combined20_path.stat().st_size

    catalog: dict[str, Any] = {
        "schema_version": "1.0-refined",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "consumer": "three.js GLTFLoader(GeoMine3D)",
        "variant": "uploaded_boreholes_refined",
        "act_params": {"source": "uploaded refined strata table"},
        "source": source_meta or {},
        "units": {"length": "m", "elevation": "局部高程(m) = 真实高程 - z_origin_m,未夸张"},
        "origin_restore": {
            "x_origin_m": float(origin[0]), "y_origin_m": float(origin[1]),
            "z_origin_m": float(origin[2]),
            "formulas": {"x_global_m": "x_local + x_origin_m",
                         "y_global_m": "y_local + y_origin_m",
                         "z_global_m": "z_local + z_origin_m"},
            "display_recommendation": {"z_scale": z_scale,
                                       "note": "前端可用 mesh.scale.z = z_scale 竖向夸张,恢复真实比例时除回"},
        },
        "grid": {
            "shared_nodes": int(len(xy_local)), "spacing_m": 100.0,
            "triangles_per_layer": int(len(model.simplices)),
            "interfaces": len(layer_names) + 1, "geological_layers": len(layer_names),
            "pinchout_threshold_m": pinchout_threshold_m,
        },
        "attributes": {
            "_thickness_m": "顶点所在节点的地层厚度(m)",
            "_interface_std_mean_m": "顶点处上下界面GP标准差均值(m)",
            "_node_index": "共享网格节点索引",
            "_pinchout_node": "该节点是否为该层数值尖灭候选(1/0)",
        },
        "element_type_map": {"1": "wedge(正常GTP)", "2": "pyramid(单顶点尖灭)", "3": "tetra(双顶点尖灭)"},
        "edge_integrity": regression["edge_integrity"],
        "layers": layer_entries,
        "combined_glb": {"path": "model_combined.glb", "bytes": combined_path.stat().st_size},
        "z20_models": {
            "scale_z": z_scale,
            "dir": "z20/",
            "files_bytes": z20_files,
            "note": "竖向缩放副本(几何=真实尺度 z×scale,顶点属性不变),显示端直接加载免缩放;"
                    "根目录 GLB 为原始尺寸",
        },
        "totals": {
            **{k: v for k, v in regression.items() if k != "edge_integrity"},
            "candidate_prisms": int(sum(l.candidate_prisms for l in model.layers)),
            "retained_prisms": int(sum(l.retained_prisms for l in model.layers)),
            "deleted_prisms": int(sum(l.deleted_prisms for l in model.layers)),
            "partial_pinchout_prisms": int(sum(l.partial_pinchout_prisms for l in model.layers)),
        },
        "build_performance": {
            "delaunay_seconds": model.t_delaunay, "layer_build_seconds": model.t_build,
            "total_seconds": time.time() - t_start,
        },
    }
    write_catalog(catalog, package_dir / "catalog.json")
    write_readme(catalog, package_dir)

    summary = {
        "regression_pass": regression["pass"],
        "total_points": regression["total_points"],
        "total_cells": regression["total_cells"],
        "total_volume_m3": regression["total_volume_m3"],
        "manifold_layers": regression["manifold_layers"],
        "pinch_contact_layers": regression["pinch_contact_layers"],
        "vertex_attributes_in_glb": attrs_in_glb_all,
        "build_seconds": t_build,
        "elapsed_seconds": time.time() - t_start,
    }
    return {"catalog": catalog, "model": model, "summary": summary}
