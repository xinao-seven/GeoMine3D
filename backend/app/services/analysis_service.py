"""项目统计分析服务。

数值核心抽成纯函数，便于在不依赖数据库的情况下单元测试；
数据库聚合部分只负责取数，再把行记录交给纯函数计算。
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence


def thickness_distribution(
    segments: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """按地层名聚合厚度统计，结果按地层平均顶深排序。

    每条记录需包含 layer_name / top_depth / thickness。
    """
    buckets: dict[str, dict[str, Any]] = {}
    for row in segments:
        name = str(row.get("layer_name") or "").strip()
        if not name:
            continue
        thickness = float(row.get("thickness") or 0)
        top = float(row.get("top_depth") or 0)
        bucket = buckets.setdefault(
            name,
            {"layer_name": name, "count": 0, "total": 0.0, "min": math.inf, "max": -math.inf, "top_sum": 0.0},
        )
        bucket["count"] += 1
        bucket["total"] += thickness
        bucket["min"] = min(bucket["min"], thickness)
        bucket["max"] = max(bucket["max"], thickness)
        bucket["top_sum"] += top

    result = []
    for bucket in buckets.values():
        count = bucket["count"]
        result.append(
            {
                "layer_name": bucket["layer_name"],
                "count": count,
                "avg_thickness": round(bucket["total"] / count, 3) if count else 0.0,
                "min_thickness": round(bucket["min"], 3) if count else 0.0,
                "max_thickness": round(bucket["max"], 3) if count else 0.0,
                "avg_top_depth": round(bucket["top_sum"] / count, 3) if count else 0.0,
            }
        )
    result.sort(key=lambda item: item["avg_top_depth"])
    return result


def layer_frequency(segments: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """统计每个地层名出现在多少个钻孔中，按平均顶深排序。"""
    per_layer: dict[str, dict[str, Any]] = {}
    for row in segments:
        name = str(row.get("layer_name") or "").strip()
        if not name:
            continue
        bucket = per_layer.setdefault(
            name, {"borehole_ids": set(), "top_sum": 0.0, "top_count": 0}
        )
        borehole_id = row.get("borehole_id")
        if borehole_id:
            bucket["borehole_ids"].add(str(borehole_id))
        bucket["top_sum"] += float(row.get("top_depth") or 0)
        bucket["top_count"] += 1

    result = [
        {
            "layer_name": name,
            "borehole_count": len(bucket["borehole_ids"]),
            "avg_top_depth": round(bucket["top_sum"] / bucket["top_count"], 3)
            if bucket["top_count"]
            else 0.0,
        }
        for name, bucket in per_layer.items()
    ]
    result.sort(key=lambda item: item["avg_top_depth"])
    return result


def depth_distribution(
    depths: Sequence[float], target_bins: int = 8
) -> dict[str, Any]:
    """钻孔总深分布：基本统计量 + 自适应等宽直方图。"""
    values = [float(d) for d in depths if d and d > 0]
    if not values:
        return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0, "bins": []}

    lo, hi = min(values), max(values)
    avg = sum(values) / len(values)
    bins = _histogram(values, lo, hi, target_bins)
    return {
        "count": len(values),
        "min": round(lo, 2),
        "max": round(hi, 2),
        "avg": round(avg, 2),
        "bins": bins,
    }


def _histogram(
    values: Sequence[float], lo: float, hi: float, target_bins: int
) -> list[dict[str, Any]]:
    if hi <= lo:
        return [
            {
                "start": round(lo, 2),
                "end": round(hi, 2),
                "count": len(values),
            }
        ]
    raw_step = (hi - lo) / max(target_bins, 1)
    magnitude = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
    step = 1.0
    for candidate in (1, 2, 2.5, 5, 10):
        step = candidate * magnitude
        if step >= raw_step:
            break
    start = math.floor(lo / step) * step
    end = math.ceil(hi / step) * step
    bin_count = max(int(round((end - start) / step)), 1)
    counts = [0] * bin_count
    for value in values:
        index = min(int((value - start) / step), bin_count - 1)
        counts[index] += 1
    return [
        {
            "start": round(start + i * step, 2),
            "end": round(start + (i + 1) * step, 2),
            "count": counts[i],
        }
        for i in range(bin_count)
    ]


def workingface_status(faces: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """工作面按状态分组计数，并汇总尺寸信息。"""
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "length_sum": 0.0, "width_sum": 0.0, "sized": 0}
    )
    for face in faces:
        status = str(face.get("status") or "未知").strip() or "未知"
        bucket = buckets[status]
        bucket["count"] += 1
        length = face.get("length")
        width = face.get("width")
        if length and width:
            bucket["length_sum"] += float(length)
            bucket["width_sum"] += float(width)
            bucket["sized"] += 1

    return [
        {
            "status": status,
            "count": bucket["count"],
            "avg_length": round(bucket["length_sum"] / bucket["sized"], 1)
            if bucket["sized"]
            else None,
            "avg_width": round(bucket["width_sum"] / bucket["sized"], 1)
            if bucket["sized"]
            else None,
        }
        for status, bucket in sorted(buckets.items(), key=lambda item: -item[1]["count"])
    ]


def coal_thickness_by_borehole(
    segments_by_borehole: Mapping[str, Sequence[Mapping[str, Any]]],
    coal_keywords: Sequence[str] = ("煤",),
) -> dict[str, dict[str, Any]]:
    """按钻孔聚合煤层（名称含关键字的层）合计厚度。"""
    result: dict[str, dict[str, Any]] = {}
    for borehole_id, segments in segments_by_borehole.items():
        total = 0.0
        layers: list[str] = []
        for row in segments:
            name = str(row.get("layer_name") or "")
            if any(keyword in name for keyword in coal_keywords):
                total += float(row.get("thickness") or 0)
                if name not in layers:
                    layers.append(name)
        result[borehole_id] = {"coal_thickness": round(total, 3), "coal_layers": layers}
    return result


def virtual_borehole(    boreholes: Sequence[Mapping[str, Any]],
    segments_by_borehole: Mapping[str, Sequence[Mapping[str, Any]]],
    x: float,
    y: float,
    max_neighbors: int = 8,
    power: float = 2.0,
) -> dict[str, Any]:
    """IDW 插值生成虚拟钻孔。

    取距查询点最近的 max_neighbors 个有分层数据的钻孔，按 1/d^power 权重
    逐层插值顶/底深；颜色取最近邻同层颜色。邻孔数量与最近孔距作为置信度返回。
    """
    scored: list[tuple[float, str]] = []
    for borehole in boreholes:
        try:
            bx = float(borehole["x"])
            by = float(borehole["y"])
        except (KeyError, TypeError, ValueError):
            continue
        borehole_id = str(borehole.get("id") or "")
        if borehole_id not in segments_by_borehole or not segments_by_borehole[borehole_id]:
            continue
        distance = math.hypot(bx - x, by - y)
        scored.append((max(distance, 1e-6), borehole_id))
    scored.sort(key=lambda item: item[0])
    neighbors = scored[: max(int(max_neighbors), 1)]
    if not neighbors:
        return {"layers": [], "used_neighbors": 0, "nearest_distance_m": None}

    # 逐层加权累计：top/bottom 深度用 IDW，颜色取最近邻
    buckets: dict[str, dict[str, Any]] = {}
    for distance, borehole_id in neighbors:
        weight = 1.0 / (distance ** power)
        for row in segments_by_borehole[borehole_id]:
            name = str(row.get("layer_name") or "").strip()
            if not name:
                continue
            bucket = buckets.setdefault(
                name,
                {"w": 0.0, "top": 0.0, "bottom": 0.0, "count": 0, "color": None},
            )
            bucket["w"] += weight
            bucket["top"] += weight * float(row.get("top_depth") or 0)
            bucket["bottom"] += weight * float(row.get("bottom_depth") or 0)
            bucket["count"] += 1
            if bucket["color"] is None:
                bucket["color"] = row.get("color")

    layers = []
    for name, bucket in buckets.items():
        top = bucket["top"] / bucket["w"] if bucket["w"] else 0.0
        bottom = bucket["bottom"] / bucket["w"] if bucket["w"] else 0.0
        layers.append(
            {
                "layer_name": name,
                "top_depth": round(top, 2),
                "bottom_depth": round(bottom, 2),
                "thickness": round(max(bottom - top, 0.0), 2),
                "color": bucket["color"] or "#8d7358",
                "sample_count": bucket["count"],
            }
        )
    layers.sort(key=lambda item: item["top_depth"])
    return {
        "layers": layers,
        "used_neighbors": len(neighbors),
        "nearest_distance_m": round(neighbors[0][0], 2),
    }


def build_overview(
    boreholes: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    faces: Sequence[Mapping[str, Any]],
    model_count: int,
) -> dict[str, Any]:
    """组合统计概览（不含模型/导入细节）。"""
    depths = [float(b.get("total_depth") or 0) for b in boreholes]
    strata_layers = {str(s.get("layer_name")).strip() for s in segments if s.get("layer_name")}
    return {
        "borehole_count": len(boreholes),
        "segment_count": len(segments),
        "strata_layer_count": len(strata_layers),
        "model_count": model_count,
        "workingface_count": len(faces),
        "total_drilling_depth": round(sum(depths), 1),
        "avg_borehole_depth": round(sum(depths) / len(depths), 1) if depths else 0.0,
        "max_borehole_depth": round(max(depths), 1) if depths else 0.0,
        "thickness_distribution": thickness_distribution(segments),
        "depth_distribution": depth_distribution(depths),
        "layer_frequency": layer_frequency(segments),
        "workingface_status": workingface_status(faces),
    }


def polygon_area(points: Sequence[Sequence[float]]) -> float:
    """鞋带公式计算多边形面积（平方米）。"""
    if len(points) < 3:
        return 0.0
    total = 0.0
    count = len(points)
    for i in range(count):
        x1, y1 = float(points[i][0]), float(points[i][1])
        x2, y2 = float(points[(i + 1) % count][0]), float(points[(i + 1) % count][1])
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def point_in_polygon(x: float, y: float, points: Sequence[Sequence[float]]) -> bool:
    """射线法判断点是否在多边形内。"""
    inside = False
    count = len(points)
    if count < 3:
        return False
    j = count - 1
    for i in range(count):
        xi, yi = float(points[i][0]), float(points[i][1])
        xj, yj = float(points[j][0]), float(points[j][1])
        if (yi > y) != (yj > y):
            intersect_x = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < intersect_x:
                inside = not inside
        j = i
    return inside


def estimate_workingface_reserves(
    face_polygons: Sequence[Mapping[str, Any]],
    boreholes: Sequence[Mapping[str, Any]],
    segments_by_borehole: Mapping[str, Sequence[Mapping[str, Any]]],
    density_t_per_m3: float = 1.35,
    coal_keywords: Sequence[str] = ("煤",),
) -> list[dict[str, Any]]:
    """按工作面圈闭多边形估算煤炭资源量。

    面积取折线多边形鞋带面积；厚度取多边形内钻孔的煤层合计厚度均值；
    资源量 = 面积 × 平均厚度 × 密度。圈闭内无钻孔时厚度/资源量返回 None。
    """
    coal = coal_thickness_by_borehole(
        {str(b.get("id")): segments_by_borehole.get(str(b.get("id")), []) for b in boreholes},
        coal_keywords,
    )
    items: list[dict[str, Any]] = []
    for face in face_polygons:
        points = face.get("points") or []
        area = polygon_area(points)
        if area <= 0:
            continue
        inside_ids = [
            str(borehole["id"])
            for borehole in boreholes
            if borehole.get("id") in segments_by_borehole
            and point_in_polygon(float(borehole["x"]), float(borehole["y"]), points)
        ]
        thicknesses = [
            coal[borehole_id]["coal_thickness"]
            for borehole_id in inside_ids
            if coal.get(borehole_id, {}).get("coal_layers")
        ]
        mean_thickness = round(sum(thicknesses) / len(thicknesses), 2) if thicknesses else None
        reserve_wan_t = (
            round(area * mean_thickness * density_t_per_m3 / 10000, 1)
            if mean_thickness
            else None
        )
        items.append(
            {
                "name": str(face.get("name") or "未命名工作面"),
                "area_m2": round(area, 0),
                "borehole_count": len(inside_ids),
                "mean_coal_thickness_m": mean_thickness,
                "reserve_wan_t": reserve_wan_t,
            }
        )
    items.sort(key=lambda item: -(item["reserve_wan_t"] or 0))
    return items


def idw_grid(
    samples: Sequence[Mapping[str, Any]],
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    nx: int = 100,
    ny: int = 100,
    power: float = 2.0,
) -> list[list[float]]:
    """对采样点做 IDW 插值生成规则网格（行优先，[0][0] 为 (xmin, ymin)）。"""
    points = [
        (float(s["x"]), float(s["y"]), float(s["value"]))
        for s in samples
        if s.get("x") is not None and s.get("y") is not None and s.get("value") is not None
    ]
    grid: list[list[float]] = []
    if not points or xmax <= xmin or ymax <= ymin or nx < 1 or ny < 1:
        return grid
    for row in range(ny):
        y = ymin + (ymax - ymin) * row / (ny - 1) if ny > 1 else ymin
        line: list[float] = []
        for col in range(nx):
            x = xmin + (xmax - xmin) * col / (nx - 1) if nx > 1 else xmin
            numerator = 0.0
            denominator = 0.0
            exact = False
            for px, py, value in points:
                distance = math.hypot(px - x, py - y)
                if distance < 1e-9:
                    numerator = value
                    denominator = 1.0
                    exact = True
                    break
                weight = 1.0 / (distance ** power)
                numerator += weight * value
                denominator += weight
            line.append(numerator / denominator if denominator else 0.0)
            if exact:
                line[-1] = numerator
        grid.append(line)
    return grid


def _nice_step(raw: float) -> float:
    if raw <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(raw))
    for candidate in (1, 2, 2.5, 5, 10):
        step = candidate * magnitude
        if step >= raw:
            return step
    return 10 * magnitude


def marching_squares(
    grid: Sequence[Sequence[float]],
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    levels: Sequence[float],
) -> list[dict[str, Any]]:
    """Marching Squares 提取等值线段（返回投影坐标线段，便于前端直接绘制）。"""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows < 2 or cols < 2 or xmax <= xmin or ymax <= ymin:
        return []
    step_x = (xmax - xmin) / (cols - 1)
    step_y = (ymax - ymin) / (rows - 1)

    # 角点分类 → 边交叉组合（边编号：0=下 1=右 2=上 3=左）
    case_edges: dict[int, tuple[tuple[int, int], ...]] = {
        0b0001: ((3, 0),), 0b0010: ((0, 1),), 0b0011: ((3, 1),),
        0b0100: ((1, 2),), 0b0101: ((3, 2), (0, 1)), 0b0110: ((0, 2),),
        0b0111: ((3, 2),), 0b1000: ((2, 3),), 0b1001: ((0, 2),),
        0b1010: ((2, 3), (1, 0)), 0b1011: ((2, 1),), 0b1100: ((1, 3),),
        0b1101: ((1, 0),), 0b1110: ((0, 3),),
    }

    def corner_value(row: int, col: int) -> float:
        return float(grid[row][col])

    def edge_point(row: int, col: int, edge: int, level: float) -> tuple[float, float]:
        x0 = xmin + col * step_x
        y0 = ymin + row * step_y
        if edge == 0:  # 下边 (row,col)-(row,col+1)
            v0, v1 = corner_value(row, col), corner_value(row, col + 1)
            t = (level - v0) / (v1 - v0)
            return x0 + t * step_x, y0
        if edge == 1:  # 右边 (row,col+1)-(row+1,col+1)
            v0, v1 = corner_value(row, col + 1), corner_value(row + 1, col + 1)
            t = (level - v0) / (v1 - v0)
            return x0 + step_x, y0 + t * step_y
        if edge == 2:  # 上边 (row+1,col)-(row+1,col+1)
            v0, v1 = corner_value(row + 1, col), corner_value(row + 1, col + 1)
            t = (level - v0) / (v1 - v0)
            return x0 + t * step_x, y0 + step_y
        # 左边 (row,col)-(row+1,col)
        v0, v1 = corner_value(row, col), corner_value(row + 1, col)
        t = (level - v0) / (v1 - v0)
        return x0, y0 + t * step_y

    out: list[dict[str, Any]] = []
    for level in levels:
        segments: list[list[float]] = []
        for row in range(rows - 1):
            for col in range(cols - 1):
                code = 0
                if corner_value(row, col) >= level:
                    code |= 0b0001
                if corner_value(row, col + 1) >= level:
                    code |= 0b0010
                if corner_value(row + 1, col + 1) >= level:
                    code |= 0b0100
                if corner_value(row + 1, col) >= level:
                    code |= 0b1000
                if code == 0 or code == 0b1111:
                    continue
                for edge_a, edge_b in case_edges[code]:
                    ax, ay = edge_point(row, col, edge_a, level)
                    bx, by = edge_point(row, col, edge_b, level)
                    segments.extend([round(ax, 2), round(ay, 2), round(bx, 2), round(by, 2)])
        if segments:
            out.append({"level": round(float(level), 2), "segments": segments})
    return out


def burial_depth_contours(
    samples: Sequence[Mapping[str, Any]],
    step: float | None = None,
    grid_size: int = 96,
) -> dict[str, Any]:
    """由钻孔样本生成某地层顶埋深等值线（自动范围/步长）。"""
    if not samples:
        return {"levels": [], "lines": [], "bbox": None}
    xs = [float(s["x"]) for s in samples]
    ys = [float(s["y"]) for s in samples]
    values = [float(s["value"]) for s in samples]
    pad_x = max((max(xs) - min(xs)) * 0.08, 1.0)
    pad_y = max((max(ys) - min(ys)) * 0.08, 1.0)
    xmin, xmax = min(xs) - pad_x, max(xs) + pad_x
    ymin, ymax = min(ys) - pad_y, max(ys) + pad_y
    value_lo, value_hi = min(values), max(values)
    if value_hi <= value_lo:
        return {
            "levels": [],
            "lines": [],
            "bbox": [round(xmin, 2), round(ymin, 2), round(xmax, 2), round(ymax, 2)],
        }
    auto_step = _nice_step((value_hi - value_lo) / 8)
    resolved_step = float(step) if step and step > 0 else auto_step
    start = math.ceil(value_lo / resolved_step) * resolved_step
    levels = []
    level = start
    while level < value_hi:
        levels.append(level)
        level += resolved_step

    grid = idw_grid(samples, xmin, ymin, xmax, ymax, grid_size, grid_size)
    lines = marching_squares(grid, xmin, ymin, xmax, ymax, levels)
    return {
        "levels": [round(level, 2) for level in levels],
        "lines": lines,
        "bbox": [round(xmin, 2), round(ymin, 2), round(xmax, 2), round(ymax, 2)],
    }
