"""勘探线剖面：剖线 × 分层 GLB 闭合壳求交，输出 (沿线距离, 标高) 矢量剖面。

分层 GLB 由 modeling_engine 导出为闭合壳体（顶面 TIN + 底面 TIN + 边界裙边），
竖直剖切面与闭合壳的交线即该层剖面轮廓；对逐层交线做 2D 多边形填充即可得到
连续的勘探线剖面图（钻孔柱状叠加其上）。

坐标系约定（与 catalog origin_restore 一致）：
- 入参 a/b 为高斯-克吕格投影坐标（米），与钻孔表 x/y 同基准；
- GLB 顶点为局部坐标 x_local = X - origin_x, y_local = Y - origin_y,
  z_local = 高程 - origin_z（未夸张，z 轴向上）；
- 输出 z 一律换算回真实标高（z_local + origin_z），s 为沿线距离（A 点为 0）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import trimesh

from app.core.config import settings


@dataclass
class LayerModelFile:
    """参与剖切的分层模型文件。"""

    code: str
    name: str
    color: str
    path: Path


def resolve_layer_files(
    rows: Sequence[tuple[str, Mapping[str, Any], str, str]],
) -> list[LayerModelFile]:
    """把 (asset_name, metadata, storage_scope, file_path) 行解析为按层序排序的文件清单。

    文件根目录与 models API 的下载逻辑一致：upload → uploads/，
    server_static → server/static/models/。缺失/无效的文件跳过。
    """
    roots = {
        "upload": settings.upload_path,
        "server_static": settings.source_model_path,
    }
    layers: list[LayerModelFile] = []
    for asset_name, metadata, scope, file_path in rows:
        if not file_path:
            continue
        # 合并模型(catalog_code=COMBINED,无 layer_index)不参与剖面，逐层壳体才有意义
        layer_index = metadata.get("layer_index")
        if not isinstance(layer_index, (int, float)) or int(layer_index) < 1:
            continue
        root = roots.get(scope)
        if root is None:
            continue
        path = (root / file_path).resolve()
        # 新交付包的分层 GLB 含内部棱柱壁(剖切视觉用)，剖面求交改用
        # shells/ 下的闭合壳；旧包没有 shells/ 时回退分层 GLB 本身。
        shell_path = path.parent / "shells" / f"{path.stem}_shell.glb"
        if shell_path.is_file():
            path = shell_path
        if not path.is_file():
            continue
        code = str(metadata.get("catalog_code") or Path(file_path).stem)
        name = asset_name or code
        color = str(metadata.get("color_hex") or "#7b8d78")
        layers.append(LayerModelFile(code=code, name=name, color=color, path=path))

    def sort_key(layer: LayerModelFile) -> tuple[int, str]:
        digits = "".join(ch for ch in layer.code if ch.isdigit())
        return (int(digits) if digits else 10**6, layer.code)

    layers.sort(key=sort_key)
    return layers


_MESH_CACHE: dict[str, tuple[float, trimesh.Trimesh]] = {}


def _load_mesh(path: Path) -> trimesh.Trimesh:
    """按 path+mtime 缓存加载 GLB 网格。"""
    stat = path.stat()
    key = str(path)
    cached = _MESH_CACHE.get(key)
    if cached and cached[0] == stat.st_mtime:
        return cached[1]
    mesh = trimesh.load(key, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"模型文件不含网格: {path.name}")
    _MESH_CACHE[key] = (stat.st_mtime, mesh)
    return mesh


def _slice_mesh_loops(
    mesh: trimesh.Trimesh,
    plane_origin: tuple[float, float, float],
    plane_normal: tuple[float, float, float],
) -> list[list[tuple[float, float, float]]]:
    """竖直平面切闭合壳，返回每条闭环的 3D 顶点序列。

    平面-三角形求交 + 端点配对拼环，避免 trimesh.section 对 networkx 的依赖。
    """
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normal = np.asarray(plane_normal, dtype=np.float64)
    origin = np.asarray(plane_origin, dtype=np.float64)
    # 规则格网模型(100m 点距)的剖线常与网格线/顶点重合，把平面临界外推 1mm
    # 消除“顶点恰在面上”的退化相交。平面为竖直面、外推沿水平法向，因此 s/标高
    # 坐标不受影响(只把剖线在平面内横移了 1mm)。
    origin = origin + normal * 1e-3
    signed = (verts - origin) @ normal

    eps = 1e-9
    edges = faces[:, [[0, 1], [1, 2], [2, 0]]]
    da = signed[edges[:, :, 0]]
    db = signed[edges[:, :, 1]]
    crossing = ((da > eps) & (db < -eps)) | ((da < -eps) & (db > eps))
    if not crossing.any():
        return []

    face_idx, edge_idx = np.nonzero(crossing)
    t = da[face_idx, edge_idx] / (da[face_idx, edge_idx] - db[face_idx, edge_idx])
    a_idx = edges[face_idx, edge_idx, 0]
    b_idx = edges[face_idx, edge_idx, 1]
    points = verts[a_idx] + (verts[b_idx] - verts[a_idx]) * t[:, None]

    # 每个跨越面恰好两条相交边 → 一条线段；顶点恰好触面的退化面跳过
    unique_faces, counts = np.unique(face_idx, return_counts=True)
    valid = np.isin(face_idx, unique_faces[counts == 2])
    face_idx = face_idx[valid]
    points = points[valid]
    if len(points) < 2 or len(points) % 2 != 0:
        return []

    segments = points.reshape(-1, 2, 3)
    loops = _chain_segments(segments)
    return [
        [(float(p[0]), float(p[1]), float(p[2])) for p in loop] for loop in loops
    ]


def _chain_segments(
    segments: np.ndarray, tol: float = 1e-4
) -> list[np.ndarray]:
    """把无序线段按共享端点拼成折线/闭环（闭合壳交线应全部闭环）。"""
    inv_tol = 1.0 / tol

    def key(point: np.ndarray) -> tuple[float, float, float]:
        return tuple(np.round(point * inv_tol))

    # 端点 → (线段号, 端点侧) 邻接表
    adjacency: dict[tuple[float, float, float], list[tuple[int, int]]] = {}
    for seg_idx, seg in enumerate(segments):
        for side in (0, 1):
            adjacency.setdefault(key(seg[side]), []).append((seg_idx, side))

    visited = np.zeros(len(segments), dtype=bool)
    loops: list[np.ndarray] = []
    for start in range(len(segments)):
        if visited[start]:
            continue
        visited[start] = True
        chain = [segments[start][0], segments[start][1]]
        # 沿链尾端点向前走
        while True:
            tail = chain[-1]
            candidates = [
                (seg_idx, side)
                for seg_idx, side in adjacency.get(key(tail), [])
                if not visited[seg_idx]
            ]
            if not candidates:
                break
            seg_idx, side = candidates[0]
            visited[seg_idx] = True
            chain.append(segments[seg_idx][1 - side])
            if key(chain[-1]) == key(chain[0]):
                break
        if len(chain) >= 3:
            loops.append(np.asarray(chain))
    return loops


def _loop_area_2d(points: Sequence[tuple[float, float]]) -> float:
    area = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def compute_section(
    layers: Sequence[LayerModelFile],
    ax: float,
    ay: float,
    bx: float,
    by: float,
    origin: Mapping[str, float],
) -> dict[str, Any]:
    """对分层 GLB 求剖线交线，返回剖面矢量数据（s 沿线距离 m / z 真实标高 m）。"""
    ax_local = ax - float(origin["x"])
    ay_local = ay - float(origin["y"])
    bx_local = bx - float(origin["x"])
    by_local = by - float(origin["y"])
    z_origin = float(origin["z"])

    dx = bx_local - ax_local
    dy = by_local - ay_local
    length = math.hypot(dx, dy)
    if length < 1e-6:
        raise ValueError("剖面线两端点重合")
    ux = dx / length
    uy = dy / length
    # 竖直剖切面在 GLB 局部坐标系里的水平法向
    nx = -uy
    ny = ux

    result_layers: list[dict[str, Any]] = []
    skipped: list[str] = []
    z_min = math.inf
    z_max = -math.inf
    for layer in layers:
        try:
            mesh = _load_mesh(layer.path)
        except (OSError, ValueError):
            skipped.append(layer.code)
            continue
        loops_local = _slice_mesh_loops(
            mesh, (ax_local, ay_local, 0.0), (nx, ny, 0.0)
        )
        loops_out: list[list[list[float]]] = []
        for loop in loops_local:
            sz: list[tuple[float, float]] = []
            for px, py, pz in loop:
                s = (px - ax_local) * ux + (py - ay_local) * uy
                z = pz + z_origin
                sz.append((round(s, 2), round(z, 2)))
            # 丢弃退化碎环（尖灭面贴合产生的发丝环）
            if _loop_area_2d(sz) < 1.0:
                continue
            loops_out.append([[s, z] for s, z in sz])
            z_min = min(z_min, min(z for _, z in sz))
            z_max = max(z_max, max(z for _, z in sz))
        result_layers.append(
            {
                "code": layer.code,
                "name": layer.name,
                "color": layer.color,
                "loops": loops_out,
            }
        )

    if z_min is math.inf:
        z_min = None
        z_max = None
    return {
        "a": {"x": ax, "y": ay},
        "b": {"x": bx, "y": by},
        "length_m": round(length, 2),
        "z_origin_m": round(z_origin, 3),
        "z_range": [z_min, z_max],
        "layer_count": len(result_layers),
        "layers": result_layers,
        "skipped": skipped,
    }
