"""
面向第6章 Three.js 可视化系统的模型交付包导出。

输出内容(由 build_chapter05_web_package.py 调用):
1. 分层 GLB(真实米制坐标,顶点级属性随 GLB 自定义 attribute 导出,
   并写入顶点色作为缺省视觉),供 three.js GLTFLoader 直接加载;
2. LOD 减面版本(pyvista decimate_pro,仅供视觉分级,不携带属性);
3. 分层显式体网格 VTU(wedge/pyramid/tetra + 单元属性),供 ParaView
   与后续体网格消费;
4. catalog.json 元数据:坐标恢复公式、逐层名称/配色/统计/包围盒、
   属性字典、LOD 清单,第6章前端据此数据驱动地组织场景。

注:Draco 压缩因当前平台的 draco 编码器无法安装而未启用;分层拆分 +
LOD 已能保证单文件在 MB 级。若后续启用,three.js 端 DRACOLoader 即插即用。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyvista as pv
import trimesh


def _faces_to_triangles(mesh: pv.PolyData) -> np.ndarray:
    """把 PolyData 的面表统一拆成三角形 (F,3)。"""
    tri = mesh.triangulate()
    faces = tri.faces.reshape(-1, 4)[:, 1:]
    return faces


def layer_to_trimesh(
    mesh: pv.PolyData,
    color_rgb: tuple[int, int, int],
    vertex_attrs: dict[str, np.ndarray] | None = None,
) -> trimesh.Trimesh:
    """
    分层表面 → trimesh。process=False 保持顶点顺序不变,
    保证 attributes 与顶点一一对应;顶点色写入 COLOR_0 作为缺省视觉。
    """
    points = np.asarray(mesh.points, dtype=np.float32)
    faces = _faces_to_triangles(mesh).astype(np.int64)
    tm = trimesh.Trimesh(vertices=points, faces=faces, process=False)
    n = len(points)
    rgba = np.tile(np.array(list(color_rgb) + [255], dtype=np.uint8), (n, 1))
    tm.visual.vertex_colors = rgba
    if vertex_attrs:
        for key, value in vertex_attrs.items():
            tm.vertex_attributes[key] = np.asarray(value)
    return tm


def export_layer_glb(
    tm: trimesh.Trimesh, output_path: Path
) -> dict:
    """导出单层 GLB 并回读校验,返回 {path, bytes, vertex_attributes_kept}。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    tm.export(str(output_path), file_type="glb")
    size = output_path.stat().st_size

    kept = False
    try:
        reloaded = trimesh.load(str(output_path), force="scene")
        first = next(iter(reloaded.geometry.values()))
        kept = bool(first.vertex_attributes)
    except Exception:
        kept = False
    return {
        "path": str(output_path),
        "bytes": size,
        "vertex_attributes_kept": kept,
    }


def export_lods(
    mesh: pv.PolyData, output_dir: Path, code: str,
    reductions: dict[str, float] | None = None,
) -> list[dict]:
    """
    生成减面 LOD。减面只服务视觉分级,不保证属性与拓扑,
    因此 LOD 文件只带顶点色,不带自定义属性。
    """
    reductions = reductions or {"lod50": 0.5, "lod80": 0.8}
    tri = mesh.triangulate()
    entries = []
    for name, reduction in reductions.items():
        decimated = tri.decimate_pro(
            reduction=reduction, preserve_topology=True
        )
        tm = trimesh.Trimesh(
            vertices=np.asarray(decimated.points, dtype=np.float32),
            faces=decimated.faces.reshape(-1, 4)[:, 1:].astype(np.int64),
            process=False,
        )
        path = output_dir / f"{code}_{name}.glb"
        if path.exists():
            path.unlink()
        tm.export(str(path), file_type="glb")
        entries.append({
            "name": name,
            "target_reduction": reduction,
            "path": str(path),
            "bytes": path.stat().st_size,
            "vertices": int(decimated.n_points),
            "triangles": int(decimated.n_cells),
        })
    return entries


def export_vtu(grid: pv.UnstructuredGrid, output_path: Path) -> dict:
    """导出显式体网格 VTU。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(str(output_path))
    return {"path": str(output_path), "bytes": output_path.stat().st_size}


def vertex_attribute_arrays(layer: "LayerResultLike") -> dict[str, np.ndarray]:
    """从分层结果的表面网格提取随 GLB 导出的顶点属性。"""
    mesh = layer.surface_mesh
    arrays = {}
    for key in ("_thickness_m", "_interface_std_mean_m", "_node_index",
                "_pinchout_node"):
        if key in mesh.point_data:
            arrays[key] = np.asarray(mesh.point_data[key])
    return arrays


def write_catalog(catalog: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# 仅用于类型标注的协议占位,避免循环导入
class LayerResultLike:
    surface_mesh: pv.PolyData
